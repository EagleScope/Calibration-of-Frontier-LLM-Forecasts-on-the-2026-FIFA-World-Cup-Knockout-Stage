"""Tests for data-freeze (§11/§12), record schemas (§21), Polymarket parser (§13)."""
import json
import os

import pytest

from config import config as C
from src import data_freeze as F
from src import records as R
from src.markets import polymarket as PM


SAMPLE_FIELDS = {
    "round": "Round of 32", "date": "2026-06-28", "venue": "MetLife Stadium",
    "venue_city": "East Rutherford", "team_A": "Brazil", "team_B": "Mexico",
    "eloA": 2042, "eloB": 1898, "elo_diff": 144, "rankA": 4, "rankB": 13,
    "mvA": 1100, "mvB": 410, "formA": "7-2-1", "formB": "5-3-2",
    "gfgaA": "18/6", "gfgaB": "12/9", "hostA": "no", "hostB": "yes",
    "restA": 4, "restB": 3,
}


# ----------------------------- data freeze -------------------------------- #
def test_render_pack_matches_template():
    text = F.render_pack(SAMPLE_FIELDS)
    assert "MATCH: Round of 32, 2026-06-28, MetLife Stadium, East Rutherford" in text
    assert "Elo difference (A - B):       144" in text
    assert text == C.MATCH_PACK_TEMPLATE.format(**SAMPLE_FIELDS)


def test_render_pack_missing_field_raises():
    bad = dict(SAMPLE_FIELDS)
    del bad["eloA"]
    with pytest.raises(ValueError):
        F.render_pack(bad)


def test_freeze_writes_files_with_hash_and_timestamp(tmp_path):
    fp = F.freeze_pack("R32_BRA_MEX", SAMPLE_FIELDS, out_dir=str(tmp_path),
                       timestamp="2026-06-27T12:00:00+00:00")
    txt = tmp_path / "R32_BRA_MEX.pack.txt"
    js = tmp_path / "R32_BRA_MEX.pack.json"
    assert txt.exists() and js.exists()
    assert fp.freeze_timestamp == "2026-06-27T12:00:00+00:00"
    assert len(fp.content_sha256) == 64
    assert F.verify_frozen(str(js)) is True


def test_freeze_refuses_overwrite(tmp_path):
    F.freeze_pack("M1", SAMPLE_FIELDS, out_dir=str(tmp_path), timestamp="t")
    with pytest.raises(FileExistsError):
        F.freeze_pack("M1", SAMPLE_FIELDS, out_dir=str(tmp_path), timestamp="t")


def test_verify_detects_tampering(tmp_path):
    F.freeze_pack("M2", SAMPLE_FIELDS, out_dir=str(tmp_path), timestamp="t")
    js = tmp_path / "M2.pack.json"
    d = json.loads(js.read_text())
    d["pack_text"] = d["pack_text"].replace("Brazil", "Argentina")  # tamper
    js.write_text(json.dumps(d))
    assert F.verify_frozen(str(js)) is False


# ----------------------------- records ------------------------------------ #
def test_records_roundtrip_jsonl(tmp_path):
    rec = R.ForecastRecord(
        model_name="Claude Opus 4.8", model_id="claude-opus-4-8", provider="anthropic",
        api_version="2023-06-01", parameters={"reasoning": "high"}, reasoning_level="high",
        arm="primary", match_id="M1", sample_index=0, timestamp="t",
        raw_response="A_WIN=40\nDRAW=30\nB_WIN=30\nADV_A=55\nADV_B=45",
        parsed={"A_WIN": 40, "DRAW": 30, "B_WIN": 30, "ADV_A": 55, "ADV_B": 45},
        parse_clean=True, usage=R.TokenUsage(input_tokens=120, output_tokens=10),
    )
    path = tmp_path / "fc.jsonl"
    R.append_jsonl(str(path), rec.to_dict())
    R.append_jsonl(str(path), rec.to_dict())
    rows = R.read_jsonl(str(path))
    assert len(rows) == 2
    assert rows[0]["model_id"] == "claude-opus-4-8"
    assert rows[0]["usage"]["input_tokens"] == 120


def test_market_snapshot_schema():
    snap = R.MarketSnapshot(
        source="polymarket", match_id="M1", raw={"Brazil": 0.62},
        devig_method="proportional", devigged={"Brazil": 0.6, "Mexico": 0.4},
        capture_timestamp="t0", kickoff_timestamp="t1", market_kind="advancement",
    )
    d = snap.to_dict()
    assert d["source"] == "polymarket" and d["market_kind"] == "advancement"


# ----------------------------- polymarket parser -------------------------- #
# Fixture mirrors the live world-cup-winner event shape verified on 2026-06-27.
CHAMP_EVENT = {
    "title": "World Cup Winner",
    "markets": [
        {"question": "Will Spain win the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.1175", "0.8825"]},
        {"question": "Will France win the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.2295", "0.7705"]},
        {"question": "Will New Zealand win the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0", "1"]},          # dropped (0)
        {"question": "Will Team AM win the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": None},                # dropped
    ],
}


def test_parse_champion_event_extracts_yes_prices():
    raw = PM.parse_champion_event(CHAMP_EVENT)
    assert raw == {"Spain": pytest.approx(0.1175), "France": pytest.approx(0.2295)}


def test_parse_handles_json_string_arrays():
    # Gamma sometimes returns outcomes/outcomePrices as JSON strings.
    ev = {"markets": [{"question": "Will Brazil win the 2026 FIFA World Cup?",
                       "outcomes": "[\"Yes\", \"No\"]",
                       "outcomePrices": "[\"0.18\", \"0.82\"]"}]}
    raw = PM.parse_champion_event(ev)
    assert raw["Brazil"] == pytest.approx(0.18)


def test_devig_champion_sums_to_one():
    raw = PM.parse_champion_event(CHAMP_EVENT)
    probs = PM.devig_champion(raw, method="proportional")
    assert sum(probs.values()) == pytest.approx(1.0)
    # France favoured over Spain, ordering preserved
    assert probs["France"] > probs["Spain"]
