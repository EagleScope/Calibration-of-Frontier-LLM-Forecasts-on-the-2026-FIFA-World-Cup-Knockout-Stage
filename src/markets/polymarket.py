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

from config import config as C
from src.markets import devig as DV

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

_WILL_WIN = re.compile(r"will\s+(.+?)\s+win\b", re.IGNORECASE)
_WIN_ON = re.compile(r"will\s+(.+?)\s+win\s+on\b", re.IGNORECASE)   # per-match "Will X win on <date>?"
_REACH = re.compile(r"will\s+(.+?)\s+reach\b", re.IGNORECASE)       # "Will X reach the <round>?"
_DRAW = re.compile(r"\bdraw\b", re.IGNORECASE)


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


# --------------------- per-match parsers (§13 + AMENDMENT_001) ------------ #
def _yes_price(market: Dict) -> Optional[float]:
    """The 'Yes' outcomePrice for a binary Yes/No market, or None if unusable.

    Gamma returns outcomes/outcomePrices as lists OR JSON-encoded strings."""
    prices = _as_list(market.get("outcomePrices"))
    outcomes = _as_list(market.get("outcomes"))
    if not prices or not outcomes:
        return None
    try:
        yi = [str(o).lower() for o in outcomes].index("yes")
    except ValueError:
        yi = 0
    try:
        v = float(prices[yi])
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def _market_provenance(market: Dict) -> Dict:
    """Per-market price/liquidity fields kept for the manifest (audit trail)."""
    keep = ("question", "outcomes", "outcomePrices", "lastTradePrice",
            "bestBid", "bestAsk", "clobTokenIds", "volume", "liquidity")
    return {k: market.get(k) for k in keep if k in market}


def _relevant_provenance(markets, team_A: str, team_B: str) -> List[Dict]:
    """Provenance only for the markets naming one of the two teams (multi-team
    events like 'Nation To Reach <round>' carry all 48 nations — keep just ours)."""
    a, b = team_A.lower(), team_B.lower()
    return [_market_provenance(m) for m in (markets or [])
            if a in (m.get("question") or "").lower()
            or b in (m.get("question") or "").lower()]


def parse_match_3way(event: Dict, team_A: str, team_B: str) -> Dict[str, float]:
    """Raw 'Yes' prices for a per-match 3-way event, ordered for the pack's A/B.

    The per-match event posts three binary markets — 'Will <A> win on <date>?',
    'Will <B> win on <date>?', 'Will <A> vs <B> end in a draw?'. Returns
    {'A_win','draw','B_win'} raw Yes prices (still sum to ~1 + margin). Pure.
    Raises ValueError if any of the three legs is missing (never fabricates)."""
    a = d = b = None
    for m in event.get("markets") or []:
        q = m.get("question") or ""
        y = _yes_price(m)
        if y is None:
            continue
        mt = _WIN_ON.search(q)
        if mt:
            team = mt.group(1).strip().lower()
            if team == team_A.lower():
                a = y
            elif team == team_B.lower():
                b = y
        elif _DRAW.search(q):
            d = y
    if a is None or d is None or b is None:
        raise ValueError(f"per-match 3-way incomplete: A_win={a} draw={d} B_win={b}")
    return {"A_win": a, "draw": d, "B_win": b}


def parse_advancement_pair(event: Dict, team_A: str, team_B: str) -> Dict[str, float]:
    """Raw 'Yes' prices for both teams from a 'Nation To Reach <round>' event.

    Returns {'A','B'} raw Yes prices. In a single knockout tie exactly one team
    advances, so the pair de-vigs to complementary probabilities. Pure; raises if
    either team's leg is missing."""
    a = b = None
    for m in event.get("markets") or []:
        q = m.get("question") or ""
        mt = _REACH.search(q)
        if not mt:
            continue
        y = _yes_price(m)
        if y is None:
            continue
        team = mt.group(1).strip().lower()
        if team == team_A.lower():
            a = y
        elif team == team_B.lower():
            b = y
    if a is None or b is None:
        raise ValueError(f"advancement pair incomplete: A={a} B={b}")
    return {"A": a, "B": b}


def _devig_all_methods(raw: List[float], keys: List[str]) -> Dict[str, Dict[str, float]]:
    """De-vig one raw vector under the locked primary + registered sensitivity
    methods (§13: proportional primary; odds_ratio, shin sensitivity)."""
    out: Dict[str, Dict[str, float]] = {}
    for meth in (C.DEVIG_PRIMARY, *C.DEVIG_SENSITIVITY):
        probs = DV.devig(raw, method=meth)
        out[meth] = {k: float(v) for k, v in zip(keys, probs)}
    return out


def devig_match_3way(raw3: Dict[str, float], method: str = C.DEVIG_PRIMARY
                     ) -> Dict[str, float]:
    """De-vig a per-match 3-way into {A_WIN,DRAW,B_WIN} (single method)."""
    p = DV.devig([raw3["A_win"], raw3["draw"], raw3["B_win"]], method=method)
    return {"A_WIN": float(p[0]), "DRAW": float(p[1]), "B_WIN": float(p[2])}


def devig_advancement(rawpair: Dict[str, float], method: str = C.DEVIG_PRIMARY
                      ) -> Dict[str, float]:
    """De-vig an advancement pair into {ADV_A,ADV_B} (single method)."""
    p = DV.devig([rawpair["A"], rawpair["B"]], method=method)
    return {"ADV_A": float(p[0]), "ADV_B": float(p[1])}


def find_match_event(search: Dict, team_A: str, team_B: str) -> Optional[Dict]:
    """Locate the per-match 3-way event in a Gamma search payload (has 'win on'
    + 'draw' markets naming both teams). Returns the event or None."""
    for e in (search.get("events") or []):
        qs = " ".join((m.get("question") or "").lower()
                      for m in (e.get("markets") or []))
        if ("win on" in qs and "draw" in qs
                and team_A.lower() in qs and team_B.lower() in qs):
            return e
    return None


def find_advancement_event(search: Dict, team_A: str, team_B: str,
                           next_round: str) -> Optional[Dict]:
    """Locate the 'Nation To Reach <next_round>' event naming both teams."""
    for e in (search.get("events") or []):
        title = (e.get("title") or "").lower()
        if "reach" not in title or next_round.lower() not in title:
            continue
        qs = " ".join((m.get("question") or "").lower()
                      for m in (e.get("markets") or []))
        if team_A.lower() in qs and team_B.lower() in qs:
            return e
    return None


def build_match_benchmark(search: Dict, team_A: str, team_B: str,
                          next_round: Optional[str] = None) -> Dict:
    """Build the structured per-match Polymarket benchmark from a Gamma search
    payload: 3-way (A_WIN/DRAW/B_WIN) and, if `next_round` is given, advancement
    (ADV_A/ADV_B). Each line carries raw Yes prices, de-vigged probabilities under
    all locked methods, and per-market provenance. Missing lines are recorded
    honestly ('captured': false) — never fabricated."""
    out: Dict = {"team_A": team_A, "team_B": team_B}

    ev3 = find_match_event(search, team_A, team_B)
    if ev3 is None:
        out["three_way"] = {"captured": False, "reason": "no per-match 3-way event in search"}
    else:
        try:
            raw3 = parse_match_3way(ev3, team_A, team_B)
            booksum = raw3["A_win"] + raw3["draw"] + raw3["B_win"]
            out["three_way"] = {
                "captured": True, "event_slug": ev3.get("slug"),
                "raw_yes": raw3, "booksum": round(booksum, 6),
                "overround_pct": round((booksum - 1.0) * 100, 4),
                "primary_method": C.DEVIG_PRIMARY,
                "devigged": _devig_all_methods(
                    [raw3["A_win"], raw3["draw"], raw3["B_win"]],
                    ["A_WIN", "DRAW", "B_WIN"]),
                "per_market": _relevant_provenance(ev3.get("markets"), team_A, team_B),
            }
        except ValueError as ex:
            out["three_way"] = {"captured": False, "reason": str(ex)}

    if next_round:
        evA = find_advancement_event(search, team_A, team_B, next_round)
        if evA is None:
            out["advancement"] = {"captured": False,
                                  "reason": f"no '{next_round}' advancement event in search"}
        else:
            try:
                rawp = parse_advancement_pair(evA, team_A, team_B)
                out["advancement"] = {
                    "captured": True, "event_slug": evA.get("slug"),
                    "next_round": next_round, "raw_yes": rawp,
                    "booksum": round(rawp["A"] + rawp["B"], 6),
                    "primary_method": C.DEVIG_PRIMARY,
                    "devigged": _devig_all_methods([rawp["A"], rawp["B"]],
                                                   ["ADV_A", "ADV_B"]),
                    "per_market": _relevant_provenance(evA.get("markets"), team_A, team_B),
                }
            except ValueError as ex:
                out["advancement"] = {"captured": False, "reason": str(ex)}
    return out


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
