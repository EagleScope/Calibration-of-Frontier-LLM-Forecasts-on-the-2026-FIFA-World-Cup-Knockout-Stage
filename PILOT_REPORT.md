# Pilot report (§19 gate) — harness & cost validation

**Date:** 2026-06-27 · **Status: PASS — proceed** · run on one finished group-stage
match (Spain–Uruguay; Elo from the live adapter, other pack fields plausible — this
is a pipeline/cost validation, not a registered forecast).

## §19 hard gate
| Gate | Result | Threshold | Verdict |
|---|---|---|---|
| Clean five-key parse rate | **100.0%** (280/280, first attempt) | > 95% | ✅ PASS |
| Brier stability N=10 vs N=20 | **0.0012** (0.1752 → 0.1740) | ≤ 0.005 | ✅ PASS |

All four models (Claude Opus 4.8, GPT-5.5, Grok 4.3, Gemini 3.1 Pro) ran the full
grid: 3 paired × 2 reasoning × 2 arms × 20 + Gemini × 1 × 2 arms × 20 = **280 calls**.

## Measured cost (prices are ESTIMATES, §18)
- **$5.86 / match** · 386,424 tokens · 51.6 min wall-clock (synchronous).
- Driven by high-reasoning tokens (Grok, GPT, Gemini), as predicted.
- **Full knockout projection:** $5.86 × 32 ≈ **$187**, plus champion/survival
  prompts ≈ **$205–230 total**. Within §18's "tens to low hundreds of dollars."
- Cost uses estimate prices (`PRICES_ARE_ESTIMATES=True`); tokens are exact, so the
  figure is final once native prices are confirmed.

## What this validates
- The end-to-end pipeline works on real APIs: frozen pack → byte-identical prompt →
  20 samples × (model × reasoning × arm) → parse → median aggregate → §21 records.
- Parsing is robust (100% clean, no retries needed).
- N=20 is stable vs N=10 (Brier within 0.0012) — supports the locked N=20 (§10).
- Reasoning params verified live for all four models (§5/§6).

## Not yet done (gating full live collection)
- Native-API **prices** to confirm (cost currently an estimate).
- Per-round **data capture** (FIFA rank, squad value, form/goals) for the actual
  knockout matchups as the bracket sets.
- **Pinnacle** closing-line capture near each kickoff (adapter ready, key set).
- PI **go** for the full ~10,000-call collection.
