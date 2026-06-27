"""
pinnacle.py — Pinnacle closing-line baseline for the 3-way (1X2) benchmark (§13).

Pinnacle has no open API; we source its odds through an aggregator that exposes
Pinnacle h2h prices. The default integration targets the-odds-api.com v4, which
returns per-bookmaker decimal odds. The CLOSING line is captured by polling near
kickoff (the last odds before the matched pre-kickoff timestamp, §13); the
aggregator's historical-odds endpoint can pin an exact timestamp on paid tiers.

Pure parsers (offline-tested) + de-vig via src.markets.devig; the network wrapper
is a thin call gated on the odds-API key in .env (ODDS_API_KEY).

the-odds-api v4 event shape (h2h soccer):
  { "home_team": "...", "away_team": "...", "commence_time": "...Z",
    "bookmakers": [ { "key": "pinnacle", "markets": [
       { "key": "h2h", "outcomes": [ {"name": "<home>", "price": 1.8},
                                     {"name": "<away>", "price": 4.5},
                                     {"name": "Draw",   "price": 3.6} ] } ] } ] }
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

import numpy as np

from config import config as C
from src.markets import devig as DV
from src.records import MarketSnapshot

ODDS_API_BASE = "https://api.the-odds-api.com/v4"
WC_SPORT_KEY = "soccer_fifa_world_cup"
PINNACLE_KEY = "pinnacle"


# ------------------------------- pure parsers ----------------------------- #
def parse_h2h(event: Dict, bookmaker_key: str = PINNACLE_KEY) -> Optional[Dict]:
    """Extract {home_team, away_team, commence_time, odds:{home,draw,away}} for the
    given bookmaker's h2h market. Returns None if that bookmaker/market is absent."""
    home = event.get("home_team")
    away = event.get("away_team")
    for bk in event.get("bookmakers") or []:
        if bk.get("key") != bookmaker_key:
            continue
        for mk in bk.get("markets") or []:
            if mk.get("key") != "h2h":
                continue
            prices: Dict[str, float] = {}
            for oc in mk.get("outcomes") or []:
                prices[oc.get("name")] = float(oc.get("price"))
            if home in prices and away in prices and "Draw" in prices:
                return {
                    "home_team": home, "away_team": away,
                    "commence_time": event.get("commence_time"),
                    "odds": {"home": prices[home], "draw": prices["Draw"],
                             "away": prices[away]},
                    "last_update": bk.get("last_update"),
                }
    return None


def devig_h2h(parsed: Dict, method: str = C.DEVIG_PRIMARY) -> Dict[str, float]:
    """De-vig the three decimal odds into {home,draw,away} probabilities (§13)."""
    o = parsed["odds"]
    raw = DV.implied_from_decimal_odds([o["home"], o["draw"], o["away"]])
    probs = DV.devig(raw, method=method)
    return {"home": float(probs[0]), "draw": float(probs[1]), "away": float(probs[2])}


def align_to_AB(devigged: Dict[str, float], parsed: Dict,
                team_A: str, team_B: str) -> np.ndarray:
    """Map {home,draw,away} probs to the pack's ordered [P(Awin),P(draw),P(Bwin)].

    World Cup knockouts are neutral-venue, so 'home/away' are nominal labels; we
    align strictly by team name to the pack's A/B."""
    home, away = parsed["home_team"], parsed["away_team"]
    if {home, away} != {team_A, team_B}:
        raise ValueError(f"event teams {home}/{away} != pack teams {team_A}/{team_B}")
    p_a = devigged["home"] if home == team_A else devigged["away"]
    p_b = devigged["home"] if home == team_B else devigged["away"]
    return np.array([p_a, devigged["draw"], p_b])


def snapshot(event: Dict, match_id: str, kickoff_timestamp: str, capture_timestamp: str,
             team_A: str, team_B: str, method: str = C.DEVIG_PRIMARY) -> MarketSnapshot:
    """Build a §21 MarketSnapshot for the Pinnacle 3-way line."""
    parsed = parse_h2h(event)
    if parsed is None:
        raise ValueError("no Pinnacle h2h market in event")
    dv = devig_h2h(parsed, method=method)
    ab = align_to_AB(dv, parsed, team_A, team_B)
    return MarketSnapshot(
        source="pinnacle", match_id=match_id, raw=parsed["odds"], devig_method=method,
        devigged={"A_WIN": float(ab[0]), "DRAW": float(ab[1]), "B_WIN": float(ab[2])},
        capture_timestamp=capture_timestamp, kickoff_timestamp=kickoff_timestamp,
        market_kind="three_way")


# ------------------------------ network wrapper --------------------------- #
def fetch_odds(api_key: str, sport_key: str = WC_SPORT_KEY, regions: str = "eu",
               markets: str = "h2h", bookmakers: str = PINNACLE_KEY,
               odds_format: str = "decimal") -> List[Dict]:
    """Live: fetch current odds for a sport (poll near kickoff for the closing line)."""
    q = urllib.parse.urlencode({"apiKey": api_key, "regions": regions, "markets": markets,
                                "bookmakers": bookmakers, "oddsFormat": odds_format})
    url = f"{ODDS_API_BASE}/sports/{sport_key}/odds?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "wc-llm-study/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
        return json.loads(r.read().decode("utf-8"))
