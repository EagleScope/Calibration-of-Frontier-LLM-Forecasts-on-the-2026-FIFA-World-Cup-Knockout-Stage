# Pre-Lock Checklist — items needing the PI before/around lock

Single auditable list of every open decision and `PENDING_SIGNOFF` in the code.
The **frozen scoring script and protocol do not depend on any of these** — they
can be timestamped now. These gate the *live data collection*, not the lock.

## A. Blocking the protocol lock (§17 — hard deadline, first R32 kickoff)
- [ ] **Push to public remote + OSF** to timestamp `METHODS_PROTOCOL_v1.md` +
      `src/scoring_frozen.py`. *(PI action — I cannot do this.)*
- [ ] **Rotate all keys** pasted in chat (4 LLM + 3 AWS). They are gitignored and
      never committed, but exposure-in-chat warrants rotation before the repo is public.

## B. Reasoning low/high mappings (§6) — RESOLVED (verified live 2026-06-27)
All confirmed via smoke test against the live APIs; `config/config.py` updated:
- [x] **Claude Opus 4.8** — `thinking.type=adaptive` + `output_config.effort`
      (low/high). temperature is DEPRECATED for this model and is not sent.
- [x] **GPT-5.5** — `reasoning_effort` low/high (reasoning tokens 177 -> 1024).
- [x] **Grok 4.3** — `reasoning_effort` low/high (reasoning tokens 660 -> 2428);
      accepts temperature 0.7.
- [x] **Gemini 3.1 Pro** — default config = always-on thinking (high cell only).

## C. Native-API prices (§18 cost logging) — ESTIMATES IN, confirm before final cost
Code location: `src/clients/pricing.py` → `PRICES` (`PRICES_ARE_ESTIMATES=True`).
- [ ] Confirm native per-1M prices. Currently ESTIMATES: Claude $5/$25 and GPT
      $5.5/$33 (Bedrock catalog), Grok $3/$15 and Gemini $2/$12 (placeholders).
      Tokens are logged exactly; only the USD multiplier needs confirming.

## D. Statistical-baseline parameterization (§13) — confirm before lock
Code location: `src/baselines.py`. Math is fixed; these inputs are open:
- [ ] **Elo→1X2 draw model**: `ELO_DRAW_MAX=0.28`, `ELO_DRAW_SCALE=200`.
- [ ] **Dixon-Coles** low-score correlation `DC_RHO_DEFAULT=-0.05`.
- [ ] **Expected-goals mapping** from the pack: `base_goals=1.35`, `elo_per_goal=250`.

## E. Data sources (§11, §13) — needed for the live pack + 3-way benchmark
- [x] **Elo (eloratings.net)** — DONE: `src/sources/elo_eloratings.py` (live TSV,
      name->rating, eloA/eloB/elo_diff). Verified live.
- [~] **FIFA rank** — adapter DONE (`src/sources/fifa_ranking.py`, frozen-table
      loader). **DECISION NEEDED:** the live FIFA page shows the *unofficial* mid-
      tournament ranking; for the freeze use the **official 2026-06-11 table**.
      Confirm "official June 11" is the snapshot to freeze, then the full 48-team
      official table is captured into `data/reference/`. A live top-10 SAMPLE
      (`official:false`) is committed only to exercise the adapter — not the input.
- [ ] **Remaining match-data adapters**: Transfermarkt squad value, recent
      form/goals (a results DB — which one? some need a key). `data_freeze.FieldSource`
      is the interface. *(Transfermarkt has no API and scraping has ToS implications
      for a public repo — confirm approach: browser-capture into a frozen table,
      like FIFA, is the clean option.)*
- [~] **Pinnacle closing line** (§13): adapter DONE (`src/markets/pinnacle.py`,
      the-odds-api v4 h2h -> de-vig -> A/B-aligned 1X2 snapshot). **NEEDS:** your
      `ODDS_API_KEY` (the-odds-api.com, Pinnacle coverage) in `.env`. Then I poll
      near each kickoff for the closing line.
- [ ] **2026 bracket/schedule** feed (teams, dates, venues, rest days). For the
      pilot only finished group-stage matches are needed.

## F. Pilot (§19) — run before any large collection
- [ ] Approve the **live pilot** on a few finished group-stage matches. It must clear
      the gate (>95% clean five-key parse; Brier stable within 0.005 between N=10/20)
      and I will **show measured per-match cost** before anything larger runs.

## Collection staging (registered operational decision — 2026-06-28)
- **Conditioning (market-supplied) arm is staged, NOT dropped.** For match 73 and
  early R32, only the **primary (market-withheld) arm** is run, because the live
  per-match market capture (Pinnacle + Polymarket) has not yet been exercised on real
  data — we will not run untested market code in the prompt path on a live match.
  Both arms remain in the registered design (§7); the conditioning arm comes online
  early in R32 once the live market capture is built and tested. This sequencing is
  recorded here so the early-R32 absence of conditioning data is transparent and dated,
  not a silent omission.
- **Market is still captured as a benchmark from match 73 onward** (raw Pinnacle/
  Polymarket pre-kickoff prices, stored as gitignored collected data) — capturing the
  price is separate from conditioning the models on it.

## Resolved at build time (no longer open)
- [x] All four model IDs verified live: `claude-opus-4-8`, `gpt-5.5-2026-04-23`,
      `grok-4.3`, `gemini-3.1-pro-preview`.
- [x] Polymarket champion/outright structure verified live (`world-cup-winner`
      event; per-team binary Yes/No). Per-match knockout markets post per round (§17).
- [x] N reduced 20 -> 10 (PI cost decision); protocol + config read N=10; pilot
      stability evidence retained out-of-tag (git history + data/pilot/_local/).
