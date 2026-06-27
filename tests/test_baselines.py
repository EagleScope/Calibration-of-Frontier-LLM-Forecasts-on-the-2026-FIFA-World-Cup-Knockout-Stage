"""Tests for the statistical reference baselines and ensemble (§13)."""
import numpy as np
import pytest

from src import baselines as B


# ------------------------------- Elo model -------------------------------- #
def test_elo_1x2_sums_to_one_and_symmetric():
    p = B.elo_1x2(0.0)
    assert p.sum() == pytest.approx(1.0)
    assert p[0] == pytest.approx(p[2])            # even match -> symmetric wins
    assert p[1] == pytest.approx(B.ELO_DRAW_MAX)  # peak draw mass when evenly matched
    assert 0.2 < p[1] < 0.35                       # football-plausible draw rate


def test_elo_1x2_monotonic_in_diff():
    favored = B.elo_1x2(300.0)
    even = B.elo_1x2(0.0)
    assert favored[0] > even[0]                    # bigger Elo edge -> more A-win
    assert favored[0] > favored[2]
    # mirror symmetry
    mirror = B.elo_1x2(-300.0)
    assert favored[0] == pytest.approx(mirror[2])
    assert favored[2] == pytest.approx(mirror[0])


# ---------------------------- trivial favourite --------------------------- #
def test_trivial_favorite_picks_higher_rated():
    assert np.argmax(B.trivial_favorite_1x2(50)) == 0
    assert np.argmax(B.trivial_favorite_1x2(-50)) == 2
    assert B.trivial_favorite_1x2(50).sum() == pytest.approx(1.0)
    # within locked bounds (no zero mass)
    assert np.all(B.trivial_favorite_1x2(50) >= 0.0)


# ----------------------------- Dixon-Coles -------------------------------- #
def test_dc_symmetric_when_equal_lambdas():
    p = B.dixon_coles_1x2(1.4, 1.4, rho=0.0)
    assert p.sum() == pytest.approx(1.0)
    assert p[0] == pytest.approx(p[2], abs=1e-9)   # equal strength -> P(Awin)=P(Bwin)


def test_dc_higher_lambda_more_wins():
    strong = B.dixon_coles_1x2(2.2, 1.0)
    assert strong[0] > strong[2]                    # A scores more -> A wins more
    assert strong.sum() == pytest.approx(1.0)


def test_dc_draw_mass_reasonable():
    p = B.dixon_coles_1x2(1.3, 1.3)
    assert 0.20 < p[1] < 0.35                        # football-plausible draw rate


def test_expected_goals_tilt():
    eg = B.expected_goals_from_pack(250.0)           # A favoured by 250 Elo
    assert eg["lambda_A"] > eg["lambda_B"]


# ------------------------------- ensemble --------------------------------- #
def test_ensemble_three_way_equal_weight():
    f = [[0.6, 0.2, 0.2], [0.4, 0.3, 0.3]]
    e = B.ensemble_three_way(f)
    assert e.sum() == pytest.approx(1.0)
    assert e[0] == pytest.approx(0.5)                # mean of 0.6 and 0.4
    assert e[1] == pytest.approx(0.25)


def test_ensemble_advance():
    assert B.ensemble_advance([0.6, 0.4, 0.5]) == pytest.approx(0.5)


def test_ensemble_empty_raises():
    with pytest.raises(ValueError):
        B.ensemble_three_way([])
