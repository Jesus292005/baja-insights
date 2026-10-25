"""Teams, players, base cards and role baselines loaded from ``teams.json``."""

from __future__ import annotations

import json
import unicodedata
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
        """Exact name, or a unique match on full name or surname, ignoring case and accents
        ('torres' -> 'J. Torres', 'ramirez' -> 'M. Ramírez'). None if nothing or more than one matches."""
        if not isinstance(name, str):
            return None
        if name in self.players:
            return self.players[name]
        needle = normalize(name)
        if not needle:
            return None
        hits = [p for p in self.players.values()
                if normalize(p.name) == needle or normalize(p.name).split(". ")[-1] == needle]
        return hits[0] if len(hits) == 1 else None

    def find_team(self, name: str) -> str | None:
        """Full or short name ignoring case and accents ('bahia fc', 'cardon'), or a part of the name
        of at least 3 letters that fits a single team. None otherwise, never a guess."""
        if not isinstance(name, str):
            return None
        needle = normalize(name)
        if not needle:
            return None
        for team, meta in self.team_meta.items():
            if needle in (normalize(team), normalize(str(meta.get("short", "")))):
                return team
        hits = [team for team in self.team_meta if len(needle) >= 3 and needle in normalize(team)]
        return hits[0] if len(hits) == 1 else None


def normalize(text: str) -> str:
    """'  Bahía FC ' -> 'bahia fc': lower case, no accents, single spaces."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(plain.lower().split())


def overall(card: dict) -> int:
    """Overall rating is the rounded mean of the seven card attributes."""
    return round(sum(card[a] for a in CARD_ATTRIBUTES) / len(CARD_ATTRIBUTES))
