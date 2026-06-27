"""
elo_eloratings.py — Elo source adapter for the §11 pack (eloratings.net).

eloratings.net (World Football Elo Ratings) is the protocol's Elo source (§11).
It serves clean TSV — no HTML scraping:
  - https://www.eloratings.net/World.tsv     current ratings: cols [rank, rank2,
    CODE, RATING, ...]; RATING is the integer at column index 3.
  - https://www.eloratings.net/en.teams.tsv  CODE -> name(s) (first = canonical).

The pure parsers below are fixture-tested; the live fetch is a thin wrapper used
to build a name->rating map and produce the eloA/eloB/elo_diff pack fields.

Provides the §11 Elo fields only. Freeze the values via data_freeze.freeze_pack
so every model receives the byte-identical frozen pack (§11/§12).
"""
from __future__ import annotations

import urllib.request
from typing import Dict, Optional

WORLD_TSV = "https://www.eloratings.net/World.tsv"
TEAMS_TSV = "https://www.eloratings.net/en.teams.tsv"

# Minimal alias map: pack/common names -> eloratings.net canonical names.
NAME_ALIASES: Dict[str, str] = {
    "USA": "United States",
    "US": "United States",
    "United States of America": "United States",
    "South Korea": "Korea Republic",
    "North Korea": "Korea DPR",
    "Ivory Coast": "Côte d'Ivoire",
}


def _http_get(url: str, timeout: float = 20.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "wc-llm-study/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (public data)
        return r.read().decode("utf-8", "replace")


# ------------------------------ pure parsers ------------------------------ #
def parse_world_tsv(text: str) -> Dict[str, int]:
    """CODE -> current Elo rating (integer at column index 3)."""
    out: Dict[str, int] = {}
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) > 3 and f[2] and f[3].isdigit():
            out[f[2]] = int(f[3])
    return out


def parse_teams_tsv(text: str) -> Dict[str, str]:
    """CODE -> canonical team name (first name field; skips *_loc location rows)."""
    out: Dict[str, str] = {}
    for line in text.splitlines():
        f = line.split("\t")
        if len(f) >= 2 and "_loc" not in f[0] and f[1].strip():
            out[f[0]] = f[1].strip()
    return out


def build_name_ratings(world_tsv: str, teams_tsv: str) -> Dict[str, int]:
    """name -> rating, by joining the two TSVs on the team code."""
    code2rating = parse_world_tsv(world_tsv)
    code2name = parse_teams_tsv(teams_tsv)
    return {code2name[c]: r for c, r in code2rating.items() if c in code2name}


# ------------------------------ source class ------------------------------ #
class EloRatingsSource:
    """Live Elo source. Fetches once and caches the name->rating map."""

    name = "eloratings.net"

    def __init__(self, name_ratings: Optional[Dict[str, int]] = None):
        # Injectable map keeps this testable offline; else call .load().
        self._ratings = name_ratings or {}

    def load(self) -> "EloRatingsSource":
        self._ratings = build_name_ratings(_http_get(WORLD_TSV), _http_get(TEAMS_TSV))
        return self

    def _canon(self, team: str) -> str:
        return NAME_ALIASES.get(team, team)

    def get_rating(self, team: str) -> Optional[int]:
        return self._ratings.get(self._canon(team))

    def elo_fields(self, team_A: str, team_B: str) -> Dict[str, int]:
        """Return {eloA, eloB, elo_diff} for the §20.2 pack; raises if unknown."""
        a = self.get_rating(team_A)
        b = self.get_rating(team_B)
        if a is None or b is None:
            missing = [t for t, v in ((team_A, a), (team_B, b)) if v is None]
            raise KeyError(f"no eloratings.net rating for: {missing} "
                           f"(add to NAME_ALIASES if a naming mismatch)")
        return {"eloA": a, "eloB": b, "elo_diff": a - b}
