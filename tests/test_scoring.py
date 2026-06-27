"""
Correctness tests for the FROZEN scoring script (§14).

These check each metric against hand-computed / analytic values — not just that
the code runs. If any of these change, the frozen scoring has changed.
"""
import numpy as np
import pytest

from config import config as C
from src import scoring_frozen as S


# --------------------------------------------------------------------------- #
# RPS (ordered three-way)                                                      #
# --------------------------------------------------------------------------- #
def test_rps_perfect_is_zero():
    P = [[1, 0, 0]]
    O = [[1, 0, 0]]
    assert S.rps_three_way(P, O)[0] == pytest.approx(0.0)


def test_rps_worst_case_is_one():
    # Predict B win, A win happens -> maximal ordinal distance.
    P = [[0, 0, 1]]
    O = [[1, 0, 0]]
    assert S.rps_three_way(P, O)[0] == pytest.approx(1.0)


def test_rps_known_value():
    # P=[.5,.5,0], A wins -> cum (.5,1) vs (1,1): (.25 + 0)/2 = .125
    P = [[0.5, 0.5, 0.0]]
    O = [[1, 0, 0]]
    assert S.rps_three_way(P, O)[0] == pytest.approx(0.125)


def test_rps_rewards_ordering_over_brier():
    # Draw happens. A near-miss (predict A) should beat a far-miss only in RPS.
    O = [[0, 1, 0]]
    near = S.rps_three_way([[0.6, 0.4, 0.0]], O)[0]
    far = S.rps_three_way([[0.0, 0.4, 0.6]], O)[0]
    # symmetric around the draw -> equal here; check ordering sensitivity instead:
    assert near == pytest.approx(far)
    # but predicting the wrong END is worse than hedging the middle:
    end = S.rps_three_way([[1.0, 0.0, 0.0]], O)[0]
    mid = S.rps_three_way([[0.0, 1.0, 0.0]], O)[0]
    assert mid < end


# --------------------------------------------------------------------------- #
# Brier (multiclass) and log score                                            #
# --------------------------------------------------------------------------- #
def test_brier_multiclass_values():
    assert S.brier_multiclass([[1, 0, 0]], [[1, 0, 0]])[0] == pytest.approx(0.0)
    assert S.brier_multiclass([[0, 0, 1]], [[1, 0, 0]])[0] == pytest.approx(2.0)
    assert S.brier_multiclass([[0.5, 0.5, 0]], [[1, 0, 0]])[0] == pytest.approx(0.5)


def test_log_score_value_and_finiteness():
    # p_true = 0.5 -> -ln(0.5)
    assert S.log_score([[0.5, 0.3, 0.2]], [[1, 0, 0]])[0] == pytest.approx(-np.log(0.5))
    # A confident-but-wrong forecast stays finite due to [0.01,0.99] clipping.
    val = S.log_score([[1.0, 0.0, 0.0]], [[0, 0, 1]])[0]
    assert np.isfinite(val)


def test_prob_matrix_renormalizes():
    # Rows not summing to 1 get renormalized (§9).
    out = S.brier_multiclass([[2, 0, 0]], [[1, 0, 0]])[0]
    assert out == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Calibration: ECE / MCE                                                       #
# --------------------------------------------------------------------------- #
def test_ece_perfectly_calibrated_is_zero():
    p = np.full(10, 0.5)
    y = np.array([1, 0] * 5)        # 50% in the 0.5 bin
    r = S.ece_mce(p, y)
    assert r["ece"] == pytest.approx(0.0)
    assert r["mce"] == pytest.approx(0.0)


def test_ece_fully_miscalibrated():
    p = np.full(10, 0.9)            # all in [0.9,1.0] bin
    y = np.zeros(10, dtype=int)     # never happens
    r = S.ece_mce(p, y)
    assert r["ece"] == pytest.approx(0.9)
    assert r["mce"] == pytest.approx(0.9)


# --------------------------------------------------------------------------- #
# Calibration slope / intercept (logistic recalibration)                      #
# --------------------------------------------------------------------------- #
def test_calibration_slope_recovers_one_when_calibrated():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.05, 0.95, size=20000)
    y = (rng.random(20000) < p).astype(int)      # perfectly calibrated
    r = S.calibration_slope_intercept(p, y)
    assert r["slope"] == pytest.approx(1.0, abs=0.12)
    assert r["intercept"] == pytest.approx(0.0, abs=0.12)


def test_calibration_slope_below_one_when_overconfident():
    rng = np.random.default_rng(1)
    true_p = rng.uniform(0.05, 0.95, size=20000)
    y = (rng.random(20000) < true_p).astype(int)
    # Report sharpened (overconfident) probabilities.
    logit = np.log(true_p / (1 - true_p))
    over_p = 1 / (1 + np.exp(-1.8 * logit))
    r = S.calibration_slope_intercept(over_p, y)
    assert r["slope"] < 1.0                       # H1 direction


# --------------------------------------------------------------------------- #
# Murphy decomposition                                                         #
# --------------------------------------------------------------------------- #
def test_murphy_uncertainty_and_reconstruction():
    rng = np.random.default_rng(2)
    p = rng.uniform(0, 1, size=500)
    y = (rng.random(500) < p).astype(int)
    r = S.murphy_decomposition(p, y)
    base = y.mean()
    assert r["uncertainty"] == pytest.approx(base * (1 - base))
    # Brier ≈ reliability - resolution + uncertainty (binned approximation).
    assert r["reconstructed_brier"] == pytest.approx(r["brier"], abs=0.02)


# --------------------------------------------------------------------------- #
# Skill scores                                                                 #
# --------------------------------------------------------------------------- #
def test_skill_score_zero_when_equal_and_positive_when_better():
    ref = np.array([0.2, 0.3, 0.25, 0.4])
    assert S.skill_score(ref, ref) == pytest.approx(0.0)
    better = ref * 0.5             # lower loss -> positive skill
    assert S.skill_score(better, ref) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# Diebold-Mariano + HLN                                                        #
# --------------------------------------------------------------------------- #
def test_dm_antisymmetric():
    rng = np.random.default_rng(3)
    a = rng.random(30)
    b = rng.random(30)
    d1 = S.diebold_mariano(a, b)
    d2 = S.diebold_mariano(b, a)
    assert d1["hln_stat"] == pytest.approx(-d2["hln_stat"])
    assert d1["p_value"] == pytest.approx(d2["p_value"])


def test_dm_hln_correction_factor_h1():
    rng = np.random.default_rng(4)
    a = rng.random(25)
    b = a + rng.normal(0, 0.1, 25)
    r = S.diebold_mariano(a, b, h=1)
    n = 25
    expected_ratio = np.sqrt((n - 1) / n)         # HLN factor at h=1
    assert r["hln_stat"] / r["dm_stat"] == pytest.approx(expected_ratio)
    assert r["df"] == n - 1


# --------------------------------------------------------------------------- #
# Bootstrap CI                                                                 #
# --------------------------------------------------------------------------- #
def test_bootstrap_reproducible_and_brackets_point():
    data = np.array([0.1, 0.2, 0.15, 0.3, 0.25, 0.05, 0.4, 0.35])
    r1 = S.bootstrap_ci(data, lambda a: a.mean(), n_resamples=2000)
    r2 = S.bootstrap_ci(data, lambda a: a.mean(), n_resamples=2000)
    assert r1 == r2                               # fixed seed -> identical
    assert r1["point"] == pytest.approx(data.mean())
    assert r1["lo"] <= r1["point"] <= r1["hi"]


# --------------------------------------------------------------------------- #
# Wilson interval                                                              #
# --------------------------------------------------------------------------- #
def test_wilson_known_value():
    r = S.wilson_interval(5, 10)
    assert r["phat"] == pytest.approx(0.5)
    assert r["lo"] == pytest.approx(0.2366, abs=1e-3)
    assert r["hi"] == pytest.approx(0.7634, abs=1e-3)


# --------------------------------------------------------------------------- #
# TOST equivalence                                                            #
# --------------------------------------------------------------------------- #
def test_tost_equivalent_when_diffs_tiny():
    rng = np.random.default_rng(5)
    diffs = rng.normal(0.0, 0.002, size=60)       # well within ±0.01
    r = S.tost_equivalence(diffs)
    assert r["margin"] == 0.01
    assert r["equivalent"] is True


def test_tost_not_equivalent_when_diffs_large():
    rng = np.random.default_rng(6)
    diffs = rng.normal(0.5, 0.05, size=60)        # far outside ±0.01
    r = S.tost_equivalence(diffs)
    assert r["equivalent"] is False


# --------------------------------------------------------------------------- #
# Markets scored separately, never pooled                                     #
# --------------------------------------------------------------------------- #
def test_skill_vs_markets_keeps_markets_separate():
    syn = S._make_synthetic(n_matches=32, seed=7)
    model = S.score_forecaster(syn["over"], syn["result3"], syn["advanced"])
    poly = S.score_forecaster(syn["polymarket"], syn["result3"], syn["advanced"])
    pin = S.score_forecaster(syn["pinnacle"], syn["result3"], syn["advanced"])
    out = S.skill_vs_markets(model, {"polymarket": poly, "pinnacle": pin})
    assert set(out.keys()) == {"polymarket", "pinnacle"}      # separate entries
    # Each market has its own RPSS/BSS/DM/TOST — not a pooled number.
    for mk in ("polymarket", "pinnacle"):
        assert "rpss" in out[mk] and "tost_rps" in out[mk]
    assert C.POOL_MARKETS is False


def test_full_demo_runs():
    rep = S.run_synthetic_demo(out_dir="data")
    assert np.isfinite(rep["model"].rps)
    assert 0 <= rep["model"].rps <= 1
