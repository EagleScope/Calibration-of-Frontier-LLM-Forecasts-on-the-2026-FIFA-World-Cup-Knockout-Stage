# N-sampling justification — registered reduction N = 20 → 10

**Registered before the protocol lock.** The locked sample size is reduced from
**N = 20 to N = 10** samples per (model × reasoning × arm × match). This halves the
live API cost (≈$200 → ≈$110) with negligible loss of precision, justified by the
pre-registration pilot below (per §10 sensitivity / §19 gate).

## The justification: a real pilot was run at N = 20 and N = 10 was stable
Pilot: **Germany vs Ecuador** (finished group-stage match, 2026-06-25), full grid,
**primary arm**, N = 20, real-sourced pack (Elo via the freeze module; FIFA / squad
value / form / goals / rest per `data/pilot/ecuador_germany_pack_sources.json`).

**§19 gate — both criteria met:**
- Clean five-key parse rate: **100.0%** (140/140, first attempt) — gate > 95% ✅
- Aggregate Brier **stable between N = 10 and N = 20**:

| cell | Brier@N=10 | Brier@N=20 | \|diff\| |
|---|---|---|---|
| Claude Opus 4.8 (low) | 0.9665 | 0.9674 | 0.0009 |
| Claude Opus 4.8 (high) | 0.9464 | 0.9464 | 0.0000 |
| GPT-5.5 (low) | 0.9206 | 0.9179 | 0.0027 |
| GPT-5.5 (high) | 0.8906 | 0.8906 | 0.0000 |
| Grok 4.3 (low) | 0.9055 | 0.9165 | 0.0110 |
| Grok 4.3 (high) | 1.0271 | 1.0302 | 0.0031 |
| Gemini 3.1 Pro (high) | 0.8608 | 0.8694 | 0.0086 |
| **aggregate (mean)** | **0.9311** | **0.9341** | **0.0030** |

Aggregate |diff| = **0.0030 ≤ 0.005** → **gate passed**. Going from 20 samples to 10
moves the aggregate Brier by 0.3 of a percentage point — N = 10 reproduces N = 20.

## Important labelling (so this is not over-read)
- This is a **sampling-stability / harness check**, **not** a forecast-skill result.
  The *absolute* Brier is high because the underdog (Ecuador) won and **Elo was leaked**
  for this finished match; **no skill is claimed**. The conditioning arm was **not run**
  (no real market line). None of that affects the justification: the metric that
  justifies N is the **N=10-vs-N=20 difference**, which measures sampling convergence
  and uses the same result on both sides, so it is independent of leakage.

## Evidence on disk (committed)
- Raw per-call records (every one of the 140 N=20 calls, verbatim response + parsed
  + params + timestamp + tokens): `data/pilot/evidence/pilot_germany_ecuador_n20_records.jsonl`
- Sourced pack + per-field source URLs: `data/pilot/ecuador_germany_pack_sources.json`

So the full N=20 run is preserved and reproducible — anyone can recompute the table
above and confirm N=10 was justified before lock.
