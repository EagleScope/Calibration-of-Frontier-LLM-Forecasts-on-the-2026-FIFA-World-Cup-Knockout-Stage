# Amendment 001 — Add the Polymarket per-match 3-way as a registered benchmark

- **Date:** 2026-06-28
- **Amends:** `METHODS_PROTOCOL_v1.md` §13 (Baselines), as frozen in the pre-registration
  `pre-registration-v1.0` (commit `c5cde21`), OSF-registered 2026-06-28.
- **Status of the original registration:** UNCHANGED. The frozen tag and its OSF
  registration are not modified, rewritten, or replaced. This amendment is a
  separate, separately-timestamped document; the original locked method stands as
  registered. (OSF "update" attached to the existing registration by the author.)
- **Timing relative to data:** filed **before any knockout match has resolved.**
  The first Round-of-32 match (match 73, South Africa vs Canada) kicks off
  2026-06-28 19:00 UTC; this amendment is based only on the pre-kickoff market
  **structure** captured at 16:51 UTC — no match result exists yet.

## The change

§13 registered two market baselines with this split:
- **Polymarket** → benchmarks **advancement** and **outright winner**.
- **Pinnacle closing line** → benchmarks the **90-minute three-way (1X2)** result.

§13 also recorded an explicit *"verify during build"* item: *"Polymarket's actual
2026 knockout market structure (likely advancement, not a three-way with a draw).
If Polymarket does not price the three-way, Pinnacle is the sole three-way
benchmark…"*

**This amendment adds** the **Polymarket per-match three-way (1X2)** —
`A_WIN / DRAW / B_WIN` — as a registered market benchmark, **alongside** (not
replacing) the already-registered Polymarket advancement and outright, and
alongside the Pinnacle three-way. The two three-way benchmarks (Pinnacle and
Polymarket) are reported **separately, never pooled**, exactly as §13 already
requires for market baselines.

Nothing else in §13 changes:
- **De-vig method unchanged:** proportional (LOCKED primary); odds-ratio and Shin
  as sensitivity.
- **Capture timing unchanged:** the matched pre-kickoff timestamp (kickoff − 3h),
  with the short pre-resolution exclusion.
- **Scoring battery unchanged (§14):** skill scores (RPSS/BSS) are computed vs each
  market separately; this adds one more market series to that existing, frozen
  comparison. No model-side method, prompt, pack, aggregation, or calibration
  metric is affected.

## Rationale (recorded)

The §13 assumption that "Polymarket prices advancement, not a 3-way with a draw"
proved **factually wrong**. At the match-73 matched pre-kickoff capture, Polymarket
posts a **liquid per-match three-way** — three binary Yes/No legs (team-A win /
draw / team-B win) — with ~**$12.9M** volume on the favourite leg and a booksum of
0.995 (≈0.5% under-round). By contrast the Polymarket **advancement** market
(*Nation to Reach Round of 16*) is **thin** (~**$28k** liquidity). It would be a
loss of information to benchmark the 3-way only against Pinnacle while ignoring a
deeper, more liquid Polymarket 3-way that directly grades the same outcome the
models forecast.

This is a **market-structure fact**, observed **before any knockout match
resolved**, and is therefore **independent of any result** — it cannot be a
result-dependent (post-hoc / HARKing) choice. It resolves the pre-registered
"verify during build" item in the direction the data showed.

## What gets captured (per match, from this match onward)

For each knockout fixture, at the matched pre-kickoff timestamp:
1. **Polymarket per-match 3-way** → de-vigged `A_WIN / DRAW / B_WIN` (NEW, this amendment).
2. **Polymarket advancement** → de-vigged `ADV_A / ADV_B` (already registered).
3. **Polymarket outright / champion** (already registered).
4. **Pinnacle closing line** 3-way (already registered).

Each line stores the raw JSON + SHA-256 + capture timestamp + per-market prices,
de-vigged under the locked proportional method plus the odds-ratio and Shin
sensitivity methods.

## Match 73 (South Africa = A, Canada = B), parsed offline from the 16:51Z archive

Leakage-free (parsed from the pre-kickoff raw search; no value re-fetched), primary
(proportional) de-vig:

| Benchmark | A_WIN | DRAW | B_WIN | ADV_A | ADV_B |
|---|---|---|---|---|---|
| Polymarket per-match 3-way | 0.166 | 0.276 | 0.558 | — | — |
| Polymarket advancement (reach R16) | — | — | — | 0.247 | 0.753 |

Recorded in `data/markets/R32_73_ZAF_CAN.market.manifest.json`.

## Implementation

Parsers added in `src/markets/polymarket.py` (`parse_match_3way`,
`parse_advancement_pair`, `build_match_benchmark`) and wired into
`src/markets/capture.py`; offline tests in `tests/test_polymarket_match.py`.
Committed **after** the pre-registration tag (per the §17 two-tier timestamp
policy); the tag itself is never rewritten.
