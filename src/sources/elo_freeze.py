"""
elo_freeze.py — pre-kickoff Elo capture-and-freeze (§11/§12, ELO_FREEZE_PROBLEM.md).

eloratings.net serves only the CURRENT ratings snapshot (no point-in-time API).
To make a frozen pack's Elo both (a) provably pre-kickoff and (b) reproducible, we
do NOT just read the parsed numbers — we ARCHIVE THE RAW SOURCE BYTES at capture
time, with a UTC timestamp and a SHA-256 per file. The frozen value is then
re-derivable from the archive forever, and the hash proves the bytes are unchanged.

Live procedure (per match): at T_cap = kickoff - 3h, call capture_elo_snapshot()
to archive World.tsv + en.teams.tsv, then freeze_elo_for_match() to pull the two
teams' ratings + provenance into the pack. Never re-capture after kickoff.

No paid APIs — eloratings.net is a free public data source.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from src.sources.elo_eloratings import (
    WORLD_TSV, TEAMS_TSV, build_name_ratings, EloRatingsSource,
)

SNAPSHOT_FILES = ("World.tsv", "en.teams.tsv")
_SOURCE_URLS = {"World.tsv": WORLD_TSV, "en.teams.tsv": TEAMS_TSV}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _http_get_bytes(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "wc-llm-study/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (public data)
        return r.read()


@dataclass
class EloSnapshot:
    """An archived eloratings.net snapshot — the reproducibility unit for Elo."""
    capture_timestamp: str          # UTC ISO-8601, when the raw bytes were fetched
    snapshot_dir: str
    files: Dict[str, Dict]          # name -> {path, sha256, bytes}
    source_urls: Dict[str, str]

    def _read(self, name: str) -> str:
        with open(os.path.join(self.snapshot_dir, name), "r",
                  encoding="utf-8", errors="replace") as f:
            return f.read()

    def name_ratings(self) -> Dict[str, int]:
        """Re-derive name->rating from the ARCHIVED bytes (offline, reproducible)."""
        return build_name_ratings(self._read("World.tsv"), self._read("en.teams.tsv"))

    def verify(self) -> bool:
        """Re-hash each archived file and confirm it matches the recorded SHA-256."""
        for name, meta in self.files.items():
            with open(os.path.join(self.snapshot_dir, name), "rb") as f:
                if _sha256_bytes(f.read()) != meta["sha256"]:
                    return False
        return True

    def to_dict(self) -> Dict:
        return {
            "capture_timestamp": self.capture_timestamp,
            "source": "eloratings.net",
            "source_urls": self.source_urls,
            "files": self.files,
        }


def capture_elo_snapshot(snapshot_dir: str,
                         capture_timestamp: Optional[str] = None) -> EloSnapshot:
    """Fetch + archive the raw eloratings snapshot. `capture_timestamp` is the REAL
    fetch time (injectable for tests); defaults to UTC now. Writes the raw .tsv
    files + a snapshot.json manifest into `snapshot_dir`."""
    ts = capture_timestamp or _utc_now_iso()
    os.makedirs(snapshot_dir, exist_ok=True)
    files: Dict[str, Dict] = {}
    for name in SNAPSHOT_FILES:
        raw = _http_get_bytes(_SOURCE_URLS[name])
        path = os.path.join(snapshot_dir, name)
        with open(path, "wb") as f:
            f.write(raw)
        files[name] = {"path": path, "sha256": _sha256_bytes(raw), "bytes": len(raw)}
    snap = EloSnapshot(ts, snapshot_dir, files, dict(_SOURCE_URLS))
    with open(os.path.join(snapshot_dir, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snap.to_dict(), f, ensure_ascii=False, indent=2)
    return snap


def load_snapshot(snapshot_dir: str) -> EloSnapshot:
    """Load a previously-archived snapshot from its manifest (offline)."""
    with open(os.path.join(snapshot_dir, "snapshot.json"), "r", encoding="utf-8") as f:
        d = json.load(f)
    return EloSnapshot(d["capture_timestamp"], snapshot_dir, d["files"],
                       d.get("source_urls", dict(_SOURCE_URLS)))


def freeze_elo_for_match(snapshot: EloSnapshot, team_A: str, team_B: str) -> Dict:
    """Pull the two teams' Elo from the snapshot and attach full provenance.

    Returns {eloA, eloB, elo_diff, elo_provenance{...}} ready to merge into the
    frozen pack. The provenance ties the value to the archived snapshot + hash +
    capture timestamp, so the frozen Elo is reproducible and provably pre-kickoff."""
    src = EloRatingsSource(snapshot.name_ratings())
    fields = src.elo_fields(team_A, team_B)
    fields["elo_provenance"] = {
        "source": "eloratings.net",
        "capture_timestamp": snapshot.capture_timestamp,
        "source_urls": snapshot.source_urls,
        "snapshot_dir": snapshot.snapshot_dir,
        "world_tsv_sha256": snapshot.files["World.tsv"]["sha256"],
        "teams_tsv_sha256": snapshot.files["en.teams.tsv"]["sha256"],
    }
    return fields
