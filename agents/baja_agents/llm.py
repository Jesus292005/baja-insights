"""One door to the models: response cache, call budget, timeout and failure counting.

``LLMRunner.run`` returns the parsed pydantic object, or ``None`` when the call is
skipped (offline, budget spent) or fails. Callers then fall back to templates.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Waits before retrying a call the deployment rejected for its tokens-per-minute limit (HTTP 429).
RATE_LIMIT_WAITS_S = (10, 30)


def is_rate_limit(exc: BaseException) -> bool:
    text = str(exc)
    return "429" in text or "rate_limit" in text.lower()


@dataclass
class Stats:
    calls: int = 0
    cache_hits: int = 0
    failures: int = 0
    skipped: int = 0
    rate_limited: int = 0
    by_agent: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"calls": self.calls, "cache_hits": self.cache_hits, "failures": self.failures,
                "skipped": self.skipped, "rate_limit_retries": self.rate_limited, "calls_by_agent": dict(self.by_agent)}


class LLMRunner:
    def __init__(self, *, max_calls: int, timeout_s: float, concurrency: int,
                 cache_dir: Path | None, model: str = "", offline: bool = False):
        self.max_calls = max_calls
        self.timeout_s = timeout_s
        self.cache_dir = cache_dir
        self.model = model
        self.offline = offline
        self.stats = Stats()
        self._sem = asyncio.Semaphore(concurrency)

    def _key(self, agent_name: str, version: str, payload: dict) -> str:
        raw = json.dumps({"agent": agent_name, "version": version, "model": self.model, "payload": payload},
                         ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _cache_path(self, agent_name: str, key: str) -> Path | None:
        return self.cache_dir / agent_name / f"{key}.json" if self.cache_dir else None

    async def run(self, agent, agent_name: str, version: str, payload: dict, schema: type[T]) -> T | None:
        key = self._key(agent_name, version, payload)
        path = self._cache_path(agent_name, key)
        if path and path.exists():
            try:
                value = schema.model_validate_json(path.read_text(encoding="utf-8"))
                self.stats.cache_hits += 1
                return value
            except ValidationError:
                path.unlink(missing_ok=True)

        if self.offline or agent is None or self.stats.calls >= self.max_calls:
            self.stats.skipped += 1
            return None

        self.stats.calls += 1
        self.stats.by_agent[agent_name] = self.stats.by_agent.get(agent_name, 0) + 1
        for attempt in range(len(RATE_LIMIT_WAITS_S) + 1):
            try:
                async with self._sem:
                    response = await asyncio.wait_for(
                        agent.run(json.dumps(payload, ensure_ascii=False), options={"response_format": schema}),
                        timeout=self.timeout_s,
                    )
                value = response.value if isinstance(response.value, schema) else schema.model_validate_json(response.text)
                break
            except Exception as exc:  # noqa: BLE001 - any failure means "use the template"
                if is_rate_limit(exc) and attempt < len(RATE_LIMIT_WAITS_S):
                    self.stats.rate_limited += 1
                    await asyncio.sleep(RATE_LIMIT_WAITS_S[attempt])
                    continue
                self.stats.failures += 1
                log.warning("%s failed: %s", agent_name, str(exc)[:200])
                return None

        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value.model_dump_json(), encoding="utf-8")
        return value
