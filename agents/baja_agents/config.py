"""Paths, settings and the Foundry client.

Agent Framework and Azure are imported lazily so the offline pipeline and the
tests run without credentials or network.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = AGENTS_DIR.parent
CONTRACTS = REPO_ROOT / "contracts"
DEFAULT_CACHE_DIR = AGENTS_DIR / ".cache"


@dataclass
class Settings:
    max_calls: int = 250          # hard cap of model calls per match run
    timeout_s: float = 30.0       # per call; on timeout the template is used
    concurrency: int = 4          # model calls in flight at the same time
    block_s: int = 300            # the curator decides once per 5 minutes of play
    cache_dir: Path = DEFAULT_CACHE_DIR


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(AGENTS_DIR / ".env")


def model_name() -> str:
    load_env()
    return os.environ.get("FOUNDRY_MODEL", "")


def verifier_model_name() -> str:
    """Optional stronger deployment for the fact-checker, FOUNDRY_VERIFIER_MODEL. Defaults to FOUNDRY_MODEL."""
    load_env()
    return os.environ.get("FOUNDRY_VERIFIER_MODEL") or model_name()


def make_credential():
    """``az login`` on a laptop, the managed identity in Azure Container Apps.

    DefaultAzureCredential tries, in order: environment variables, workload identity,
    managed identity (``AZURE_CLIENT_ID`` picks a user-assigned one) and then the Azure CLI.
    The shared token cache is skipped so a cached account never wins over ``az login``.
    """
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential(exclude_shared_token_cache_credential=True,
                                  exclude_interactive_browser_credential=True)


_credential = None


def credential():
    """One credential per process, so its tokens are cached and reused by every client."""
    global _credential
    if _credential is None:
        _credential = make_credential()
    return _credential


def make_client(model: str | None = None):
    """FoundryChatClient from FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL (or ``model``) in agents/.env."""
    load_env()
    from agent_framework.foundry import FoundryChatClient

    return FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=model or os.environ["FOUNDRY_MODEL"],
        credential=credential(),
    )


def make_agent(client, name: str, instructions: str):
    from agent_framework import Agent

    return Agent(client=client, name=name, instructions=instructions)
