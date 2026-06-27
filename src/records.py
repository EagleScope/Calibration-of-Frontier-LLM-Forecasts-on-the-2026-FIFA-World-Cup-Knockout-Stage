"""
records.py — stored data schemas (§21).

Three record types, each JSON-serializable so the raw study data is auditable:
  ForecastRecord       — one per model call (§21)
  AggregatedForecast   — one per (model x reasoning x arm x match) (§21)
  MarketSnapshot       — one per (market, match) (§21)

A small JSONL append helper keeps raw + parsed forecasts in newline-delimited
JSON so the full provenance is preserved.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0          # high-reasoning half dominates cost (§18)
    total_tokens: int = 0
    usd_cost: Optional[float] = None   # filled from per-provider price table (PENDING)


@dataclass
class ForecastRecord:
    """Per-call record (§21)."""
    model_name: str
    model_id: str                      # exact API identifier
    provider: str
    api_version: str                   # logged per call (§5)
    parameters: Dict                   # all params sent (reasoning kwargs, temp, ...)
    reasoning_level: str               # 'low' | 'high'
    arm: str                           # 'primary' | 'conditioning'
    match_id: str
    sample_index: int                  # 0..N-1
    timestamp: str                     # ISO-8601, when the call returned
    raw_response: str                  # verbatim model text
    parsed: Optional[Dict[str, int]]   # {A_WIN,DRAW,B_WIN,ADV_A,ADV_B} or None if unparsed
    parse_clean: bool = False          # passed strict is_clean_five_key (§19 gate)
    n_attempts: int = 1                # incl. retries on parse failure
    usage: TokenUsage = field(default_factory=TokenUsage)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AggregatedForecast:
    """Per (model x reasoning x arm x match) aggregate (§21)."""
    model_name: str
    reasoning_level: str
    arm: str
    match_id: str
    n: int
    median: Dict[str, float]           # per-key median (primary point forecast)
    trimmed_mean: Dict[str, float]     # 10% trimmed mean (robustness)
    timestamp_window: Dict[str, str]   # {'start':..., 'end':...}

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MarketSnapshot:
    """Per (market, match) snapshot (§21)."""
    source: str                        # 'polymarket' | 'pinnacle'
    match_id: str
    raw: Dict                          # raw odds/prices as captured
    devig_method: str
    devigged: Dict[str, float]         # de-vigged probabilities
    capture_timestamp: str
    kickoff_timestamp: str
    market_kind: str = ""              # 'three_way' | 'advancement' | 'outright'

    def to_dict(self) -> Dict:
        return asdict(self)


def append_jsonl(path: str, record: Dict) -> None:
    """Append one record as a JSON line (preserves raw provenance)."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> List[Dict]:
    out: List[Dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out
