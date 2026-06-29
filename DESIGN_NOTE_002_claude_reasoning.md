# Design Note 002 (repo) — Opus 4.8 adaptive thinking: finding & limitation

> Repo-level methods note. The registered method is **unchanged**: no edit to
> `config/config.py`, to the §20 prompt, or to the frozen pre-registration tag
> `pre-registration-v1.0` (commit `c5cde21`); the OSF registration is untouched.
> Committed post-tag. This note records an observed behaviour and its consequence
> for analysis — it does **not** change anything that runs.

- **Date:** 2026-06-29

## Finding — Opus 4.8 barely reasons on the forecasting task
On the registered forecasting prompt, **Claude Opus 4.8's adaptive thinking engages
~0 extended reasoning at BOTH low and high effort.** Direct diagnostic (same frozen
match-76 pack, `thinking:{type:"adaptive", display:"summarized"}`):

| Task | effort | output_tokens | visible thinking |
|---|---|---|---|
| Forecast (study prompt) | low | 40 | 0 chars |
| Forecast (study prompt) | high | 40 | 0 chars |
| **Hard-probe control** (3 logic puzzles) | high | **589** | **578 chars** |

The hard-probe control (output **40 → 589**, thinking **0 → 578 chars**) proves the
pipeline **can** induce and capture Claude's thinking when the task warrants it — so
the near-zero thinking on the forecast task is **genuine model behaviour, not a
harness bug**.

**Mechanism / cost note (so it is not re-litigated):** the Anthropic Messages API
`usage` object has **no separate reasoning-token field** (fields are
`input_tokens`, `output_tokens`, `cache_*`). Claude's thinking, when it happens, is
billed **inside `output_tokens`**, which we capture. So `reasoning_tokens = 0` in our
records is correct (there is no field to read), `output_tokens ≈ 40/call` means the
model genuinely produced ~no thinking, and **Claude's cost is correctly counted, not
undercounted.** Claude is the cheapest model here because its adaptive thinking is
truly adaptive — unlike GPT-5.5 / Grok 4.3, whose `reasoning_effort` spends reasoning
tokens even on easy tasks.

## Limitation — within-Claude effort contrast is null for this task
Because adaptive thinking engages ~0 at both levels, **Claude's low-vs-high effort
forecasts are identical on this task → a null within-model effort contrast.**
Consequently:

- **H2's within-model effort contrast is carried by GPT-5.5 and Grok 4.3**, which
  vary `reasoning_effort` low vs high across **all** matches.
- **Claude Opus 4.8 contributes a documented null** to that contrast (reported, not
  dropped).
- **Gemini 3.1 Pro is high-only** and is excluded from the paired effort contrast, as
  pre-registered.

## Decision (recorded)
A forced-extended-thinking Claude arm was **considered and rejected** — `budget_tokens`
is unavailable on Opus 4.8, `effort:"high"` already produced zero thinking (so
`effort:"max"` is unlikely to differ), and the only reliable forcer (appending a
"reason step by step" instruction) is a **prompt change, not a reasoning manipulation**
— it would be prompt-confounded, answer a different question, and add cost and a
coverage asymmetry for no clean gain. **No forced arm is built or run.**

The registered Claude arm stays **locked** (adaptive thinking; effort low + high;
byte-identical prompt; primary + conditioning; N=10). It is identical across **all 32
matches**, which therefore remain fully comparable on it. Matches 73 and 76 were
collected under exactly this arm.
