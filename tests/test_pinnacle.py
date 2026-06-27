"""Tests for the Pinnacle (the-odds-api) adapter (§13) — pure parsers, offline."""
import numpy as np
import pytest

from src.markets import pinnacle as PIN

# Fixture mirrors the-odds-api v4 h2h event shape.
EVENT = {
    "home_team": "Brazil", "away_team": "Mexico",
    "commence_time": "2026-06-28T16:00:00Z",
    "bookmakers": [
        {"key": "betfair", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Brazil", "price": 1.7}, {"name": "Mexico", "price": 5.0},
            {"name": "Draw", "price": 3.8}]}]},
        {"key": "pinnacle", "last_update": "2026-06-28T15:55:00Z",
         "markets": [{"key": "h2h", "outcomes": [
             {"name": "Brazil", "price": 1.80}, {"name": "Mexico", "price": 4.50},
             {"name": "Draw", "price": 3.60}]}]},
    ],
}


def test_parse_selects_pinnacle():
    p = PIN.parse_h2h(EVENT)
    assert p["home_team"] == "Brazil" and p["away_team"] == "Mexico"
    assert p["odds"] == {"home": 1.80, "draw": 3.60, "away": 4.50}
    assert p["last_update"] == "2026-06-28T15:55:00Z"   # came from pinnacle, not betfair


def test_parse_missing_bookmaker_returns_none():
    assert PIN.parse_h2h(EVENT, bookmaker_key="williamhill") is None


def test_devig_sums_to_one_and_favorite_highest():
    p = PIN.parse_h2h(EVENT)
    dv = PIN.devig_h2h(p)
    assert dv["home"] + dv["draw"] + dv["away"] == pytest.approx(1.0)
    assert dv["home"] > dv["away"]                       # Brazil favoured


def test_align_to_AB_by_name():
    p = PIN.parse_h2h(EVENT)
    dv = PIN.devig_h2h(p)
    # Pack labels Mexico as A, Brazil as B -> probs must follow the names, not home/away
    vec = PIN.align_to_AB(dv, p, team_A="Mexico", team_B="Brazil")
    assert vec.sum() == pytest.approx(1.0)
    assert vec[2] > vec[0]                                # B=Brazil (fav) > A=Mexico


def test_align_rejects_mismatched_teams():
    p = PIN.parse_h2h(EVENT)
    dv = PIN.devig_h2h(p)
    with pytest.raises(ValueError):
        PIN.align_to_AB(dv, p, team_A="Brazil", team_B="Argentina")


def test_snapshot_schema():
    snap = PIN.snapshot(EVENT, match_id="R32_BRA_MEX",
                        kickoff_timestamp="2026-06-28T16:00:00Z",
                        capture_timestamp="2026-06-28T15:55:00Z",
                        team_A="Brazil", team_B="Mexico")
    assert snap.source == "pinnacle" and snap.market_kind == "three_way"
    assert snap.devigged["A_WIN"] + snap.devigged["DRAW"] + snap.devigged["B_WIN"] == pytest.approx(1.0)
    assert snap.devig_method == "proportional"
