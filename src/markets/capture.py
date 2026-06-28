"""
capture.py — pre-kickoff MARKET BENCHMARK capture (§13), raw-first.

Stores the real pre-kickoff market as a BENCHMARK (for scoring), captured at the
matched timestamp. It is NOT fed to the models — the primary arm withholds the
market from the prompt; capturing the price is a separate thing from conditioning
on it.

Design rules (PI directive, item 5):
  - The RAW provider response is the source of truth: archive it verbatim, with a
    UTC capture timestamp and a SHA-256, exactly like the Elo snapshot.
  - De-vig (proportional primary) only if it parses clean; raw numbers are the
    non-negotiable, parsing/de-vig can be finished later.
  - NEVER fabricate, estimate, or substitute a market number. A missing line is
    recorded honestly ("captured": false) — never filled with a guess.
  - Stored under a TRACKED path (data/markets/), committed in a per-round commit
    AFTER the pre-registration tag (§17 public timestamps). It is NOT in the tagged
    commit (the tag is created before any market/forecast commit).

This module separates the PURE archive/manifest logic (offline-tested) from the
thin network fetchers (run only at the kickoff-3h window).
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.markets import pinnacle as PIN
from src.markets import polymarket as PM


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _fetch_raw_bytes(url: str, timeout: float = 25.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "wc-llm-study/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (public/keyed data)
        return r.read()


# ----------------------------- pure archive core -------------------------- #
def archive_payload(out_dir: str, name: str, raw: bytes,
                    capture_timestamp: str) -> Dict:
    """Write raw bytes verbatim + record path/sha256/size/timestamp. Pure I/O."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "wb") as f:
        f.write(raw)
    return {"path": path, "sha256": _sha256_bytes(raw), "bytes": len(raw),
            "captured_at": capture_timestamp}


def _match_event(events: List[Dict], team_A: str, team_B: str) -> Optional[Dict]:
    want = {team_A.lower(), team_B.lower()}
    for e in events:
        names = {str(e.get("home_team", "")).lower(), str(e.get("away_team", "")).lower()}
        if want == names:
            return e
    return None


# ----------------------------- capture (network) -------------------------- #
def capture_market_benchmark(out_dir: str, match_id: str, team_A: str, team_B: str,
                             odds_api_key: str, kickoff_timestamp: str,
                             capture_timestamp: Optional[str] = None,
                             polymarket_next_round: Optional[str] = None) -> Dict:
    """Run at kickoff-3h. Captures Pinnacle (raw + de-vig if clean) and the
    Polymarket per-match 3-way + advancement (§13 + AMENDMENT_001). `polymarket_
    next_round` (e.g. 'Round of 16') enables the advancement line. Writes
    manifest.json. Never fabricates — honest absence is recorded."""
    ts = capture_timestamp or _utc_now_iso()
    os.makedirs(out_dir, exist_ok=True)
    manifest: Dict = {"match_id": match_id, "team_A": team_A, "team_B": team_B,
                      "capture_timestamp": ts, "kickoff_timestamp": kickoff_timestamp,
                      "devig_method": PIN.C.DEVIG_PRIMARY, "pinnacle": {}, "polymarket": {}}

    # --- Pinnacle: RAW first, then de-vig if it parses clean ---
    try:
        q = urllib.parse.urlencode({"apiKey": odds_api_key, "regions": "eu",
                                    "markets": "h2h", "bookmakers": PIN.PINNACLE_KEY,
                                    "oddsFormat": "decimal"})
        url = f"{PIN.ODDS_API_BASE}/sports/{PIN.WC_SPORT_KEY}/odds?{q}"
        raw = _fetch_raw_bytes(url)
        arch = archive_payload(out_dir, f"{match_id}.pinnacle.raw.json", raw, ts)
        manifest["pinnacle"] = {"captured": True, **arch}
        events = json.loads(raw.decode("utf-8"))
        ev = _match_event(events, team_A, team_B)
        if ev is not None:
            parsed = PIN.parse_h2h(ev)
            if parsed is not None:
                manifest["pinnacle"]["raw_odds"] = parsed["odds"]
                try:
                    dv = PIN.devig_h2h(parsed)
                    ab = PIN.align_to_AB(dv, parsed, team_A, team_B)
                    manifest["pinnacle"]["devigged_AB"] = {
                        "A_WIN": float(ab[0]), "DRAW": float(ab[1]), "B_WIN": float(ab[2])}
                except Exception as ex:  # de-vig deferred, raw still captured
                    manifest["pinnacle"]["devig_error"] = str(ex)[:160]
            else:
                manifest["pinnacle"]["note"] = "event found but no Pinnacle h2h market"
        else:
            manifest["pinnacle"]["note"] = "match event not in Pinnacle feed at capture time"
    except Exception as ex:
        manifest["pinnacle"] = {"captured": False, "reason": str(ex)[:200]}

    # --- Polymarket: raw archive + per-match 3-way + advancement (§13 + AMENDMENT_001) ---
    try:
        url = f"{PM.GAMMA}/public-search?{urllib.parse.urlencode({'q': team_A + ' ' + team_B, 'limit_per_type': 20})}"
        raw = _fetch_raw_bytes(url)
        arch = archive_payload(out_dir, f"{match_id}.polymarket.search.raw.json", raw, ts)
        search = json.loads(raw.decode("utf-8"))
        bench = PM.build_match_benchmark(search, team_A, team_B,
                                         next_round=polymarket_next_round)
        manifest["polymarket"] = {"captured": True, "raw_search": arch, "benchmark": bench}
    except Exception as ex:
        manifest["polymarket"] = {"captured": False,
                                  "reason": "no Polymarket capture: " + str(ex)[:160]}

    with open(os.path.join(out_dir, f"{match_id}.market.manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest
