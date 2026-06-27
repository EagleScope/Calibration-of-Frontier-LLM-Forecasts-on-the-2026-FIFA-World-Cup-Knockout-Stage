"""
data_freeze.py — Module 1 in the §18 build order: freeze the standardized
information pack per match (§11, §12, §20.2) and write timestamped artifacts.

Freeze protocol (§11): pull every field once, timestamp it, freeze it, and send
the byte-identical file to all four models. Leakage control (§12): the frozen
file is immutable; a content hash is stored so any later edit is detectable.

This module implements the freeze/serialize CORE, which takes a dict of field
values (from a manual entry sheet or a source adapter) and writes:
  <match_id>.pack.txt   — the exact §20.2 rendered pack used in prompts
  <match_id>.pack.json  — machine-readable record (§21-style) with timestamp+hash

The per-source FETCH adapters (eloratings.net, Transfermarkt, FIFA, results DB)
are declared as an interface below; the concrete scrapers are pending the data-
source decisions (see PACK_DATA_SOURCES in config). The freeze core does not
depend on them, so it is fully testable now.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from config import config as C


# Required keys to render the §20.2 template (the .format placeholders).
PACK_TEMPLATE_KEYS = (
    "round", "date", "venue", "venue_city", "team_A", "team_B",
    "eloA", "eloB", "elo_diff", "rankA", "rankB", "mvA", "mvB",
    "formA", "formB", "gfgaA", "gfgaB", "hostA", "hostB", "restA", "restB",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def render_pack(fields: Dict) -> str:
    """Render the exact §20.2 pack text (single source: config template)."""
    missing = [k for k in PACK_TEMPLATE_KEYS if k not in fields]
    if missing:
        raise ValueError(f"pack fields missing: {missing}")
    return C.MATCH_PACK_TEMPLATE.format(**fields)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class FrozenPack:
    match_id: str
    fields: Dict
    pack_text: str
    freeze_timestamp: str
    content_sha256: str
    sources: Dict[str, str] = field(default_factory=lambda: dict(C.PACK_DATA_SOURCES))

    def to_dict(self) -> Dict:
        return {
            "match_id": self.match_id,
            "fields": self.fields,
            "pack_text": self.pack_text,
            "freeze_timestamp": self.freeze_timestamp,
            "content_sha256": self.content_sha256,
            "sources": self.sources,
            "protocol_version": C.PROTOCOL_VERSION,
        }


def freeze_pack(match_id: str, fields: Dict, out_dir: str = "data/packs",
                timestamp: Optional[str] = None) -> FrozenPack:
    """Render, hash, timestamp, and write the frozen pack (.txt + .json).

    `timestamp` is injectable for reproducible tests; defaults to UTC now.
    Refuses to overwrite an existing frozen pack (freeze is one-shot, §12)."""
    pack_text = render_pack(fields)
    ts = timestamp or _utc_now_iso()
    digest = _sha256(pack_text)
    fp = FrozenPack(match_id=match_id, fields=dict(fields), pack_text=pack_text,
                    freeze_timestamp=ts, content_sha256=digest)

    os.makedirs(out_dir, exist_ok=True)
    txt_path = os.path.join(out_dir, f"{match_id}.pack.txt")
    json_path = os.path.join(out_dir, f"{match_id}.pack.json")
    for p in (txt_path, json_path):
        if os.path.exists(p):
            raise FileExistsError(f"frozen pack already exists, refusing overwrite: {p}")
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(pack_text)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(fp.to_dict(), f, ensure_ascii=False, indent=2)
    return fp


def verify_frozen(json_path: str) -> bool:
    """Re-hash the stored pack text and confirm it matches the frozen hash (§12)."""
    with open(json_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    return _sha256(d["pack_text"]) == d["content_sha256"]


# --------------------------------------------------------------------------- #
# Source-adapter interface (concrete scrapers PENDING data-source decisions).  #
# --------------------------------------------------------------------------- #
class FieldSource:
    """Interface for a per-field data source (§11). Concrete implementations for
    eloratings.net / FIFA / Transfermarkt / results DB are pending the data-source
    decisions; the freeze core above works with any dict provider (incl. manual)."""

    name = "abstract"

    def fetch_match_fields(self, match_id: str) -> Dict:  # pragma: no cover
        raise NotImplementedError(
            "Concrete source adapter pending data-source decision; "
            "supply pack fields manually or via a confirmed adapter.")
