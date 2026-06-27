"""
parsing.py — parse the five-key match output and the champion output (§20.6).

The protocol's pilot gate (§19) counts a response as "clean" only if it returns
EXACTLY the expected keys as integers — no percent signs, no extra text. In
analysis we still renormalize a slightly-off response to sum 100 (§20.6). These
two notions are separated here:

  is_clean_five_key(text)  -> bool   (strict; feeds the >95% parse-rate gate)
  parse_five_keys(text)    -> dict   (lenient extraction; raises ParseError if a
                                      required key is missing/non-integer)
"""
from __future__ import annotations

import re
from typing import Dict, List

from config import config as C


class ParseError(ValueError):
    """Raised when a response cannot yield all required integer keys."""


_KEY_LINE = re.compile(r"^\s*([A-Za-z_]+)\s*=\s*(-?\d+)\s*$")


def is_clean_five_key(text: str) -> bool:
    """Strict check for the pilot parse-rate metric (§19/§20.6):
    exactly five non-empty lines, each 'KEY=<integer>' in the expected order,
    no percent signs, no extra characters."""
    if "%" in text:
        return False
    lines = [ln for ln in text.strip().splitlines() if ln.strip() != ""]
    if len(lines) != len(C.FIVE_KEYS):
        return False
    for line, expected_key in zip(lines, C.FIVE_KEYS):
        m = _KEY_LINE.match(line)
        if not m or m.group(1) != expected_key:
            return False
    return True


def parse_five_keys(text: str) -> Dict[str, int]:
    """Lenient extraction: scan all 'KEY=int' lines, keep the five expected keys.
    Strips a trailing percent sign if present. Raises ParseError if any required
    key is missing or non-integer."""
    found: Dict[str, int] = {}
    cleaned = text.replace("%", "")
    for line in cleaned.splitlines():
        m = _KEY_LINE.match(line)
        if m and m.group(1) in C.FIVE_KEYS:
            found[m.group(1)] = int(m.group(2))
    missing = [k for k in C.FIVE_KEYS if k not in found]
    if missing:
        raise ParseError(f"missing/invalid keys: {missing}")
    return {k: found[k] for k in C.FIVE_KEYS}


def renormalize_five(parsed: Dict[str, int]) -> Dict[str, float]:
    """Renormalize to probabilities (§9/§20.6): three-way sums to 1, advance pair
    sums to 1. Returns floats in [0,1]."""
    out: Dict[str, float] = {}
    tw = [parsed[k] for k in C.THREE_WAY_KEYS]
    s_tw = sum(tw)
    if s_tw <= 0:
        raise ParseError("three-way probabilities sum to <= 0")
    for k in C.THREE_WAY_KEYS:
        out[k] = parsed[k] / s_tw
    adv = [parsed[k] for k in C.ADVANCE_KEYS]
    s_adv = sum(adv)
    if s_adv <= 0:
        raise ParseError("advance probabilities sum to <= 0")
    for k in C.ADVANCE_KEYS:
        out[k] = parsed[k] / s_adv
    return out


_CHAMP_LINE = re.compile(r"^\s*(.+?)\s*=\s*(-?\d+)\s*$")


def parse_champion(text: str) -> Dict[str, float]:
    """Parse the champion prompt output (§20.5): 'TEAM=probability' per line,
    renormalized to sum to 1 across all listed teams."""
    cleaned = text.replace("%", "")
    teams: Dict[str, int] = {}
    for line in cleaned.splitlines():
        m = _CHAMP_LINE.match(line)
        if m:
            teams[m.group(1).strip()] = int(m.group(2))
    if not teams:
        raise ParseError("no TEAM=probability lines found")
    total = sum(teams.values())
    if total <= 0:
        raise ParseError("champion probabilities sum to <= 0")
    return {t: v / total for t, v in teams.items()}
