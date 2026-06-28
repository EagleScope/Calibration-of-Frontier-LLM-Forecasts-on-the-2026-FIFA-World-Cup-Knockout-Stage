"""Offline tests for the raw market-capture core (§13). No network."""
import json

import pytest

from src.markets import capture as CAP


def test_archive_payload_writes_raw_with_hash(tmp_path):
    raw = b'{"home_team":"South Africa","away_team":"Canada"}'
    arch = CAP.archive_payload(str(tmp_path), "M73.pinnacle.raw.json", raw,
                               "2026-06-28T16:00:00+00:00")
    # raw bytes written verbatim
    assert (tmp_path / "M73.pinnacle.raw.json").read_bytes() == raw
    # sha256 matches a fresh hash, timestamp + size recorded
    assert arch["sha256"] == CAP._sha256_bytes(raw)
    assert arch["bytes"] == len(raw)
    assert arch["captured_at"] == "2026-06-28T16:00:00+00:00"


def test_match_event_by_team_names():
    events = [
        {"home_team": "Brazil", "away_team": "Japan"},
        {"home_team": "South Africa", "away_team": "Canada"},
    ]
    ev = CAP._match_event(events, "Canada", "South Africa")   # order-independent
    assert ev is not None and ev["home_team"] == "South Africa"
    assert CAP._match_event(events, "Spain", "Canada") is None


def test_devig_method_is_proportional():
    # The capture records the locked primary de-vig method.
    from config import config as C
    assert C.DEVIG_PRIMARY == "proportional"
