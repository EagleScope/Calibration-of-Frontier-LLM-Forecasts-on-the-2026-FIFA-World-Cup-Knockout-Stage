"""
fifa_ranking.py — FIFA ranking source for the §11 pack.

The FIFA ranking page (inside.fifa.com/fifa-world-ranking/men) is a bot-protected
server-rendered SPA with no clean public JSON endpoint, and it defaults to the
LIVE (unofficial, mid-window) ranking. For a pre-registration we must freeze the
OFFICIAL published ranking, not the in-flux live one (§11/§12).

So this adapter follows the freeze philosophy: it loads a COMMITTED frozen
ranking table (JSON), rather than scraping FIFA live on every run. The table is
captured once from the official source and version-pinned by its publish date.

Table JSON schema:
  {
    "source": "FIFA/Coca-Cola Men's World Ranking",
    "official_date": "2026-06-11",
    "captured_at": "<ISO timestamp>",
    "official": true,
    "ranking": { "<team>": {"rank": <int>, "points": <float>}, ... }
  }
"""
from __future__ import annotations

import json
from typing import Dict, Optional

# Pack/common names -> FIFA table names (extend as fixtures require).
NAME_ALIASES: Dict[str, str] = {
    "United States": "USA",
    "US": "USA",
    "South Korea": "Korea Republic",
    "North Korea": "Korea DPR",
    "Ivory Coast": "Côte d'Ivoire",
    "Iran": "IR Iran",
}


def load_ranking_table(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class FifaRankingSource:
    """FIFA ranking from a frozen table. Inject a dict (tests) or use load()."""

    name = "FIFA"

    def __init__(self, table: Optional[Dict] = None):
        self._table = table or {"ranking": {}}

    def load(self, path: str) -> "FifaRankingSource":
        self._table = load_ranking_table(path)
        return self

    @property
    def official(self) -> bool:
        return bool(self._table.get("official", False))

    @property
    def official_date(self) -> Optional[str]:
        return self._table.get("official_date")

    def _canon(self, team: str) -> str:
        return NAME_ALIASES.get(team, team)

    def get_rank(self, team: str) -> Optional[int]:
        row = self._table.get("ranking", {}).get(self._canon(team))
        return int(row["rank"]) if row else None

    def get_points(self, team: str) -> Optional[float]:
        row = self._table.get("ranking", {}).get(self._canon(team))
        return float(row["points"]) if row else None

    def fifa_rank_fields(self, team_A: str, team_B: str) -> Dict[str, int]:
        """Return {rankA, rankB} for the §20.2 pack; raises if a team is missing."""
        ra = self.get_rank(team_A)
        rb = self.get_rank(team_B)
        if ra is None or rb is None:
            missing = [t for t, v in ((team_A, ra), (team_B, rb)) if v is None]
            raise KeyError(f"no FIFA rank for: {missing} "
                           f"(add to NAME_ALIASES or the frozen table)")
        return {"rankA": ra, "rankB": rb}
