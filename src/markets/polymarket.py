"""
polymarket.py — Polymarket baseline via the public Gamma API (§13).

Gamma API is fully public (no auth, no cost): https://gamma-api.polymarket.com
CLOB price-history is used for the matched pre-kickoff timestamp capture (§13).

VERIFIED AT BUILD (2026-06-27) by querying the live API:
  - Outright / champion market: event slug `world-cup-winner`, structured as one
    binary "Will <Team> win the 2026 FIFA World Cup?" market per team, with
    outcomes ["Yes","No"] and outcomePrices ["<yes>","<no>"]. Champion prob =
    de-vigged Yes prices normalized across teams. -> benchmarks the outright /
    champion target (§8 champion, §13 outright).
  - Also live: `world-cup-nation-to-reach-final`, third-place-advance markets.
  - Per-match knockout markets (advancement / 3-way) are NOT posted yet because
    the knockout bracket is not set (group stage ongoing on the build date). They
    are captured per-round as the bracket reveals (§17 rolling timestamps). §13's
    assumed split stands: Polymarket grades advancement/outright; whether it also
    prices the 3-way-with-draw per match is confirmed when fixtures post.

The pure parsers below are unit-tested on fixtures; network functions are thin
wrappers and are NOT exercised in the test suite (kept offline/deterministic).
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

from src.markets import devig as DV

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

_WILL_WIN = re.compile(r"will\s+(.+?)\s+win\b", re.IGNORECASE)


def _http_get(url: str, timeout: float = 20.0):
    req = urllib.request.Request(url, headers={"User-Agent": "wc-llm-study/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (public API)
        return json.loads(r.read().decode("utf-8"))


def _as_list(maybe_json) -> List:
    """Gamma returns some array fields (outcomes, outcomePrices) as JSON strings."""
    if isinstance(maybe_json, list):
        return maybe_json
    if isinstance(maybe_json, str):
        try:
            return json.loads(maybe_json)
        except json.JSONDecodeError:
            return []
    return []


# ----------------------------- pure parsers ------------------------------- #
def parse_champion_event(event: Dict) -> Dict[str, float]:
    """Extract raw Yes prices per team from a `world-cup-winner`-style event.

    Returns {team: yes_price} for teams with a usable (>0) price. Pure; takes the
    already-fetched event JSON so it is testable offline."""
    out: Dict[str, float] = {}
    for m in event.get("markets") or []:
        q = m.get("question") or ""
        mt = _WILL_WIN.search(q)
        if not mt:
            continue
        team = mt.group(1).strip()
        prices = _as_list(m.get("outcomePrices"))
        outcomes = _as_list(m.get("outcomes"))
        if not prices or not outcomes:
            continue
        # Yes price is the price aligned with the "Yes" outcome.
        try:
            yi = [o.lower() for o in outcomes].index("yes")
        except ValueError:
            yi = 0
        try:
            yes = float(prices[yi])
        except (TypeError, ValueError):
            continue
        if yes > 0:
            out[team] = yes
    return out


def devig_champion(raw_yes: Dict[str, float], method: str = "proportional"
                   ) -> Dict[str, float]:
    """De-vig champion Yes prices into probabilities summing to 1 across teams."""
    if not raw_yes:
        return {}
    teams = list(raw_yes.keys())
    probs = DV.devig([raw_yes[t] for t in teams], method=method)
    return {t: float(p) for t, p in zip(teams, probs)}


# ----------------------------- network wrappers --------------------------- #
def fetch_event_by_slug(slug: str) -> Optional[Dict]:
    """Fetch a single event by slug from Gamma (returns the first match or None)."""
    url = f"{GAMMA}/events?{urllib.parse.urlencode({'slug': slug})}"
    data = _http_get(url)
    events = data.get("events") if isinstance(data, dict) else data
    if isinstance(events, list) and events:
        return events[0]
    return None


def fetch_champion_probabilities(slug: str = "world-cup-winner",
                                 method: str = "proportional") -> Dict[str, float]:
    """Live: fetch + parse + de-vig the champion/outright market (§8, §13)."""
    event = fetch_event_by_slug(slug)
    if event is None:
        return {}
    return devig_champion(parse_champion_event(event), method=method)


def fetch_prices_history(clob_token_id: str, interval: str = "max",
                         fidelity: int = 1) -> Dict:
    """CLOB price history for a token, for matched pre-kickoff capture (§13)."""
    q = urllib.parse.urlencode({"market": clob_token_id, "interval": interval,
                                "fidelity": fidelity})
    return _http_get(f"{CLOB}/prices-history?{q}")
