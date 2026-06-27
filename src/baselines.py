"""
baselines.py — statistical reference points and the LLM ensemble (§13).

§13 lists three statistical reference points computed on the SAME pack, plus an
equal-weight LLM ensemble reported beside the individual models:

  1. Elo model          -> elo_1x2
  2. Poisson goals model in the Dixon-Coles tradition -> dixon_coles_1x2
  3. Trivial favorite (higher-rated team always)      -> trivial_favorite_1x2
  + Equal-weight LLM ensemble                         -> ensemble_three_way / _advance

All produce ordered three-way probabilities [P(A win), P(draw), P(B win)] so the
frozen scoring (RPS/Brier/log) applies directly.

The exact pack->parameter mappings the protocol leaves open are flagged
PENDING_SIGNOFF and exposed as explicit arguments (defaults are transparent and
documented), so the *math* is fixed here while the *parameterization* is confirmed
before lock. The trivial favorite is fully specified by the protocol.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence

import numpy as np

from config import config as C

# PENDING_SIGNOFF: Elo->1X2 draw model parameters (protocol names the "Elo model"
# but not the exact 1X2 split). Transparent Gaussian draw-width default.
ELO_DRAW_MAX = 0.28      # peak draw probability for evenly matched teams
ELO_DRAW_SCALE = 200.0   # Elo points; larger mismatch -> smaller draw prob
# PENDING_SIGNOFF: Dixon-Coles low-score correlation parameter (DC found small <0).
DC_RHO_DEFAULT = -0.05
DC_MAX_GOALS = 10
# Trivial favourite confidence within the locked [0.01,0.99] bounds (§14).
TRIVIAL_HI, TRIVIAL_LO = 0.98, 0.01


def _renorm3(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    s = v.sum()
    if s <= 0:
        raise ValueError("three-way vector must have positive mass")
    return v / s


def elo_1x2(elo_diff: float, draw_max: float = ELO_DRAW_MAX,
            draw_scale: float = ELO_DRAW_SCALE) -> np.ndarray:
    """Elo reference: convert the Elo difference (A - B) to [P(Awin),P(draw),P(Bwin)].

    Expected score  We = 1 / (1 + 10**(-d/400))   (neutral venue).
    Draw model      P(draw) = draw_max * exp(-(d/draw_scale)**2)   (peaks when even).
    Then            P(Awin) = We - P(draw)/2 ,  P(Bwin) = 1 - We - P(draw)/2 .
    """
    d = float(elo_diff)
    we = 1.0 / (1.0 + 10.0 ** (-d / 400.0))
    p_draw = draw_max * math.exp(-((d / draw_scale) ** 2))
    p_a = we - p_draw / 2.0
    p_b = 1.0 - we - p_draw / 2.0
    v = np.clip(np.array([p_a, p_draw, p_b]), 1e-6, None)
    return _renorm3(v)


def trivial_favorite_1x2(elo_diff: float) -> np.ndarray:
    """Trivial-favourite reference (§13): the higher-rated team always.

    Encoded as a probabilistic forecast within the locked [0.01,0.99] bounds:
    nearly all mass on the favourite's win (draw at the floor). A zero Elo
    difference yields a symmetric coin-flip with a floor draw."""
    floor = TRIVIAL_LO
    if elo_diff > 0:
        v = np.array([TRIVIAL_HI, floor, floor])
    elif elo_diff < 0:
        v = np.array([floor, floor, TRIVIAL_HI])
    else:
        v = np.array([0.5 - floor / 2, floor, 0.5 - floor / 2])
    return _renorm3(v)


def _dc_tau(x: int, y: int, lA: float, lB: float, rho: float) -> float:
    """Dixon-Coles low-score dependence correction."""
    if x == 0 and y == 0:
        return 1.0 - lA * lB * rho
    if x == 0 and y == 1:
        return 1.0 + lA * rho
    if x == 1 and y == 0:
        return 1.0 + lB * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


def dixon_coles_1x2(lambda_A: float, lambda_B: float, rho: float = DC_RHO_DEFAULT,
                    max_goals: int = DC_MAX_GOALS) -> np.ndarray:
    """Poisson/Dixon-Coles reference: scoreline grid with the DC tau correction,
    summed into [P(Awin),P(draw),P(Bwin)]. `lambda_*` are expected goals."""
    if lambda_A <= 0 or lambda_B <= 0:
        raise ValueError("expected goals must be positive")
    xs = np.arange(0, max_goals + 1)
    pA = np.array([math.exp(-lambda_A) * lambda_A ** k / math.factorial(k) for k in xs])
    pB = np.array([math.exp(-lambda_B) * lambda_B ** k / math.factorial(k) for k in xs])
    p_awin = p_draw = p_bwin = 0.0
    for x in xs:
        for y in xs:
            p = _dc_tau(x, y, lambda_A, lambda_B, rho) * pA[x] * pB[y]
            if x > y:
                p_awin += p
            elif x == y:
                p_draw += p
            else:
                p_bwin += p
    return _renorm3(np.array([p_awin, p_draw, p_bwin]))


# PENDING_SIGNOFF: how expected goals are derived from the pack (Elo diff + recent
# goals). Transparent default below; confirm the exact mapping before lock.
def expected_goals_from_pack(elo_diff: float, base_goals: float = 1.35,
                             elo_per_goal: float = 250.0) -> Dict[str, float]:
    """Map Elo difference to expected goals for each side (PENDING_SIGNOFF default).
    base_goals = league-average goals/team; Elo diff tilts the split."""
    tilt = elo_diff / elo_per_goal
    return {"lambda_A": max(0.1, base_goals + tilt / 2),
            "lambda_B": max(0.1, base_goals - tilt / 2)}


# ------------------------------ ensemble (§13) ---------------------------- #
def ensemble_three_way(forecasts: Sequence[Sequence[float]]) -> np.ndarray:
    """Equal-weight LLM ensemble of three-way forecasts (§13)."""
    M = np.array([_renorm3(f) for f in forecasts], dtype=float)
    if M.size == 0:
        raise ValueError("no forecasts to ensemble")
    return _renorm3(M.mean(axis=0))


def ensemble_advance(p_advance: Sequence[float]) -> float:
    """Equal-weight ensemble of P(team A advances)."""
    a = np.asarray(p_advance, dtype=float)
    if a.size == 0:
        raise ValueError("no advance probabilities to ensemble")
    return float(np.clip(a.mean(), 0.0, 1.0))
