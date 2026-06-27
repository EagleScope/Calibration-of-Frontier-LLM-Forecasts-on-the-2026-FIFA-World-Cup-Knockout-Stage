# Elo freeze & leakage — design note (pipeline gap surfaced by the pilot)

**Status: proposal, not implemented.** The pilot ran on a *finished* match, where
eloratings.net's current rating already reflects the result → Elo leakage. For the
*prospective* live study this specific leakage does not occur, but it forces a
precise capture-and-freeze procedure for Elo, specified below.

## What eloratings.net actually serves (verified 2026-06-27)
- `World.tsv` (and `2026.tsv`, etc.) are **current ratings snapshots** — the live
  rating for every team *as of now*. They update after each match.
- The extra columns are ratings at a few **fixed** reference points (≈1 month / 1
  year / longer ago) and rank deltas — **not** an arbitrary-date lookup.
- There is **no documented stable API or file for "national-team Elo as of date X"**,
  and **no match-result log** to recompute from. `2026.tsv` is a ratings table, not
  results. (ClubElo's `api.clubelo.com` gives point-in-time Elo but for **clubs**,
  not national teams — not applicable here.)

## Q1 — Live R32: capture & freeze each team's Elo leakage-free, reproducibly
Because each knockout match is played **after** we freeze its pack (§11/§12, §17),
a pre-kickoff capture is genuinely pre-match → no leakage. Make it reproducible by
archiving the **raw source bytes**, not just the parsed numbers:

1. At the matched pre-kickoff capture time `T_cap` (see Q3), fetch and **store the
   raw `World.tsv` + `en.teams.tsv` bytes** to `data/packs/<match_id>.elo_raw/`.
2. Parse the two teams' ratings, compute `elo_diff`, write them into the frozen pack.
3. Record in the pack JSON: the parsed values, `T_cap` (UTC ISO-8601), the source
   URLs, and a **SHA-256 of the raw `World.tsv` bytes**.
4. Freeze via `data_freeze.freeze_pack` (already hashes the rendered pack + refuses
   overwrite). **Enhancement needed:** also persist the raw-source archive + its hash,
   so the exact upstream state is preserved even though eloratings.net is a moving
   target. (Today the adapter re-fetches live — fine for *capture*, not for *audit*.)

Result: the frozen pack is byte-reproducible (raw snapshot archived) and leakage-free
(captured before kickoff).

## Q2 — Point-in-time / historical Elo (so finished matches could be scored cleanly)?
**No clean off-the-shelf source exists for national teams.** Two real options:

- **(A) Capture-and-freeze before kickoff** — the recommended, simplest, fully
  reproducible method. Works for every prospective knockout match. **Cannot**
  retroactively fix an already-finished match (we have no pre-match snapshot for it).
- **(B) Self-recompute Elo to a cutoff date** — implement eloratings.net's published
  World-Football-Elo formula (base ratings + K-factor by match importance + goal-
  difference multiplier + home/neutral handling) over an **independent match-results
  database** truncated at `date < kickoff`. This is the *only* way to get a
  leakage-free Elo for a **finished** match, and it doubles as an audit cross-check.
  Cost: a faithful reimplementation that won't match eloratings to the integer, plus
  a results-DB dependency. Reserve for the **group-stage secondary analysis** (§3/§14),
  which is already labelled non-prospective/exploratory and otherwise inherits this
  same Elo leakage.

**Recommendation:** (A) for the registered prospective study; (B) only if we want the
secondary group-stage Elo (and the Elo / Dixon-Coles baselines on it) to be
leakage-clean — otherwise flag that leakage explicitly there too.

## Q3 — Exact timestamp & procedure for the live Elo freeze
- **`T_cap` = kickoff − 3 hours**, per match. Rationale: align Elo capture with the
  **market snapshot's matched pre-kickoff timestamp** (§13) and the **3-hour
  pre-resolution exclusion** the protocol already adopts (§13, Prophet Arena ref), so
  Elo, FIFA rank, and the de-vigged market all describe the **same information set**.
- **Per-match, not per-round:** ratings shift as earlier matches in the round finish,
  so capture each match's Elo at *its own* `T_cap`, not once for the whole bracket.
- **Procedure:** at `T_cap` → fetch `World.tsv` + `en.teams.tsv` → archive raw bytes +
  SHA-256 → parse the two teams → write `eloA/eloB/elo_diff` + `T_cap` + source URLs +
  hash into the pack → `freeze_pack` (immutable, hashed). All four models then receive
  the byte-identical frozen pack (§11).
- **Edge cases:** if eloratings.net is unreachable at `T_cap`, retry within a short
  window and log the actual capture time; if a team name doesn't resolve, extend
  `NAME_ALIASES` (do not silently drop). Never re-capture after kickoff.

## One-line summary
For the live study, **capture eloratings `World.tsv` at kickoff−3h, archive the raw
bytes + hash, and freeze** — that is leakage-free and reproducible. Point-in-time
historical national-team Elo isn't available off the shelf; scoring a *finished*
match cleanly would require self-recomputing Elo to a pre-match cutoff (option B).

---

## IMPLEMENTED (2026-06-27)
The live capture-and-freeze above is built: `src/sources/elo_freeze.py`
(`capture_elo_snapshot` archives raw `World.tsv` + `en.teams.tsv` with a UTC
timestamp + per-file SHA-256; `freeze_elo_for_match` re-derives the two teams'
ratings from the archive and attaches provenance). Verified live: captured a real
snapshot, then re-derived Germany = 1916 **from the archived bytes offline**, with
the capture timestamp and hashes recorded. 4 offline tests in
`tests/test_elo_freeze.py`. This solves the **prospective** (R32+) case.

## SCOPE DECISION FOR THE PI — the 72 finished group-stage matches (§3/§14 secondary)
These are already over, so there is **no pre-match Elo snapshot** for them and none
can be captured now (the leakage we hit in the pilot). This must be settled before
the pre-registration is tagged. Three options — **I am not deciding; the PI decides:**

- **(a) Find/synthesize a historical-Elo source for the group stage.** The only
  viable form is **self-recomputing** World-Football-Elo to a `date < kickoff` cutoff
  for each of the 72 matches, from an independent results DB (eloratings' formula is
  published).
  *One-line rec:* most rigorous and keeps Elo (the single strongest predictor, §11)
  in the secondary set — but it's a real build (Elo reimplementation + results-DB
  dependency + validation) that won't match eloratings to the integer.

- **(b) Run the group-stage secondary WITHOUT Elo** (FIFA rank + squad value + form/
  goals/rest only; drop Elo and the Elo/Dixon-Coles baselines there).
  *One-line rec:* cheap and fully leakage-clean, but the group-stage pack then differs
  from the knockout pack, so the two sets are **not apples-to-apples**, and the
  secondary loses its strongest feature.

- **(c) Drop the group-stage secondary analysis entirely** (§3/§14 exploratory).
  *One-line rec:* simplest and removes the leakage question completely, but forfeits
  the ~72-match power booster the protocol leans on for its hard power ceiling (§15).

> The knockout (primary) study is unaffected by this decision — it always freezes
> Elo pre-kickoff via the implemented module. This is purely about the secondary
> group-stage dataset.
