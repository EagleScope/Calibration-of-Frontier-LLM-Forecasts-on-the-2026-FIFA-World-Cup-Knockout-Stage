"""
scoring_frozen.py
=================================================================================
FROZEN SCORING SCRIPT — committed and timestamped at protocol lock (§14, §17).

This file implements the ENTIRE pre-registered scoring battery. It is frozen at
lock so that scoring cannot be tuned after results arrive — the credibility of
the study (§0, §17) rests on this file predating the tournament.

It runs end-to-end on synthetic forecasts + results (see `main()` /
`run_synthetic_demo`). It needs NO real data, NO API keys, and NO network.

>>> DO NOT MODIFY AFTER LOCK. <<<
Any change after the lock commit must be a NEW, separately-timestamped file with
a documented rationale; the registered analysis is whatever this file computed at
the lock timestamp.

Battery (all from METHODS_PROTOCOL_v1.md §14):
  Calibration (on binary advance / not-advance):
    - Expected Calibration Error (10 equal-width bins) + Maximum Calibration Error
    - Reliability diagram
    - Calibration slope & intercept (logistic recalibration)
    - Murphy decomposition of Brier (reliability, resolution, uncertainty)
  Probabilistic accuracy (on ordered three-way result):
    - Ranked Probability Score (RPS) — PRIMARY (outcomes are ordinal)
    - Brier score and logarithmic score alongside (preds clipped to [0.01,0.99])
  Skill vs each market (SEPARATELY, never pooled):
    - Ranked Probability Skill Score & Brier Skill Score
  Inference:
    - Diebold-Mariano with Harvey-Leybourne-Newbold small-sample correction
    - Bootstrap confidence intervals (10,000 resamples)
    - Wilson intervals for proportions
    - TOST equivalence at margin 0.01
=================================================================================
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy import optimize, stats

# Single source of truth for every locked parameter (§ constants).
from config import config as C

# Matplotlib only for the reliability diagram; Agg backend = no display needed.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# =============================================================================
# Proper scores (per-observation, vectorized)
# =============================================================================
def _as_prob_matrix(P: Sequence[Sequence[float]]) -> np.ndarray:
    """Coerce to (n,3) float array and renormalize each row to sum 1 (§9)."""
    P = np.asarray(P, dtype=float)
    if P.ndim != 2 or P.shape[1] != 3:
        raise ValueError("three-way probabilities must have shape (n, 3)")
    row = P.sum(axis=1, keepdims=True)
    if np.any(row <= 0):
        raise ValueError("each forecast row must have positive mass")
    return P / row


def rps_three_way(P: Sequence[Sequence[float]], O: Sequence[Sequence[float]]) -> np.ndarray:
    """Ranked Probability Score for ordered 3-way outcomes (A win, draw, B win).

    Normalized RPS in [0,1] (Epstein 1969; Constantinou & Fenton 2012):
        RPS = 1/(K-1) * sum_{i=1}^{K-1} (CDF_pred_i - CDF_obs_i)^2
    Lower is better. Returns one RPS per match.
    """
    P = _as_prob_matrix(P)
    O = _as_prob_matrix(O)
    cum_p = np.cumsum(P, axis=1)
    cum_o = np.cumsum(O, axis=1)
    # Only first K-1 cumulative terms contribute (last is 1 for both).
    return np.sum((cum_p[:, :-1] - cum_o[:, :-1]) ** 2, axis=1) / (P.shape[1] - 1)


def brier_multiclass(P: Sequence[Sequence[float]], O: Sequence[Sequence[float]]) -> np.ndarray:
    """Multiclass Brier (sum over classes), ignores ordering. Range [0,2]."""
    P = _as_prob_matrix(P)
    O = _as_prob_matrix(O)
    return np.sum((P - O) ** 2, axis=1)


def log_score(P: Sequence[Sequence[float]], O: Sequence[Sequence[float]]) -> np.ndarray:
    """Negative log score -ln(p_true); preds clipped to [0.01,0.99] then renormed (§14)."""
    P = _as_prob_matrix(P)
    O = _as_prob_matrix(O)
    lo, hi = C.PRED_BOUNDS
    Pc = np.clip(P, lo, hi)
    Pc = Pc / Pc.sum(axis=1, keepdims=True)
    p_true = np.sum(Pc * O, axis=1)
    return -np.log(p_true)


def brier_binary(p: Sequence[float], y: Sequence[int]) -> np.ndarray:
    """Binary Brier (p - y)^2 per observation (used for advance forecasts)."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    return (p - y) ** 2


# =============================================================================
# Calibration (binary advance / not-advance)
# =============================================================================
@dataclass
class BinStat:
    lo: float
    hi: float
    count: int
    confidence: float   # mean predicted prob in bin
    accuracy: float     # observed frequency in bin


def _equal_width_bins(p: np.ndarray, y: np.ndarray, n_bins: int) -> List[BinStat]:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: List[BinStat] = []
    # Right-closed final bin so p==1.0 lands in the last bin.
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    for b in range(n_bins):
        mask = idx == b
        cnt = int(mask.sum())
        conf = float(p[mask].mean()) if cnt else float("nan")
        acc = float(y[mask].mean()) if cnt else float("nan")
        bins.append(BinStat(float(edges[b]), float(edges[b + 1]), cnt, conf, acc))
    return bins


def ece_mce(p: Sequence[float], y: Sequence[int], n_bins: int = C.ECE_BINS) -> Dict:
    """Expected & Maximum Calibration Error over equal-width bins (§14)."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(p)
    bins = _equal_width_bins(p, y, n_bins)
    ece = 0.0
    mce = 0.0
    for bs in bins:
        if bs.count == 0:
            continue
        gap = abs(bs.accuracy - bs.confidence)
        ece += (bs.count / n) * gap
        mce = max(mce, gap)
    return {"ece": ece, "mce": mce, "n_bins": n_bins, "bins": bins}


def reliability_diagram(p: Sequence[float], y: Sequence[int], path: str,
                        n_bins: int = C.ECE_BINS, title: str = "Reliability") -> str:
    """Save a reliability diagram PNG; returns the path."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    bins = _equal_width_bins(p, y, n_bins)
    xs = [b.confidence for b in bins if b.count]
    ys = [b.accuracy for b in bins if b.count]
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], "--", color="gray", label="perfect")
    ax.plot(xs, ys, "o-", label="forecaster")
    ax.set_xlabel("Predicted probability (confidence)")
    ax.set_ylabel("Observed frequency (accuracy)")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def _logit(p: np.ndarray) -> np.ndarray:
    lo, hi = C.PRED_BOUNDS
    p = np.clip(p, lo, hi)
    return np.log(p / (1.0 - p))


def calibration_slope_intercept(p: Sequence[float], y: Sequence[int]) -> Dict:
    """Logistic recalibration (§14): fit  logit P(y=1) = intercept + slope*logit(p).

    Perfect calibration -> slope == 1, intercept == 0.
    Overconfidence -> slope < 1 (the H1 direction).

    Fit by minimizing the logistic negative log-likelihood with a numerically
    stable `logaddexp` objective (no sklearn/statsmodels dependency, no overflow).
    """
    y = np.asarray(y, dtype=float)
    x = _logit(np.asarray(p, dtype=float))
    X = np.column_stack([np.ones_like(x), x])   # columns: [intercept, slope]

    def nll(beta: np.ndarray) -> float:
        eta = X @ beta
        # log(1+exp(eta)) - y*eta, stable for large |eta| via logaddexp.
        return float(np.sum(np.logaddexp(0.0, eta) - y * eta))

    def grad(beta: np.ndarray) -> np.ndarray:
        eta = np.clip(X @ beta, -30.0, 30.0)
        mu = 1.0 / (1.0 + np.exp(-eta))
        return X.T @ (mu - y)

    # np.errstate guards a spurious "matmul" FP warning seen with numpy 2.x on
    # macOS Accelerate; the objective (logaddexp / clipped exp) has no real div0.
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        res = optimize.minimize(nll, np.zeros(2), jac=grad, method="L-BFGS-B")
    beta = res.x
    return {"intercept": float(beta[0]), "slope": float(beta[1])}


def murphy_decomposition(p: Sequence[float], y: Sequence[int],
                         n_bins: int = C.ECE_BINS) -> Dict:
    """Murphy (1973) decomposition of the binary Brier score (§14):
        Brier = Reliability - Resolution + Uncertainty
    Binned by predicted probability (decomposition depends on binning)."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(p)
    base = float(y.mean())
    bins = _equal_width_bins(p, y, n_bins)
    reliability = 0.0
    resolution = 0.0
    for bs in bins:
        if bs.count == 0:
            continue
        reliability += bs.count * (bs.confidence - bs.accuracy) ** 2
        resolution += bs.count * (bs.accuracy - base) ** 2
    reliability /= n
    resolution /= n
    uncertainty = base * (1.0 - base)
    brier = float(np.mean((p - y) ** 2))
    return {
        "reliability": reliability,        # lower is better (calibration)
        "resolution": resolution,          # higher is better (discrimination)
        "uncertainty": uncertainty,        # irreducible
        "brier": brier,
        "reconstructed_brier": reliability - resolution + uncertainty,
        "base_rate": base,
    }


# =============================================================================
# Skill scores vs each market — SEPARATE, never pooled (§13, §14)
# =============================================================================
def skill_score(score_model: Sequence[float], score_reference: Sequence[float]) -> float:
    """Generic skill score: 1 - mean(model)/mean(reference). >0 beats reference.

    Used for both RPSS (feed RPS arrays) and BSS (feed Brier arrays). The caller
    must NEVER pool the two market references (POOL_MARKETS is False)."""
    sm = float(np.mean(score_model))
    sr = float(np.mean(score_reference))
    if sr == 0:
        return float("nan")
    return 1.0 - sm / sr


# =============================================================================
# Inference
# =============================================================================
def diebold_mariano(loss1: Sequence[float], loss2: Sequence[float], h: int = 1) -> Dict:
    """Diebold-Mariano test with Harvey-Leybourne-Newbold small-sample correction.

    loss_i = per-match loss of forecaster i (e.g. RPS). Positive DM => forecaster 1
    worse than forecaster 2. p-value from t-distribution with (n-1) df (HLN, 1997).
    Mandatory at this sample size (§14)."""
    d = np.asarray(loss1, dtype=float) - np.asarray(loss2, dtype=float)
    n = len(d)
    if n < 2:
        raise ValueError("need >= 2 paired observations")
    dbar = float(d.mean())

    # Newey-West-style long-run variance up to lag h-1 (h=1 -> just gamma_0).
    def autocov(k: int) -> float:
        if k == 0:
            return float(np.mean((d - dbar) ** 2))
        return float(np.mean((d[k:] - dbar) * (d[:-k] - dbar)))

    var_d = autocov(0) + 2.0 * sum(autocov(k) for k in range(1, h))
    if var_d <= 0:
        return {"dm_stat": float("nan"), "hln_stat": float("nan"),
                "p_value": float("nan"), "df": n - 1, "mean_diff": dbar}

    dm = dbar / np.sqrt(var_d / n)
    # HLN correction factor.
    factor = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    hln = dm * factor
    p = 2.0 * stats.t.cdf(-abs(hln), df=n - 1)
    return {"dm_stat": float(dm), "hln_stat": float(hln),
            "p_value": float(p), "df": n - 1, "mean_diff": dbar}


def bootstrap_ci(data: Sequence, stat_fn: Callable[[np.ndarray], float],
                 n_resamples: int = C.BOOTSTRAP_RESAMPLES,
                 ci_level: float = C.CI_LEVEL,
                 seed: int = C.BOOTSTRAP_SEED) -> Dict:
    """Percentile bootstrap CI over matches (10,000 resamples, §14).

    `data` is indexed by match (1-D array, or a 2-D array with one row per match);
    `stat_fn` maps a resampled `data` to a scalar. Fixed seed -> reproducible CIs."""
    arr = np.asarray(data)
    n = arr.shape[0]
    rng = np.random.default_rng(seed)
    point = float(stat_fn(arr))
    boot = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        boot[i] = stat_fn(arr[idx])
    alpha = 1.0 - ci_level
    lo, hi = np.quantile(boot, [alpha / 2, 1 - alpha / 2])
    return {"point": point, "lo": float(lo), "hi": float(hi),
            "ci_level": ci_level, "n_resamples": n_resamples}


def wilson_interval(k: int, n: int, ci_level: float = C.CI_LEVEL) -> Dict:
    """Wilson score interval for a proportion (§14)."""
    if n == 0:
        return {"phat": float("nan"), "lo": float("nan"), "hi": float("nan")}
    z = stats.norm.ppf(1 - (1 - ci_level) / 2)
    phat = k / n
    denom = 1 + z**2 / n
    center = (phat + z**2 / (2 * n)) / denom
    half = (z * np.sqrt(phat * (1 - phat) / n + z**2 / (4 * n**2))) / denom
    return {"phat": phat, "lo": float(center - half), "hi": float(center + half),
            "ci_level": ci_level}


def tost_equivalence(diffs: Sequence[float], margin: float = C.EQUIVALENCE_MARGIN,
                     alpha: float = C.ALPHA) -> Dict:
    """Two One-Sided Tests for equivalence (Lakens 2017; §14).

    `diffs` = per-match score difference (e.g. RPS_model - RPS_market). Tests
    whether the mean difference lies within +/- `margin`. Equivalent if BOTH
    one-sided tests reject at `alpha`. Margin is FROZEN at 0.01 (§14)."""
    d = np.asarray(diffs, dtype=float)
    n = len(d)
    if n < 2:
        raise ValueError("need >= 2 observations for TOST")
    mean = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n))
    df = n - 1
    if se == 0:
        equiv = abs(mean) < margin
        return {"mean_diff": mean, "se": 0.0, "margin": margin,
                "p_lower": 0.0 if mean > -margin else 1.0,
                "p_upper": 0.0 if mean < margin else 1.0,
                "p_tost": 0.0 if equiv else 1.0, "equivalent": bool(equiv), "df": df}
    # H0_lower: mean <= -margin  (reject => mean > -margin)
    t_lower = (mean - (-margin)) / se
    p_lower = 1 - stats.t.cdf(t_lower, df)
    # H0_upper: mean >= +margin  (reject => mean < +margin)
    t_upper = (mean - margin) / se
    p_upper = stats.t.cdf(t_upper, df)
    p_tost = max(p_lower, p_upper)
    return {"mean_diff": mean, "se": se, "margin": margin,
            "p_lower": float(p_lower), "p_upper": float(p_upper),
            "p_tost": float(p_tost), "equivalent": bool(p_tost < alpha), "df": df}


# =============================================================================
# Forecaster-level runner
# =============================================================================
@dataclass
class Forecaster:
    """A forecaster's predictions over the same n matches."""
    name: str
    three_way: np.ndarray              # (n,3) ordered probs A/draw/B
    p_advance: np.ndarray              # (n,) P(team A advances)


@dataclass
class ScoreReport:
    name: str
    rps: float
    brier3: float
    logscore: float
    advance_brier: float
    calibration: Dict
    murphy: Dict
    per_match: Dict = field(default_factory=dict)  # arrays kept for DM/skill/TOST


def score_forecaster(fc: Forecaster, result_three_way: np.ndarray,
                     advanced: np.ndarray, reliability_path: Optional[str] = None) -> ScoreReport:
    """Compute the full per-forecaster battery on observed results."""
    rps = rps_three_way(fc.three_way, result_three_way)
    bs3 = brier_multiclass(fc.three_way, result_three_way)
    ls = log_score(fc.three_way, result_three_way)
    adv_bs = brier_binary(fc.p_advance, advanced)
    calib = {
        "ece_mce": ece_mce(fc.p_advance, advanced),
        "slope_intercept": calibration_slope_intercept(fc.p_advance, advanced),
    }
    if reliability_path:
        calib["reliability_diagram"] = reliability_diagram(
            fc.p_advance, advanced, reliability_path, title=f"Reliability — {fc.name}")
    murphy = murphy_decomposition(fc.p_advance, advanced)
    return ScoreReport(
        name=fc.name,
        rps=float(rps.mean()), brier3=float(bs3.mean()), logscore=float(ls.mean()),
        advance_brier=float(adv_bs.mean()),
        calibration=calib, murphy=murphy,
        per_match={"rps": rps, "brier3": bs3, "logscore": ls, "advance_brier": adv_bs},
    )


def skill_vs_markets(model: ScoreReport, markets: Dict[str, ScoreReport]) -> Dict:
    """RPSS & BSS of `model` vs EACH market separately (never pooled, §13/§14),
    each with a bootstrap CI and a TOST equivalence test at the frozen margin."""
    if C.POOL_MARKETS:  # guard — must stay False
        raise RuntimeError("POOL_MARKETS must be False: markets are scored separately")
    out: Dict[str, Dict] = {}
    for mname, mrep in markets.items():
        rps_m = model.per_match["rps"]
        rps_ref = mrep.per_match["rps"]
        bs_m = model.per_match["brier3"]
        bs_ref = mrep.per_match["brier3"]

        rpss = skill_score(rps_m, rps_ref)
        bss = skill_score(bs_m, bs_ref)

        # Bootstrap CI for RPSS over matches (resample matched pairs).
        pair = np.column_stack([rps_m, rps_ref])
        rpss_ci = bootstrap_ci(
            pair, lambda a: 1.0 - a[:, 0].mean() / a[:, 1].mean())

        dm = diebold_mariano(rps_m, rps_ref)             # model vs market on RPS
        tost = tost_equivalence(rps_m - rps_ref)         # equivalence at margin 0.01
        out[mname] = {
            "rpss": rpss, "bss": bss, "rpss_ci": rpss_ci,
            "dm_rps": dm, "tost_rps": tost,
        }
    return out


# =============================================================================
# Synthetic end-to-end demo (proves the frozen script runs before any real data)
# =============================================================================
def _make_synthetic(n_matches: int = 32, seed: int = 0):
    """Generate synthetic true probabilities, sampled outcomes, and three
    forecasters (a decent model, an overconfident model, and two 'markets')."""
    rng = np.random.default_rng(seed)
    # Latent true 3-way probs per match.
    raw = rng.dirichlet([3.0, 2.5, 3.0], size=n_matches)
    true3 = raw
    # Sample the realized ordered outcome.
    outcomes = np.array([rng.choice(3, p=true3[i]) for i in range(n_matches)])
    result3 = np.eye(3)[outcomes]
    # True advance prob for team A ~ P(A win) + half the draw mass (penalties ~50/50).
    p_adv_true = true3[:, 0] + 0.5 * true3[:, 1]
    advanced = (rng.random(n_matches) < p_adv_true).astype(int)

    def noisy(scale, sharpen):
        # sharpen>1 => overconfident (push probs toward extremes).
        p = true3 ** sharpen
        p = p / p.sum(axis=1, keepdims=True)
        p = p + rng.normal(0, scale, size=p.shape)
        p = np.clip(p, 1e-3, None)
        p = p / p.sum(axis=1, keepdims=True)
        adv = np.clip((p[:, 0] + 0.5 * p[:, 1]), 1e-3, 1 - 1e-3)
        return p, adv

    good_p, good_adv = noisy(0.03, 1.0)
    over_p, over_adv = noisy(0.03, 1.8)        # overconfident (H1 direction)
    poly_p, poly_adv = noisy(0.02, 1.0)        # "market" — slightly sharper/better
    pin_p, pin_adv = noisy(0.025, 1.0)
    return {
        "result3": result3, "advanced": advanced,
        "good": Forecaster("Good-LLM", good_p, good_adv),
        "over": Forecaster("Overconfident-LLM", over_p, over_adv),
        "polymarket": Forecaster("Polymarket", poly_p, poly_adv),
        "pinnacle": Forecaster("Pinnacle", pin_p, pin_adv),
    }


def run_synthetic_demo(out_dir: str = "data") -> Dict:
    syn = _make_synthetic(n_matches=32, seed=42)
    model = score_forecaster(syn["over"], syn["result3"], syn["advanced"],
                             reliability_path=f"{out_dir}/_demo_reliability.png")
    good = score_forecaster(syn["good"], syn["result3"], syn["advanced"])
    poly = score_forecaster(syn["polymarket"], syn["result3"], syn["advanced"])
    pin = score_forecaster(syn["pinnacle"], syn["result3"], syn["advanced"])

    markets = {"polymarket": poly, "pinnacle": pin}
    skill = skill_vs_markets(model, markets)

    # Bootstrap CI on the model's own RPS.
    rps_ci = bootstrap_ci(model.per_match["rps"], lambda a: a.mean())
    # DM: overconfident vs good LLM on RPS.
    dm_over_good = diebold_mariano(model.per_match["rps"], good.per_match["rps"])
    # Wilson interval on advance hit-rate.
    adv_hits = int(((syn["over"].p_advance >= 0.5).astype(int) == syn["advanced"]).sum())
    wilson = wilson_interval(adv_hits, len(syn["advanced"]))

    report = {
        "model": model, "markets": markets, "skill_vs_markets": skill,
        "rps_ci": rps_ci, "dm_over_vs_good": dm_over_good, "advance_hitrate_wilson": wilson,
    }
    _print_report(report)
    return report


def _print_report(r: Dict) -> None:
    m: ScoreReport = r["model"]
    line = "=" * 74
    print(line)
    print("FROZEN SCORING — synthetic end-to-end demo (no real data)")
    print(line)
    print(f"Forecaster under test: {m.name}")
    print(f"  RPS (primary)         : {m.rps:.4f}")
    print(f"  Brier (3-way)         : {m.brier3:.4f}")
    print(f"  Log score             : {m.logscore:.4f}")
    print(f"  Advance Brier         : {m.advance_brier:.4f}")
    ece = m.calibration["ece_mce"]
    si = m.calibration["slope_intercept"]
    print(f"  ECE / MCE             : {ece['ece']:.4f} / {ece['mce']:.4f}")
    print(f"  Calib slope / intercept: {si['slope']:.3f} / {si['intercept']:.3f}"
          f"   (slope<1 => overconfident, H1)")
    mu = m.murphy
    print(f"  Murphy: reliability={mu['reliability']:.4f} resolution={mu['resolution']:.4f} "
          f"uncertainty={mu['uncertainty']:.4f}")
    print(f"  RPS 95% bootstrap CI  : [{r['rps_ci']['lo']:.4f}, {r['rps_ci']['hi']:.4f}]")
    print("-" * 74)
    print("Skill vs each market (SEPARATE — never pooled):")
    for mk, s in r["skill_vs_markets"].items():
        ci = s["rpss_ci"]
        t = s["tost_rps"]
        print(f"  [{mk}] RPSS={s['rpss']:+.4f} CI[{ci['lo']:+.4f},{ci['hi']:+.4f}]  "
              f"BSS={s['bss']:+.4f}")
        print(f"        DM(HLN) stat={s['dm_rps']['hln_stat']:+.3f} p={s['dm_rps']['p_value']:.3f}  "
              f"TOST(±{t['margin']}) p={t['p_tost']:.3f} equivalent={t['equivalent']}")
    dm = r["dm_over_vs_good"]
    print("-" * 74)
    print(f"DM overconfident-vs-good (RPS): HLN={dm['hln_stat']:+.3f} p={dm['p_value']:.3f}")
    w = r["advance_hitrate_wilson"]
    print(f"Advance hit-rate Wilson 95% CI: phat={w['phat']:.3f} [{w['lo']:.3f}, {w['hi']:.3f}]")
    print(line)
    print("Frozen scoring battery ran end-to-end. (§14 complete.)")
    print(line)


if __name__ == "__main__":
    run_synthetic_demo(out_dir="data")
    sys.exit(0)
