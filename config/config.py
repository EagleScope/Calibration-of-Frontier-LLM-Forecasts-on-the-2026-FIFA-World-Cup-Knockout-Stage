"""
config.py — SINGLE SOURCE OF TRUTH for the pre-registered WC-2026 LLM
calibration study.

Every locked parameter from METHODS_PROTOCOL_v1.md lives here and nowhere else.
Nothing in this dict/these constants may be hardcoded elsewhere in the codebase;
modules import from here so the frozen values are auditable in one place.

Section references (§) point at METHODS_PROTOCOL_v1.md.

Provenance of each value:
  FROZEN          — locked by the protocol text; do not change.
  VERIFIED        — checked against the live provider API at build time
                    (model IDs / key validity), then frozen.
  PENDING_SIGNOFF — proposed default that needs the PI's explicit confirmation
                    BEFORE protocol lock (flagged inline; never silently guessed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# =============================================================================
# 0. Lock metadata
# =============================================================================
PROTOCOL_VERSION = "1.0"
PROTOCOL_FILE = "METHODS_PROTOCOL_v1.md"
# Set to the commit/timestamp at lock. Until then the study is NOT locked.
LOCKED = False  # FROZEN flips to True only at the §17 protocol-lock commit.

# =============================================================================
# 1. Repetitions & aggregation  (§10) — FROZEN
# =============================================================================
N_SAMPLES = 20                      # samples per (model x reasoning x arm x match)
PRIMARY_AGGREGATOR = "median"       # primary point forecast
ROBUSTNESS_AGGREGATOR = "trimmed_mean"
TRIMMED_MEAN_PROPORTION = 0.10      # 10% trimmed mean (each tail)
SENSITIVITY_N = (5, 10, 15, 20)     # re-derive aggregate at these N for stability
TEMPERATURE = 0.7                   # for models that accept it; documented per model

# =============================================================================
# 2. Forecast output keys & elicitation  (§8, §9, §20.6) — FROZEN
# =============================================================================
# Exactly these five integer keys per match call.
FIVE_KEYS: Tuple[str, ...] = ("A_WIN", "DRAW", "B_WIN", "ADV_A", "ADV_B")
THREE_WAY_KEYS: Tuple[str, ...] = ("A_WIN", "DRAW", "B_WIN")   # ordinal: RPS applies
ADVANCE_KEYS: Tuple[str, ...] = ("ADV_A", "ADV_B")
ELICITATION_SCALE = (0, 100)        # integer 0-100, renormalized to sum 100 in analysis

# =============================================================================
# 3. Reasoning-effort conditions  (§6) — FROZEN structure
# =============================================================================
REASONING_LEVELS: Tuple[str, ...] = ("low", "high")
# Gemini is high-only (always-on thinking, cannot disable) — see MODELS below.

# =============================================================================
# 4. Market-conditioning arms  (§7) — FROZEN
# =============================================================================
ARMS: Tuple[str, ...] = ("primary", "conditioning")  # market withheld / supplied

# =============================================================================
# 5. Statistical analysis constants  (§14) — FROZEN
# =============================================================================
EQUIVALENCE_MARGIN = 0.01           # TOST margin in RPS/Brier diff (§14, most consequential)
BOOTSTRAP_RESAMPLES = 10_000        # bootstrap CIs for scores & skill
ALPHA = 0.05                        # significance level; primary tests uncorrected (§14)
CI_LEVEL = 0.95                     # 95% confidence/bootstrap intervals
# Fixes the FROZEN scoring script's bootstrap resampling so CIs are reproducible
# and cannot be re-rolled after results arrive (§17 credibility). Not a modelling
# choice — purely reproducibility.
BOOTSTRAP_SEED = 20260627
ECE_BINS = 10                       # equal-width bins for ECE/MCE
PRED_BOUNDS: Tuple[float, float] = (0.01, 0.99)   # clip preds so log score stays finite
DM_SMALL_SAMPLE_CORRECTION = "harvey-leybourne-newbold"   # mandatory at this n
PROPORTION_INTERVAL = "wilson"      # Wilson intervals for proportions

# Primary vs alongside scores (§14)
PRIMARY_SCORE = "rps"               # ordinal outcomes -> RPS is primary
ALONGSIDE_SCORES = ("brier", "log")

# De-vig methods (§13) — proportional primary; others as sensitivity
DEVIG_PRIMARY = "proportional"
DEVIG_SENSITIVITY = ("odds_ratio", "shin")

# Skill-score baselines are scored SEPARATELY and NEVER pooled (§13, §14)
MARKET_BASELINES: Tuple[str, ...] = ("polymarket", "pinnacle")
POOL_MARKETS = False                # hard rule: never pool skill across the two

# =============================================================================
# 6. Pilot gate  (§19) — FROZEN
# =============================================================================
PILOT_MIN_PARSE_RATE = 0.95         # > 95% responses return clean five keys
PILOT_BRIER_STABILITY = 0.005       # |Brier(N=10) - Brier(N=20)| must be <= this

# =============================================================================
# 7. Scale estimate  (§18) — FROZEN (sanity check / cost projection)
# =============================================================================
CALLS_PER_MATCH = 280               # (3 paired x 2 reasoning x 2 arms x 20) + (Gemini x 1 x 2 arms x 20)
N_KNOCKOUT_MATCHES = 32

# =============================================================================
# 8. Models (LOCKED four-model set, §5) — IDs VERIFIED at build time
# =============================================================================
@dataclass(frozen=True)
class ModelSpec:
    slot: int
    name: str                       # display name from the protocol (§5)
    provider: str                   # anthropic | openai | xai | google
    model_id: str                   # VERIFIED exact API identifier
    api: str                        # which native API / SDK base
    in_paired_contrast: bool        # §6 low-vs-high paired contrast membership
    accepts_temperature: bool       # §10 temperature handling
    # Map reasoning level -> exact extra kwargs to send to the provider.
    # Keys present == levels this model runs. Gemini runs "high" only.
    reasoning_kwargs: Dict[str, dict] = field(default_factory=dict)
    notes: str = ""


MODELS: List[ModelSpec] = [
    # ---- Slot 1: Claude Opus 4.8 (Anthropic native) -----------------------
    ModelSpec(
        slot=1,
        name="Claude Opus 4.8",
        provider="anthropic",
        model_id="claude-opus-4-8",                 # VERIFIED via GET /v1/models
        api="anthropic_messages",
        in_paired_contrast=True,
        accepts_temperature=True,
        reasoning_kwargs={
            # Claude has NO low/high enum — reasoning is `thinking.budget_tokens`.
            # PENDING_SIGNOFF: define the two budgets that operationalize low vs high.
            # Proposed: low = thinking disabled (minimal reasoning),
            #           high = extended thinking with a large budget.
            "low": {"thinking": {"type": "disabled"}},                       # PENDING_SIGNOFF
            "high": {"thinking": {"type": "enabled", "budget_tokens": 16000}},  # PENDING_SIGNOFF
        },
        notes="Anthropic key valid at build. budget_tokens mapping needs PI sign-off (§6).",
    ),
    # ---- Slot 2: GPT-5.5 (OpenAI native) ----------------------------------
    ModelSpec(
        slot=2,
        name="GPT-5.5",
        provider="openai",
        model_id="gpt-5.5-2026-04-23",              # VERIFIED; pinned dated snapshot
        api="openai_responses",
        in_paired_contrast=True,
        accepts_temperature=False,                  # §10: GPT-5.x reasoning rejects temp != 1
        reasoning_kwargs={
            "low": {"reasoning_effort": "low"},     # reasoning_effort in {minimal,low,medium,high}
            "high": {"reasoning_effort": "high"},
        },
        notes="Only model offering a dated snapshot. Diversity via stochastic reasoning, not temp.",
    ),
    # ---- Slot 3: Grok 4.3 (xAI native, OpenAI-compatible) -----------------
    ModelSpec(
        slot=3,
        name="Grok 4.3",
        provider="xai",
        model_id="grok-4.3",                        # VERIFIED via GET /v1/models
        api="xai_openai_compatible",
        in_paired_contrast=True,
        accepts_temperature=True,                   # PENDING_SIGNOFF: confirm at client build
        reasoning_kwargs={
            # PENDING_SIGNOFF: confirm grok-4.3 exposes reasoning_effort low/high
            # (grok-3-mini did; grok-4 was always-reasoning). Verify at client build.
            "low": {"reasoning_effort": "low"},     # PENDING_SIGNOFF
            "high": {"reasoning_effort": "high"},   # PENDING_SIGNOFF
        },
        notes="reasoning_effort support on grok-4.3 must be confirmed before lock.",
    ),
    # ---- Slot 4: Gemini 3.1 Pro (Google AI native) — HIGH ONLY ------------
    ModelSpec(
        slot=4,
        name="Gemini 3.1 Pro",
        provider="google",
        model_id="gemini-3.1-pro-preview",          # VERIFIED; note: PREVIEW alias (may drift)
        api="google_genai",
        in_paired_contrast=False,                   # §6: excluded from paired low-vs-high
        accepts_temperature=True,
        reasoning_kwargs={
            # Always-on thinking, cannot disable -> contributes the HIGH cell only.
            # PENDING_SIGNOFF: confirm exact thinking-level param at client build.
            "high": {},                             # PENDING_SIGNOFF (default thinking on)
        },
        notes="Preview alias, not a dated snapshot; log API version + timestamp every call (§5).",
    ),
]

# Provider -> env var holding the API key (keys live in .env, never in code).
PROVIDER_ENV_VARS: Dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "xai": "XAI_API_KEY",
    "google": "GOOGLE_AI_API_KEY",
}

XAI_BASE_URL = "https://api.x.ai/v1"   # Grok via OpenAI-compatible endpoint

# =============================================================================
# 9. Standardized information-pack field list  (§11) — FROZEN
# =============================================================================
# Two-market baselines are EXCLUDED from the primary pack (circularity, §11/§12).
PACK_FIELDS: Tuple[str, ...] = (
    "elo", "elo_diff", "fifa_rank", "squad_value_eur_m",
    "recent_form_wdl", "goals_for_against", "host_flag", "rest_days",
)
PACK_DATA_SOURCES: Dict[str, str] = {
    "elo": "eloratings.net",
    "fifa_rank": "FIFA",
    "squad_value_eur_m": "Transfermarkt",
    "recent_form_wdl": "match-results database (TBD)",
    "goals_for_against": "match-results database (TBD)",
    "rest_days": "official schedule",
    "host_flag": "official schedule (USA/CAN/MEX co-hosts)",
}

# =============================================================================
# 10. Frozen prompt set  (§20) — BYTE-IDENTICAL across all models & conditions
# =============================================================================
# NOTE: these strings are frozen. Reasoning effort & temperature are set ONLY by
# API parameter (above), never by prompt wording. The market arm differs from the
# primary arm by exactly one added line (§20.4).

# §20.1 — shared instruction block (top of every match prompt)
SHARED_INSTRUCTION_BLOCK = (
    "You are forecasting a single match in the 2026 FIFA World Cup knockout stage.\n"
    "Use only the data provided below. Do not use any outside information.\n"
    "All matches are at neutral venues unless a host flag indicates otherwise.\n"
    "Give your honest probability estimate. Do not hedge to round numbers."
)

# §20.2 — match information pack (filled per match, identical structure every time)
MATCH_PACK_TEMPLATE = (
    "MATCH: {round}, {date}, {venue}, {venue_city}\n"
    "TEAM A: {team_A}\n"
    "TEAM B: {team_B}\n"
    "\n"
    "                              TEAM A        TEAM B\n"
    "World Football Elo:           {eloA}        {eloB}\n"
    "Elo difference (A - B):       {elo_diff}\n"
    "FIFA ranking:                 {rankA}       {rankB}\n"
    "Squad market value (EUR m):   {mvA}         {mvB}\n"
    "Recent form (last 10, W-D-L): {formA}       {formB}\n"
    "Goals for / against (last 10):{gfgaA}       {gfgaB}\n"
    "Host nation playing at home:  {hostA}       {hostB}\n"
    "Rest days since last match:   {restA}       {restB}"
)

# §20.3 — match prompt primary arm (market withheld), output spec
OUTPUT_SPEC = (
    "Give the probability of each 90-minute result, as integers that sum to 100.\n"
    "Then give the probability that each team advances to the next round after\n"
    "extra time and penalties, as integers that sum to 100.\n"
    "Respond with exactly these five lines and nothing else.\n"
    "\n"
    "A_WIN=\n"
    "DRAW=\n"
    "B_WIN=\n"
    "ADV_A=\n"
    "ADV_B="
)

# §20.4 — market-supplied arm: one line added to the pack BEFORE the output spec
MARKET_LINE_TEMPLATE = (
    "Market-implied probabilities (de-vigged), A_WIN / DRAW / B_WIN:\n"
    "                              {mktA} / {mktD} / {mktB}"
)

# §20.5 — champion-probability prompt (refreshed before each round)
CHAMPION_PROMPT_TEMPLATE = (
    "You are forecasting the winner of the 2026 FIFA World Cup.\n"
    "Use only the data provided below. Do not use any outside information.\n"
    "\n"
    "REMAINING TEAMS AND BRACKET:\n"
    "{bracket_with_paths}\n"
    "\n"
    "TEAM SUMMARY (Elo, FIFA rank, squad value EUR m):\n"
    "{one_row_per_remaining_team}\n"
    "\n"
    "Give the probability that each remaining team wins the tournament, as integers\n"
    "that sum to 100 across all teams listed. Respond with one line per team in the\n"
    "form TEAM=probability and nothing else."
)


def build_match_prompt(pack_fields: dict, arm: str, market: Optional[dict] = None) -> str:
    """Assemble a full match prompt from frozen pieces.

    arm == 'primary'      -> instruction + pack + output spec
    arm == 'conditioning' -> instruction + pack + market line + output spec  (§20.4)

    The ONLY difference between arms is the single market line; everything else is
    byte-identical, as required by §7/§20.
    """
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}, got {arm!r}")
    pack = MATCH_PACK_TEMPLATE.format(**pack_fields)
    parts = [SHARED_INSTRUCTION_BLOCK, "", pack]
    if arm == "conditioning":
        if market is None:
            raise ValueError("conditioning arm requires market={'mktA','mktD','mktB'}")
        parts += ["", MARKET_LINE_TEMPLATE.format(**market)]
    parts += ["", OUTPUT_SPEC]
    return "\n".join(parts)
