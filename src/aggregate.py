"""
aggregate.py — aggregate the N=10 samples per (model x reasoning x arm x match).

LOCKED (§10):
  - Primary point forecast  = MEDIAN of the samples (per key).
  - Robustness check        = 10% trimmed mean.
  - Sensitivity             = re-derive at N = 5, 10 (config.SENSITIVITY_N).

Samples are the renormalized probability dicts (parsing.renormalize_five). We
aggregate each key across samples, then renormalize so the three-way and the
advance pair each sum to 1 again (median/trimmed-mean of a simplex need not).
"""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np

from config import config as C


def _trimmed_mean(x: np.ndarray, proportion: float) -> float:
    """Symmetric trimmed mean: drop `proportion` from each tail."""
    x = np.sort(np.asarray(x, dtype=float))
    n = len(x)
    k = int(np.floor(n * proportion))
    if n - 2 * k <= 0:
        return float(np.mean(x))
    return float(np.mean(x[k:n - k]))


def _renorm(d: Dict[str, float]) -> Dict[str, float]:
    out = dict(d)
    s_tw = sum(out[k] for k in C.THREE_WAY_KEYS)
    if s_tw > 0:
        for k in C.THREE_WAY_KEYS:
            out[k] /= s_tw
    s_adv = sum(out[k] for k in C.ADVANCE_KEYS)
    if s_adv > 0:
        for k in C.ADVANCE_KEYS:
            out[k] /= s_adv
    return out


def aggregate(samples: Sequence[Dict[str, float]], method: str = C.PRIMARY_AGGREGATOR
              ) -> Dict[str, float]:
    """Aggregate a list of renormalized 5-key sample dicts.

    method == 'median'        -> per-key median (primary)
    method == 'trimmed_mean'  -> per-key 10% trimmed mean (robustness)
    Result is renormalized so three-way and advance pair each sum to 1.
    """
    if not samples:
        raise ValueError("no samples to aggregate")
    keys = C.FIVE_KEYS
    agg: Dict[str, float] = {}
    for k in keys:
        col = np.array([s[k] for s in samples], dtype=float)
        if method == "median":
            agg[k] = float(np.median(col))
        elif method == "trimmed_mean":
            agg[k] = _trimmed_mean(col, C.TRIMMED_MEAN_PROPORTION)
        else:
            raise ValueError(f"unknown method {method!r}")
    return _renorm(agg)


def dispersion(samples: Sequence[Dict[str, float]],
               keys: Sequence[str] = C.FIVE_KEYS) -> tuple:
    """Per-key spread of the N samples — the model's self-consistency / precision.

    Returns (sd, iqr) dicts in probability units (sample SD, ddof=1; IQR = Q75-Q25).
    Computed from the SAME renormalized samples as the median/trimmed-mean, so no
    extra calls — it just preserves the spread the aggregate would otherwise hide."""
    if not samples:
        raise ValueError("no samples")
    sd: Dict[str, float] = {}
    iqr: Dict[str, float] = {}
    for k in keys:
        col = np.array([s[k] for s in samples], dtype=float)
        sd[k] = float(np.std(col, ddof=1)) if len(col) > 1 else 0.0
        q1, q3 = np.percentile(col, [25, 75])
        iqr[k] = float(q3 - q1)
    return sd, iqr


def sensitivity(samples: Sequence[Dict[str, float]],
                ns: Sequence[int] = C.SENSITIVITY_N,
                method: str = C.PRIMARY_AGGREGATOR) -> Dict[int, Dict[str, float]]:
    """Re-derive the aggregate using the first n samples for each n in `ns`
    (§10 stability demonstration). Skips n values larger than the sample count."""
    out: Dict[int, Dict[str, float]] = {}
    for n in ns:
        if n <= len(samples):
            out[n] = aggregate(samples[:n], method=method)
    return out
