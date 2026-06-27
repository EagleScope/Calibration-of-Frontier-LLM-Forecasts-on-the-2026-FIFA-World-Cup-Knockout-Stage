# Pre-Lock Checklist — items needing the PI before/around lock

Single auditable list of every open decision and `PENDING_SIGNOFF` in the code.
The **frozen scoring script and protocol do not depend on any of these** — they
can be timestamped now. These gate the *live data collection*, not the lock.

## A. Blocking the protocol lock (§17 — hard deadline, first R32 kickoff)
- [ ] **Push to public remote + OSF** to timestamp `METHODS_PROTOCOL_v1.md` +
      `src/scoring_frozen.py`. *(PI action — I cannot do this.)*
- [ ] **Rotate all keys** pasted in chat (4 LLM + 3 AWS). They are gitignored and
      never committed, but exposure-in-chat warrants rotation before the repo is public.

## B. Reasoning low/high mappings (§6) — confirm before the live run
Code location: `config/config.py` → `MODELS[*].reasoning_kwargs`.
- [ ] **Claude Opus 4.8** — no low/high enum. Current default: `low` = thinking
      disabled, `high` = extended thinking `budget_tokens=16000`. Confirm the two
      budgets. (Note: thinking-on forces `temperature=1`, so the high cell cannot
      use temp 0.7 — diversity from stochastic reasoning, documented per §10.)
- [ ] **Grok 4.3** — confirm `reasoning_effort` low/high is exposed by `grok-4.3`
      (grok-3-mini had it; grok-4 was always-reasoning). Verify in the pilot smoke-test.
- [ ] **Gemini 3.1 Pro** — confirm the exact thinking-level parameter for the
      high-only cell (always-on thinking).
- [ ] **Grok temperature** — confirm `grok-4.3` accepts `temperature=0.7`.

## C. Native-API prices (§18 cost logging)
Code location: `src/clients/pricing.py` → `PRICES`.
- [ ] Confirm current per-1M input/output (and reasoning) prices for Anthropic,
      OpenAI, xAI, Google. Tokens are logged now; USD shows PENDING until set.
      The pilot reports the true per-match figure once prices are in.

## D. Statistical-baseline parameterization (§13) — confirm before lock
Code location: `src/baselines.py`. Math is fixed; these inputs are open:
- [ ] **Elo→1X2 draw model**: `ELO_DRAW_MAX=0.28`, `ELO_DRAW_SCALE=200`.
- [ ] **Dixon-Coles** low-score correlation `DC_RHO_DEFAULT=-0.05`.
- [ ] **Expected-goals mapping** from the pack: `base_goals=1.35`, `elo_per_goal=250`.

## E. Data sources (§11, §13) — needed for the live pack + 3-way benchmark
- [x] **Elo (eloratings.net)** — DONE: `src/sources/elo_eloratings.py` (live TSV,
      name->rating, eloA/eloB/elo_diff). Verified live.
- [ ] **Remaining match-data adapters**: FIFA rank, Transfermarkt squad value,
      recent form/goals (a results DB — which one? some need a key).
      `data_freeze.FieldSource` is the interface. *(Transfermarkt has no API and
      scraping has ToS implications for a public repo — confirm approach.)*
- [ ] **Pinnacle closing line** (§13): no open API; pick an odds aggregator
      (e.g. the-odds-api.com) + key. Sole three-way (1X2) benchmark if Polymarket
      doesn't price the draw per match.
- [ ] **2026 bracket/schedule** feed (teams, dates, venues, rest days). For the
      pilot only finished group-stage matches are needed.

## F. Pilot (§19) — run before any large collection
- [ ] Approve the **live pilot** on a few finished group-stage matches. It must clear
      the gate (>95% clean five-key parse; Brier stable within 0.005 between N=10/20)
      and I will **show measured per-match cost** before anything larger runs.

## Resolved at build time (no longer open)
- [x] All four model IDs verified live: `claude-opus-4-8`, `gpt-5.5-2026-04-23`,
      `grok-4.3`, `gemini-3.1-pro-preview`.
- [x] Polymarket champion/outright structure verified live (`world-cup-winner`
      event; per-team binary Yes/No). Per-match knockout markets post per round (§17).
