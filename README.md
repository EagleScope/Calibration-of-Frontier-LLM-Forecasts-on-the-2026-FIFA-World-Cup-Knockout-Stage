# WC-2026 LLM Calibration Study

Pre-registered forecasting pipeline measuring how well-calibrated frontier LLM
match forecasts are over the **2026 FIFA World Cup knockout stage**, benchmarked
against real-money markets (Polymarket, Pinnacle) on proper scoring rules.

**This is a pre-registration.** [`METHODS_PROTOCOL_v1.md`](METHODS_PROTOCOL_v1.md)
is the single source of truth. The code implements the registered method exactly;
it does not deviate from or "improve" the spec.

## Two-tier timestamping (§17)
1. **Protocol lock (hard deadline):** this protocol + the **frozen scoring script**
   committed and timestamped **before the first Round-of-32 kickoff**.
2. **Forecast timestamps (rolling):** each round's forecasts frozen before that
   round's kickoff.

## Repository layout
```
config/config.py      Single source of truth: all locked constants, the four
                      verified model entries, and the §20 prompt templates.
src/data_freeze.py    §11 — pull each field, write one timestamped frozen pack
                      per match. (build order #1)
src/clients/          §18 — uniform forecast(pack, reasoning_level, arm) per
                      provider. (next session)
src/run_aggregate.py  §18.3 — 10 samples, parse five keys, aggregate by median.
src/scoring_frozen.py §14 — FROZEN scoring: calibration, RPS/Brier/log, skill
                      vs each market, DM+HLN, bootstrap CIs, TOST. Runs on
                      synthetic data. Committed & timestamped at lock.
src/pilot.py          §19 — pilot gate on finished group-stage matches.
tests/                Minimal test per module.
```

## Models (§5, IDs verified against live provider APIs at build time)
| Slot | Model | Provider / API | Model ID |
|---|---|---|---|
| 1 | Claude Opus 4.8 | Anthropic | `claude-opus-4-8` |
| 2 | GPT-5.5 | OpenAI | `gpt-5.5-2026-04-23` |
| 3 | Grok 4.3 | xAI (OpenAI-compatible) | `grok-4.3` |
| 4 | Gemini 3.1 Pro | Google AI | `gemini-3.1-pro-preview` (high-only, §6) |

## Secrets
API keys load from `.env` (gitignored). Copy `.env.example` → `.env` and fill in.
**Never commit real keys — this repo is public.**

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit
pytest -q
```

## Status
- [x] Config — locked constants, verified models, §20 prompts (`config/config.py`)
- [x] **Frozen scoring script (§14)** — `src/scoring_frozen.py` (lock-critical; runs on synthetic data)
- [x] De-vig / parsing / aggregation — `src/markets/devig.py`, `src/parsing.py`, `src/aggregate.py`
- [x] Data freeze (§11/§12) + storage schemas (§21) — `src/data_freeze.py`, `src/records.py`
- [x] Polymarket Gamma client (§13) — `src/markets/polymarket.py` (champion/outright verified live)
- [x] Model clients (§18.2) — `src/clients/` (code complete; live smoke-test pending approval)
- [x] Run/aggregate (§18.3) + Pilot gate (§19) — `src/run_aggregate.py`, `src/pilot.py`
- [ ] **PI sign-offs before lock** — reasoning low/high mappings (Claude budget, Grok param,
      Gemini thinking), native-API prices; pilot live run on finished group-stage matches
- [ ] Data-source adapters — Elo / FIFA / Transfermarkt / results DB scrapers (sources TBD)
- [ ] Pinnacle closing-line source (§13) — odds aggregator + key TBD

`73 tests passing.` No live API calls are made anywhere in the test suite.
