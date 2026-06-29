# Per-match knockout freeze — standing procedure (SOP)

The repeatable procedure for freezing one knockout match, **consistent with match 73
(South Africa vs Canada)**. Run it in the match's **kickoff−3h** window. Output is
committed **post-tag**; the frozen pre-registration tag `c5cde21` and the OSF
registration are never touched.

## Timing & leakage (non-negotiable)
- Capture at the **matched pre-kickoff timestamp** (target kickoff−3h). Use **one
  shared timestamp `T`** across the Elo snapshot, the market capture, and the pack
  freeze, so model and market describe the same information set.
- **Never capture after kickoff.** Record the actual `T`; if it isn't exactly −3h,
  that's fine as long as it is genuinely pre-kickoff.

## A/B convention
- **TEAM A = the first-named team in the fixture; TEAM B = the second** (match 73:
  A = South Africa, B = Canada). Market lines are aligned to A/B strictly by team name.

## Fields & sources (identical to match 73)
| Field | Source / method |
|---|---|
| World Football Elo + Elo diff | eloratings.net live `World.tsv` — archive raw bytes + SHA-256, re-derive offline (`src/sources/elo_freeze.py`). |
| FIFA ranking | **FIFA's own page** `inside.fifa.com/fifa-world-ranking/men`, live pre-kickoff, **verified on FIFA's own page** (third-party reprints NOT used). Via Chrome browser. |
| Squad market value (EUR m) | **Transfermarkt national-team page directly**, both teams. Via Chrome browser. |
| Recent form (last 10, W-D-L) + goals for/against | The verified last-10 table (`data/reference/last10/last10_<round>.json`), **penalties = draw** convention, taking the 10 most recent games **dated before this fixture** (leakage-checked). Source recorded as author-verified. |
| Rest days | Days from each team's most recent match (last-10 table) to this fixture's date. |
| Host nation at home | 2026 hosts = **USA / Canada / Mexico**; `yes` only if the team is a host, else `no`. |
| Venue / city | Official 2026 schedule. |

## Market benchmark (captured, withheld from the primary arm)
- **Pinnacle** de-vigged 1X2 → registered 3-way benchmark **and** the line injected
  into the **conditioning** arm.
- **Polymarket** per-match 3-way (EXPLORATORY, Design Note 001) + advancement
  (reach next round, registered) + outright/champion (registered).
- De-vig: **proportional** (LOCKED primary) + **odds-ratio** and **Shin** sensitivity.
- Archive raw JSON + SHA-256 + capture timestamp + per-market prices.

## Output artifacts (committed post-tag; NOT in the frozen tag)
- `data/packs/<match_id>.pack.{txt,json}` — rendered §20.2 pack + SHA-256 + `T`.
- `data/packs/<match_id>.sources.json` — per-field provenance.
- `data/packs/<match_id>.elo/` — raw Elo snapshot + hash.
- `data/markets/<match_id>.market.manifest.json` — raw + de-vigged benchmarks.
- Forecasts (when authorized) → `data/forecasts/_local/` (gitignored).

## Order of operations
1. Pull staged **form/goals/rest/host** for both teams from the verified last-10 table.
2. Browser: **FIFA ranks** (FIFA page) + **squad values** (Transfermarkt) + **venue**.
3. Programmatic capture at `T = now`: **Elo snapshot** + **market** (Pinnacle + Polymarket).
4. Build & freeze the pack; write sources + market manifest.
5. **Pause for PI review.** Run model forecasts (primary, and conditioning once
   authorized) only on the PI's explicit **go** — no model spend before that.

## Round note
The last-10 form table is **per-round**: it rolls forward, so each round uses a
refreshed table that includes the prior round's results (flag the PI to refresh at
each new round).
