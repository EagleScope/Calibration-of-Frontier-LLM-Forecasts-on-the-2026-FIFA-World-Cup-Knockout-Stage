"""Tests for Elo capture-and-freeze (§11) — offline, using a fixture snapshot."""
import json

import pytest

from src.sources import elo_freeze as EF

WORLD_TSV = (
    "1\t1\tDE\t1916\t1\t2000\n"
    "2\t2\tEC\t1902\t1\t1880\n"
    "3\t3\tBR\t2009\t1\t2100\n"
)
TEAMS_TSV = (
    "DE\tGermany\n"
    "EC\tEcuador\n"
    "BR\tBrazil\n"
    "XX_loc\tin somewhere\n"
)


def _write_snapshot(d, ts="2026-06-25T17:00:00+00:00"):
    """Write a fixture snapshot dir as capture_elo_snapshot would, but offline."""
    files = {}
    for name, content in (("World.tsv", WORLD_TSV), ("en.teams.tsv", TEAMS_TSV)):
        raw = content.encode("utf-8")
        (d / name).write_bytes(raw)
        files[name] = {"path": str(d / name), "sha256": EF._sha256_bytes(raw), "bytes": len(raw)}
    manifest = {"capture_timestamp": ts, "source": "eloratings.net",
                "source_urls": EF._SOURCE_URLS, "files": files}
    (d / "snapshot.json").write_text(json.dumps(manifest))
    return ts


def test_snapshot_reproduces_ratings_from_archive(tmp_path):
    _write_snapshot(tmp_path)
    snap = EF.load_snapshot(str(tmp_path))
    nr = snap.name_ratings()
    assert nr["Germany"] == 1916 and nr["Ecuador"] == 1902


def test_freeze_for_match_value_and_provenance(tmp_path):
    ts = _write_snapshot(tmp_path)
    snap = EF.load_snapshot(str(tmp_path))
    out = EF.freeze_elo_for_match(snap, "Germany", "Ecuador")
    assert out["eloA"] == 1916 and out["eloB"] == 1902 and out["elo_diff"] == 14
    prov = out["elo_provenance"]
    assert prov["capture_timestamp"] == ts                      # provably pre-kickoff
    assert prov["source"] == "eloratings.net"
    assert len(prov["world_tsv_sha256"]) == 64                   # snapshot reference (hash)
    assert prov["snapshot_dir"] == str(tmp_path)


def test_verify_detects_tampering(tmp_path):
    _write_snapshot(tmp_path)
    snap = EF.load_snapshot(str(tmp_path))
    assert snap.verify() is True
    # Tamper with the archived raw bytes -> hash no longer matches.
    (tmp_path / "World.tsv").write_text(WORLD_TSV.replace("1916", "9999"))
    assert snap.verify() is False


def test_snapshot_hash_matches_recorded(tmp_path):
    _write_snapshot(tmp_path)
    snap = EF.load_snapshot(str(tmp_path))
    # Recorded hash equals a fresh hash of the archived file.
    raw = (tmp_path / "World.tsv").read_bytes()
    assert snap.files["World.tsv"]["sha256"] == EF._sha256_bytes(raw)
