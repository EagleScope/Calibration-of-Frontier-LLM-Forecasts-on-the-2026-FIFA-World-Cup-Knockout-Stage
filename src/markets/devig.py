"""
devig.py — remove the bookmaker margin (vig) from implied probabilities (§13).

LOCKED method choice (§13):
  - proportional (basic)  -> PRIMARY  (config.DEVIG_PRIMARY)
  - odds_ratio            -> sensitivity (favorite-longshot aware)
  - shin                  -> sensitivity (insider-trading model)

All functions take RAW implied probabilities (e.g. 1/decimal_odds per outcome,
which sum to > 1 because of the margin) and return true probabilities summing
to 1. Works for the 3-way 1X2 market and for any n-outcome market.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from scipy import optimize

from config import config as C


def implied_from_decimal_odds(odds: Sequence[float]) -> np.ndarray:
    """Raw implied probabilities 1/odds (still include the margin)."""
    o = np.asarray(odds, dtype=float)
    if np.any(o <= 1.0):
        raise ValueError("decimal odds must be > 1.0")
    return 1.0 / o


def _check(raw: Sequence[float]) -> np.ndarray:
    p = np.asarray(raw, dtype=float)
    if p.ndim != 1 or len(p) < 2:
        raise ValueError("need a 1-D vector of >= 2 raw implied probabilities")
    if np.any(p <= 0):
        raise ValueError("raw implied probabilities must be positive")
    return p


def devig_proportional(raw: Sequence[float]) -> np.ndarray:
    """PRIMARY: scale so probabilities sum to 1 (basic normalization)."""
    p = _check(raw)
    return p / p.sum()


def devig_odds_ratio(raw: Sequence[float]) -> np.ndarray:
    """Odds-ratio method (Cheung 2015). Find c so that

        sum_i  p_i / (c + p_i - c*p_i)  == 1

    and return those normalized probabilities. c == 1 reproduces the raw
    probabilities; c is solved to absorb the margin in an odds-ratio-fair way."""
    p = _check(raw)

    def f(c: float) -> float:
        return np.sum(p / (c + p - c * p)) - 1.0

    # booksum>1 => need c>1 to shrink; bracket generously.
    c = optimize.brentq(f, 1e-6, 1e6)
    out = p / (c + p - c * p)
    return out / out.sum()   # guard tiny numerical residual


def devig_shin(raw: Sequence[float]) -> np.ndarray:
    """Shin (1992,1993) method: model a proportion z of insider trading and back
    out true probabilities. Solve for z in [0,1) such that the recovered
    probabilities sum to 1, with booksum B = sum(raw):

        p_true_i = [ sqrt(z^2 + 4(1-z) * p_i^2 / B) - z ] / (2(1-z))
    """
    p = _check(raw)
    B = p.sum()

    def recover(z: float) -> np.ndarray:
        return (np.sqrt(z**2 + 4 * (1 - z) * p**2 / B) - z) / (2 * (1 - z))

    def g(z: float) -> float:
        return float(recover(z).sum() - 1.0)

    # g(0)=B-... ; find root in (0, ~0.5). Fall back to proportional if no margin.
    if abs(B - 1.0) < 1e-12:
        return p / B
    try:
        z = optimize.brentq(g, 1e-9, 0.99)
    except ValueError:
        return devig_proportional(p)
    out = recover(z)
    return out / out.sum()


DEVIG_METHODS = {
    "proportional": devig_proportional,
    "odds_ratio": devig_odds_ratio,
    "shin": devig_shin,
}


def devig(raw: Sequence[float], method: str = C.DEVIG_PRIMARY) -> np.ndarray:
    """Dispatch to a named de-vig method (default = locked primary)."""
    if method not in DEVIG_METHODS:
        raise ValueError(f"method must be one of {sorted(DEVIG_METHODS)}, got {method!r}")
    return DEVIG_METHODS[method](raw)
