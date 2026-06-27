"""
Minimal frozen-value tests for config.py.

These guard the pre-registered constants: if any locked value drifts, a test
fails. This is the auditability check the protocol relies on (§16 lock).
"""
import pytest

from config import config as C


# ---- §10 repetitions & aggregation ----
def test_locked_constants():
    assert C.N_SAMPLES == 20
    assert C.PRIMARY_AGGREGATOR == "median"
    assert C.TRIMMED_MEAN_PROPORTION == 0.10
    assert C.SENSITIVITY_N == (5, 10, 15, 20)
    assert C.TEMPERATURE == 0.7


# ---- §14 statistics ----
def test_statistical_constants():
    assert C.EQUIVALENCE_MARGIN == 0.01          # single most consequential choice
    assert C.BOOTSTRAP_RESAMPLES == 10_000
    assert C.ALPHA == 0.05
    assert C.CI_LEVEL == 0.95
    assert C.ECE_BINS == 10
    assert C.PRED_BOUNDS == (0.01, 0.99)
    assert C.DM_SMALL_SAMPLE_CORRECTION == "harvey-leybourne-newbold"
    assert C.PRIMARY_SCORE == "rps"
    assert C.DEVIG_PRIMARY == "proportional"
    assert C.POOL_MARKETS is False               # markets NEVER pooled
    assert set(C.MARKET_BASELINES) == {"polymarket", "pinnacle"}


# ---- §19 pilot gate ----
def test_pilot_gate():
    assert C.PILOT_MIN_PARSE_RATE == 0.95
    assert C.PILOT_BRIER_STABILITY == 0.005


# ---- §8/§20.6 output keys ----
def test_five_keys():
    assert C.FIVE_KEYS == ("A_WIN", "DRAW", "B_WIN", "ADV_A", "ADV_B")
    assert C.THREE_WAY_KEYS == ("A_WIN", "DRAW", "B_WIN")
    assert C.ADVANCE_KEYS == ("ADV_A", "ADV_B")


# ---- §5 model set ----
def test_four_models_verified():
    assert len(C.MODELS) == 4
    by_slot = {m.slot: m for m in C.MODELS}
    assert by_slot[1].model_id == "claude-opus-4-8"
    assert by_slot[2].model_id == "gpt-5.5-2026-04-23"
    assert by_slot[3].model_id == "grok-4.3"
    assert by_slot[4].model_id == "gemini-3.1-pro-preview"


def test_gemini_high_only_excluded_from_paired_contrast():
    gemini = next(m for m in C.MODELS if m.provider == "google")
    assert gemini.in_paired_contrast is False         # §6
    assert set(gemini.reasoning_kwargs.keys()) == {"high"}
    # The three paired models run both levels.
    paired = [m for m in C.MODELS if m.in_paired_contrast]
    assert len(paired) == 3
    for m in paired:
        assert set(m.reasoning_kwargs.keys()) == {"low", "high"}


def test_every_provider_has_env_var():
    for m in C.MODELS:
        assert m.provider in C.PROVIDER_ENV_VARS
        assert C.PROVIDER_ENV_VARS[m.provider]        # non-empty


def test_gpt_rejects_temperature():
    gpt = next(m for m in C.MODELS if m.provider == "openai")
    assert gpt.accepts_temperature is False           # §10 documented per model


# ---- §20 frozen prompts ----
def test_shared_block_byte_exact():
    expected = (
        "You are forecasting a single match in the 2026 FIFA World Cup knockout stage.\n"
        "Use only the data provided below. Do not use any outside information.\n"
        "All matches are at neutral venues unless a host flag indicates otherwise.\n"
        "Give your honest probability estimate. Do not hedge to round numbers."
    )
    assert C.SHARED_INSTRUCTION_BLOCK == expected


def test_output_spec_lists_five_keys_in_order():
    # Each key appears as a "KEY=" line, in the protocol's order.
    for k in C.FIVE_KEYS:
        assert f"{k}=" in C.OUTPUT_SPEC
    idx = [C.OUTPUT_SPEC.index(f"{k}=") for k in C.FIVE_KEYS]
    assert idx == sorted(idx)


SAMPLE_PACK = {
    "round": "Round of 32", "date": "2026-06-28", "venue": "Stadium", "venue_city": "City",
    "team_A": "Team A", "team_B": "Team B",
    "eloA": 2000, "eloB": 1900, "elo_diff": 100,
    "rankA": 5, "rankB": 12, "mvA": 800, "mvB": 600,
    "formA": "6-2-2", "formB": "5-3-2", "gfgaA": "14/7", "gfgaB": "11/8",
    "hostA": "no", "hostB": "no", "restA": 4, "restB": 3,
}
SAMPLE_MARKET = {"mktA": 45, "mktD": 28, "mktB": 27}


def test_conditioning_arm_differs_by_exactly_the_market_block():
    primary = C.build_match_prompt(SAMPLE_PACK, arm="primary")
    cond = C.build_match_prompt(SAMPLE_PACK, arm="conditioning", market=SAMPLE_MARKET)
    market_block = C.MARKET_LINE_TEMPLATE.format(**SAMPLE_MARKET)
    # The block is inserted as "{market_block}\n\n" immediately before the output
    # spec; removing exactly that must reproduce the primary prompt byte-for-byte.
    assert market_block in cond
    assert cond.replace(market_block + "\n\n", "") == primary
    # And the market block is absent from the primary arm.
    assert market_block not in primary


def test_conditioning_requires_market():
    with pytest.raises(ValueError):
        C.build_match_prompt(SAMPLE_PACK, arm="conditioning")


def test_bad_arm_rejected():
    with pytest.raises(ValueError):
        C.build_match_prompt(SAMPLE_PACK, arm="retrieval")
