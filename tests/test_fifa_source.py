"""Tests for the FIFA ranking adapter (§11) — frozen-table loader, offline."""
import json

import pytest

from src.sources import fifa_ranking as F

TABLE = {
    "source": "FIFA", "official_date": "2026-06-11", "official": True,
    "ranking": {
        "France": {"rank": 1, "points": 1906.84},
        "Spain": {"rank": 3, "points": 1879.58},
        "USA": {"rank": 16, "points": 1648.0},
    },
}


def test_rank_and_points_lookup():
    src = F.FifaRankingSource(TABLE)
    assert src.get_rank("France") == 1
    assert src.get_points("Spain") == pytest.approx(1879.58)
    assert src.official is True and src.official_date == "2026-06-11"


def test_fifa_rank_fields():
    src = F.FifaRankingSource(TABLE)
    assert src.fifa_rank_fields("France", "Spain") == {"rankA": 1, "rankB": 3}


def test_alias_united_states_to_usa():
    src = F.FifaRankingSource(TABLE)
    assert src.get_rank("United States") == 16     # alias -> "USA"


def test_missing_team_raises():
    src = F.FifaRankingSource(TABLE)
    with pytest.raises(KeyError):
        src.fifa_rank_fields("France", "Atlantis")


def test_load_from_file(tmp_path):
    p = tmp_path / "fifa.json"
    p.write_text(json.dumps(TABLE))
    src = F.FifaRankingSource().load(str(p))
    assert src.get_rank("France") == 1


def test_sample_file_is_marked_unofficial():
    # The committed sample must NOT be mistaken for the official freeze.
    src = F.FifaRankingSource().load(
        "data/reference/fifa_ranking_live_2026-06-27_top10_SAMPLE.json")
    assert src.official is False
    assert src.get_rank("France") == 1
