"""Tests for the eloratings.net Elo adapter (§11) — pure parsers, offline."""
import pytest

from src.sources import elo_eloratings as E

# Fixtures mirror the real TSV column layout verified live on 2026-06-27.
WORLD_TSV = (
    "1\t1\tES\t2144\t1\t2189\t7\t1946\n"
    "1\t1\tAR\t2144\t1\t2172\t5\t1988\n"
    "3\t3\tFR\t2123\t1\t2135\t16\t1795\n"
    "\t\t\t\n"                       # junk line ignored
    "10\t10\tUS\t1781\t1\t1900\n"
)
TEAMS_TSV = (
    "ES\tSpain\n"
    "AR\tArgentina\n"
    "FR\tFrance\n"
    "US\tUnited States\tUSA\n"
    "BS_loc\tin the Bahamas\n"        # location row skipped
)


def test_parse_world_tsv_picks_rating_column():
    r = E.parse_world_tsv(WORLD_TSV)
    assert r == {"ES": 2144, "AR": 2144, "FR": 2123, "US": 1781}


def test_parse_teams_tsv_canonical_name_and_skips_loc():
    t = E.parse_teams_tsv(TEAMS_TSV)
    assert t["ES"] == "Spain" and t["US"] == "United States"
    assert all("_loc" not in code for code in t)


def test_build_name_ratings_join():
    nr = E.build_name_ratings(WORLD_TSV, TEAMS_TSV)
    assert nr["Spain"] == 2144 and nr["France"] == 2123


def test_elo_fields_and_diff():
    src = E.EloRatingsSource(E.build_name_ratings(WORLD_TSV, TEAMS_TSV))
    f = src.elo_fields("Spain", "France")
    assert f == {"eloA": 2144, "eloB": 2123, "elo_diff": 21}


def test_alias_resolves_usa():
    src = E.EloRatingsSource(E.build_name_ratings(WORLD_TSV, TEAMS_TSV))
    assert src.get_rating("USA") == 1781        # alias -> "United States"


def test_unknown_team_raises():
    src = E.EloRatingsSource(E.build_name_ratings(WORLD_TSV, TEAMS_TSV))
    with pytest.raises(KeyError):
        src.elo_fields("Spain", "Atlantis")
