"""Teams, players, base cards and role baselines loaded from ``teams.json``."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .contract import CARD_ATTRIBUTES

DEFAULT_TEAMS_PATH = Path(__file__).resolve().parents[2] / "mocks" / "teams.json"


@dataclass(frozen=True)
class Player:
    name: str
    team: str
    number: int
    position: str
    starter: bool
    card: dict = field(hash=False, compare=False)


@dataclass
class Roster:
    match: dict
    home: str
    away: str
    players: dict[str, Player]
    baselines: dict[str, dict[str, float]]
    team_meta: dict[str, dict]

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Roster":
        data = json.loads(Path(path or DEFAULT_TEAMS_PATH).read_text(encoding="utf-8"))
        players: dict[str, Player] = {}
        team_meta: dict[str, dict] = {}
        for team in data["teams"]:
            team_meta[team["name"]] = {k: v for k, v in team.items() if k != "players"}
            for p in team["players"]:
                players[p["name"]] = Player(
                    name=p["name"], team=team["name"], number=p["number"],
                    position=p["position"], starter=p["starter"], card=dict(p["card"]),
                )
        baselines = {k: v for k, v in data["role_baselines_per_90"].items() if not k.startswith("_")}
        return cls(
            match=data["match"], home=data["match"]["home"], away=data["match"]["away"],
            players=players, baselines=baselines, team_meta=team_meta,
        )

    def opponent(self, team: str) -> str:
        return self.away if team == self.home else self.home

    def team_players(self, team: str, starters_only: bool = False) -> list[Player]:
        return [p for p in self.players.values() if p.team == team and (p.starter or not starters_only)]

    def by_position(self, team: str, position: str, starters_only: bool = True) -> list[Player]:
        return [p for p in self.team_players(team, starters_only) if p.position == position]

    def find(self, name: str) -> Player | None:
        """Exact name, or a unique case-insensitive match on surname ('torres' -> 'J. Torres')."""
        if name in self.players:
            return self.players[name]
        needle = name.strip().lower()
        hits = [p for p in self.players.values()
                if p.name.lower() == needle or p.name.lower().split(". ")[-1] == needle]
        return hits[0] if len(hits) == 1 else None

    def find_team(self, name: str) -> str | None:
        needle = name.strip().lower()
        for team, meta in self.team_meta.items():
            if needle in (team.lower(), str(meta.get("short", "")).lower()) or needle in team.lower():
                return team
        return None


def overall(card: dict) -> int:
    """Overall rating is the rounded mean of the seven card attributes."""
    return round(sum(card[a] for a in CARD_ATTRIBUTES) / len(CARD_ATTRIBUTES))
