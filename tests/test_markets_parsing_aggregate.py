"""Tests for de-vig (§13), output parsing (§20.6), and aggregation (§10)."""
import numpy as np
import pytest

from config import config as C
from src.markets import devig as DV
from src import parsing as P
from src import aggregate as A


# --------------------------- de-vig (§13) --------------------------------- #
def test_proportional_normalizes():
    raw = [0.55, 0.30, 0.25]          # booksum 1.10 (10% margin)
    out = DV.devig_proportional(raw)
    assert out.sum() == pytest.approx(1.0)
    assert out[0] == pytest.approx(0.55 / 1.10)


def test_all_methods_sum_to_one_and_order_preserved():
    odds = [1.80, 3.60, 4.50]         # decimal odds, a typical 1X2
    raw = DV.implied_from_decimal_odds(odds)
    for name in ("proportional", "odds_ratio", "shin"):
        out = DV.devig(raw, method=name)
        assert out.sum() == pytest.approx(1.0, abs=1e-9)
        assert np.all(out > 0)
        # favourite stays the favourite under every method
        assert np.argmax(out) == 0


def test_devig_no_margin_is_identity():
    raw = [0.5, 0.3, 0.2]             # already sums to 1
    for name in ("proportional", "odds_ratio", "shin"):
        out = DV.devig(raw, method=name)
        assert out == pytest.approx(np.array(raw), abs=1e-6)


def test_devig_primary_is_proportional():
    assert C.DEVIG_PRIMARY == "proportional"
    raw = [0.6, 0.3, 0.2]
    assert DV.devig(raw) == pytest.approx(DV.devig_proportional(raw))


def test_implied_rejects_bad_odds():
    with pytest.raises(ValueError):
        DV.implied_from_decimal_odds([1.0, 2.0])


# --------------------------- parsing (§20.6) ------------------------------ #
CLEAN = "A_WIN=45\nDRAW=28\nB_WIN=27\nADV_A=58\nADV_B=42"


def test_clean_five_key_true():
    assert P.is_clean_five_key(CLEAN) is True
    parsed = P.parse_five_keys(CLEAN)
    assert parsed == {"A_WIN": 45, "DRAW": 28, "B_WIN": 27, "ADV_A": 58, "ADV_B": 42}


def test_percent_sign_not_clean_but_still_parses():
    txt = "A_WIN=45%\nDRAW=28%\nB_WIN=27%\nADV_A=58%\nADV_B=42%"
    assert P.is_clean_five_key(txt) is False        # % => not clean for the gate
    parsed = P.parse_five_keys(txt)                 # but lenient parse strips %
    assert parsed["A_WIN"] == 45


def test_extra_text_not_clean_but_parses():
    txt = "Here is my forecast:\nA_WIN=40\nDRAW=30\nB_WIN=30\nADV_A=55\nADV_B=45\nGood luck!"
    assert P.is_clean_five_key(txt) is False
    assert P.parse_five_keys(txt)["DRAW"] == 30


def test_missing_key_raises():
    with pytest.raises(P.ParseError):
        P.parse_five_keys("A_WIN=40\nDRAW=30\nB_WIN=30\nADV_A=55")


def test_renormalize_handles_off_by_a_bit():
    parsed = {"A_WIN": 50, "DRAW": 30, "B_WIN": 25, "ADV_A": 60, "ADV_B": 45}  # sums 105 / 105
    r = P.renormalize_five(parsed)
    assert r["A_WIN"] + r["DRAW"] + r["B_WIN"] == pytest.approx(1.0)
    assert r["ADV_A"] + r["ADV_B"] == pytest.approx(1.0)


def test_parse_champion():
    txt = "Spain=18\nFrance=16\nBrazil=15\nEngland=12\nArgentina=14\nGermany=11\nNetherlands=14"
    champ = P.parse_champion(txt)
    assert sum(champ.values()) == pytest.approx(1.0)
    assert champ["Spain"] == pytest.approx(18 / 100)


# --------------------------- aggregation (§10) ---------------------------- #
def _mk(a, d, b, adv_a):
    p = P.renormalize_five({"A_WIN": a, "DRAW": d, "B_WIN": b,
                            "ADV_A": adv_a, "ADV_B": 100 - adv_a})
    return p


def test_median_aggregation_primary():
    samples = [_mk(40, 30, 30, 55), _mk(50, 25, 25, 60), _mk(45, 30, 25, 58)]
    agg = A.aggregate(samples, method="median")
    assert agg["A_WIN"] + agg["DRAW"] + agg["B_WIN"] == pytest.approx(1.0)
    assert agg["ADV_A"] + agg["ADV_B"] == pytest.approx(1.0)
    # median of A_WIN raw fractions [.40,.50,.45] -> .45 then renorm (sums already 1)
    assert agg["A_WIN"] == pytest.approx(0.45, abs=1e-9)


def test_trimmed_mean_drops_tails():
    # 10% trim of 20 samples drops 2 each side; an outlier should be removed.
    base = [_mk(45, 30, 25, 55) for _ in range(19)]
    outlier = _mk(99, 1, 0, 99)
    samples = base + [outlier]
    tm = A.aggregate(samples, method="trimmed_mean")
    md = A.aggregate(samples, method="median")
    # trimmed mean stays close to the bulk despite the outlier
    assert tm["A_WIN"] == pytest.approx(md["A_WIN"], abs=0.02)


def test_sensitivity_subsets():
    samples = [_mk(40 + i, 30, 30 - i, 50 + i) for i in range(20)]
    sens = A.sensitivity(samples, ns=(5, 10, 15, 20))
    assert set(sens.keys()) == {5, 10, 15, 20}
    for n, agg in sens.items():
        assert agg["A_WIN"] + agg["DRAW"] + agg["B_WIN"] == pytest.approx(1.0)
