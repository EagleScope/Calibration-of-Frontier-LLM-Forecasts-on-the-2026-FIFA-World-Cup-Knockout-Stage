"""
run_aggregate.py — Module §18.3: run the design grid for a match, parse, store,
and aggregate by median (+ trimmed-mean robustness).

For one match the grid is (per §4/§5/§7/§10):
    for each model:
        for each reasoning level it supports (Gemini: high only):
            for each arm in {primary, conditioning}:
                call forecast() N times (config.N_SAMPLES)

Raw ForecastRecords (incl. unparsed) are appended to JSONL for full provenance
(§21). Parsed+renormalized samples are aggregated into an AggregatedForecast.
Clients are injected, so this is fully testable with offline fakes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import config as C
from src import aggregate as AGG
from src import parsing as P
from src.clients.base import ModelClient
from src.records import AggregatedForecast, ForecastRecord, append_jsonl


Cell = Tuple[str, str, str]   # (model_name, reasoning_level, arm)


@dataclass
class CellResult:
    model_name: str
    reasoning_level: str
    arm: str
    records: List[ForecastRecord]
    aggregate: Optional[AggregatedForecast]

    @property
    def clean_rate(self) -> float:
        if not self.records:
            return 0.0
        return sum(r.parse_clean for r in self.records) / len(self.records)


def _renormalized_samples(records: List[ForecastRecord]) -> List[Dict[str, float]]:
    samples: List[Dict[str, float]] = []
    for r in records:
        if r.parsed is None:
            continue
        try:
            samples.append(P.renormalize_five(r.parsed))
        except P.ParseError:
            continue
    return samples


def aggregate_cell(records: List[ForecastRecord], model_name: str,
                   reasoning_level: str, arm: str, match_id: str
                   ) -> Optional[AggregatedForecast]:
    samples = _renormalized_samples(records)
    if not samples:
        return None
    median = AGG.aggregate(samples, method="median")
    trimmed = AGG.aggregate(samples, method="trimmed_mean")
    sd, iqr = AGG.dispersion(samples)
    times = [r.timestamp for r in records if r.timestamp]
    window = {"start": min(times), "end": max(times)} if times else {"start": "", "end": ""}
    return AggregatedForecast(
        model_name=model_name, reasoning_level=reasoning_level, arm=arm,
        match_id=match_id, n=len(samples), median=median, trimmed_mean=trimmed,
        timestamp_window=window, sd=sd, iqr=iqr)


def run_match(clients: Dict[str, ModelClient], match_id: str, pack_fields: Dict,
              market: Optional[Dict] = None, n: int = C.N_SAMPLES,
              records_path: Optional[str] = None) -> Dict[Cell, CellResult]:
    """Run the full grid for one match. `clients` maps model_name -> ModelClient.

    The conditioning arm is only run when `market` is supplied (else skipped, since
    §20.4 needs the market line)."""
    out: Dict[Cell, CellResult] = {}
    for spec in C.MODELS:
        client = clients.get(spec.name)
        if client is None:
            continue
        for level in spec.reasoning_kwargs.keys():     # 'low'/'high' or just 'high'
            for arm in C.ARMS:
                if arm == "conditioning" and market is None:
                    continue
                records: List[ForecastRecord] = []
                for i in range(n):
                    rec = client.forecast(
                        pack_fields, reasoning_level=level, arm=arm,
                        match_id=match_id, sample_index=i,
                        market=market if arm == "conditioning" else None)
                    records.append(rec)
                    if records_path:
                        append_jsonl(records_path, rec.to_dict())
                agg = aggregate_cell(records, spec.name, level, arm, match_id)
                out[(spec.name, level, arm)] = CellResult(
                    spec.name, level, arm, records, agg)
    return out


def three_way_vector(agg: AggregatedForecast) -> np.ndarray:
    """[P(A win), P(draw), P(B win)] from an aggregate (for RPS/Brier scoring)."""
    return np.array([agg.median[k] for k in C.THREE_WAY_KEYS], dtype=float)


def advance_prob_A(agg: AggregatedForecast) -> float:
    """P(team A advances) from an aggregate (for calibration scoring)."""
    return float(agg.median["ADV_A"])


def expected_calls_per_match(n: int = C.N_SAMPLES) -> int:
    """Sanity check against the §18 scale estimate (280 calls/match at N=20)."""
    total = 0
    for spec in C.MODELS:
        total += len(spec.reasoning_kwargs) * len(C.ARMS) * n
    return total
