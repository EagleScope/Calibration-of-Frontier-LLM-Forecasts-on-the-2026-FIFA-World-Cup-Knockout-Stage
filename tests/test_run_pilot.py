"""Tests for the run/aggregate grid (§18.3) and the pilot gate (§19), offline."""
import numpy as np
import pytest

from config import config as C
from src import run_aggregate as RA
from src import pilot as PI
from src.clients.fake import ConstantFakeClient

PACK = {
    "round": "Group A", "date": "2026-06-15", "venue": "Stadium", "venue_city": "City",
    "team_A": "A", "team_B": "B", "eloA": 2000, "eloB": 1900, "elo_diff": 100,
    "rankA": 5, "rankB": 12, "mvA": 800, "mvB": 600, "formA": "6-2-2", "formB": "5-3-2",
    "gfgaA": "14/7", "gfgaB": "11/8", "hostA": "no", "hostB": "no", "restA": 4, "restB": 3,
}


def _clean_response(i, level, temp):
    # Slightly vary samples around a stable center so median is well-defined.
    a = 45 + (i % 3) - 1
    d = 28
    b = 100 - a - d
    adv = 58 + (i % 3) - 1
    return f"A_WIN={a}\nDRAW={d}\nB_WIN={b}\nADV_A={adv}\nADV_B={100 - adv}"


def _bad_response(i, level, temp):
    return "no structured answer here"


def _all_clients(resp_fn):
    return {spec.name: ConstantFakeClient(spec, resp_fn) for spec in C.MODELS}


# ----------------------------- run/aggregate ------------------------------ #
def test_expected_calls_matches_protocol_scale():
    # §18: 280 calls/match at N=20 for the four-model set.
    assert RA.expected_calls_per_match(n=20) == 280
    assert RA.expected_calls_per_match(n=20) == C.CALLS_PER_MATCH


def test_run_match_grid_shape_and_aggregate():
    clients = _all_clients(_clean_response)
    cells = RA.run_match(clients, "M1", PACK,
                         market={"mktA": 45, "mktD": 28, "mktB": 27}, n=20)
    # 3 paired models x 2 levels x 2 arms = 12, + Gemini 1 level x 2 arms = 2 -> 14
    assert len(cells) == 14
    for cell in cells.values():
        assert cell.aggregate is not None
        assert cell.aggregate.n == 20
        tw = RA.three_way_vector(cell.aggregate)
        assert tw.sum() == pytest.approx(1.0)
        assert 0.0 <= RA.advance_prob_A(cell.aggregate) <= 1.0
        # aggregate also carries the per-key spread of the 20 samples
        assert set(cell.aggregate.sd) == set(C.FIVE_KEYS)
        assert all(v >= 0 for v in cell.aggregate.iqr.values())


def test_conditioning_skipped_without_market():
    clients = _all_clients(_clean_response)
    cells = RA.run_match(clients, "M1", PACK, market=None, n=5)
    assert all(arm != "conditioning" for (_, _, arm) in cells.keys())


def test_records_persisted_to_jsonl(tmp_path):
    from src.records import read_jsonl
    clients = {C.MODELS[0].name: ConstantFakeClient(C.MODELS[0], _clean_response)}
    path = tmp_path / "fc.jsonl"
    RA.run_match(clients, "M1", PACK, n=20, records_path=str(path))
    rows = read_jsonl(str(path))
    # one model x 2 levels x 1 arm (no market) x 20 = 40 records
    assert len(rows) == 40
    assert rows[0]["match_id"] == "M1"


# ----------------------------- pilot gate --------------------------------- #
def _pilot_matches():
    return [
        PI.PilotMatch("G1", PACK, result_three_way=[1, 0, 0], advanced=1),
        PI.PilotMatch("G2", PACK, result_three_way=[0, 1, 0], advanced=0),
    ]


def test_pilot_passes_with_clean_stable_forecasts():
    clients = _all_clients(_clean_response)
    res = PI.run_pilot(clients, _pilot_matches(), n=20)
    assert res.parse_rate == 1.0
    assert res.parse_gate_pass is True
    assert res.brier_stability <= C.PILOT_BRIER_STABILITY
    assert res.brier_gate_pass is True
    assert res.passed is True
    assert res.usd_per_match is not None and res.usd_per_match > 0   # estimate prices set
    assert res.tokens_per_match > 0


def test_pilot_fails_on_low_parse_rate():
    clients = _all_clients(_bad_response)
    res = PI.run_pilot(clients, _pilot_matches(), n=20)
    assert res.parse_rate == 0.0
    assert res.parse_gate_pass is False
    assert res.passed is False


def test_pilot_summary_renders():
    clients = _all_clients(_clean_response)
    res = PI.run_pilot(clients, _pilot_matches(), n=20)
    s = res.summary()
    assert "PILOT GATE" in s and "PASS" in s
