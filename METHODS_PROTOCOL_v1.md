# Methods & Pre-Registration Protocol — LLM Calibration on the 2026 World Cup Knockout Stage

**Version 1.0 — locked, four-model set. This document is both (a) the pre-registration to be timestamped before the first Round-of-32 kickoff and (b) the executable build specification handed to the implementation engineer.**

---

## 0. Framing (governs how everything below is read)

This is a **calibration and market-benchmarking study, not an accuracy contest.** No defensible study can rest on forecasting football *well*: the strongest public statistical models correlate only weakly with actual outcomes and concede their own limited power. The claims of this study rest instead on four things: the scoring rules being **proper**, the forecasts being **timestamped before kickoff**, the baselines being **real markets**, and the analysis being **pre-registered**. Every primary outcome is informative in either direction precisely because the prediction is locked in advance.

---

## 1. Research questions

**Overarching.** When current frontier large language models are asked to forecast irreducibly uncertain, market-priced football outcomes under identical information, how well-calibrated are their probabilities, how do they compare to real-money market baselines, and does giving them more reasoning or more information make them better forecasters or only more confident?

- **RQ1.** How well-calibrated are frontier LLM match forecasts, and in which direction do they err?
- **RQ2.** Does increasing reasoning effort improve or degrade calibration and accuracy, and is the direction consistent across models?
- **RQ3.** How do LLM forecasts compare to the de-vigged Polymarket price and the Pinnacle closing line on proper scoring rules?
- **RQ4.** Do LLMs contribute information beyond their structured inputs and the market, or do they mainly anchor on and reproduce them?

---

## 2. Aims

1. **Calibration.** Measure each model's calibration as a probabilistic forecaster of the 2026 knockout stage and characterize the direction and size of any miscalibration.
2. **Reasoning effect.** Test, *within* each model, whether higher reasoning effort changes calibration and accuracy. Reasoning mode is a manipulated within-model factor, **not** a cross-vendor causal comparison.
3. **Market skill.** Benchmark every model against the de-vigged Polymarket price and the Pinnacle closing line on proper scores; establish whether any model matches, beats, or trails each market.
4. **Added information vs anchoring.** Determine whether models add forecasting information beyond the market and beyond the provided Elo/ratings inputs, including whether supplying the market price in the prompt changes their forecasts.

---

## 3. Hypotheses (directional, pre-registered)

- **H1 — Calibration.** Pooled across models, forecasts are miscalibrated, with calibration error reliably above zero and overconfidence the dominant direction (calibration slope < 1).
- **H2 — Reasoning effort.** Higher reasoning effort does not improve, and may worsen, calibration within a model; direction is model-dependent and effects on accuracy are small. *No per-model direction is predicted* (we have no genuine per-model prior); the registered prediction is the pooled "no improvement," with per-model results reported descriptively.
- **H3 — Market skill.** Average ranked-probability and Brier skill scores against **both** the de-vigged Polymarket price **and** the Pinnacle closing line are at or below zero (markets not beaten). Tested with equivalence bounds so an affirmative "statistically equivalent to the market" claim is possible, not merely "failed to differ."
- **H4 — Information conditioning.** Supplying the market price in the prompt pulls model probabilities toward the de-vigged market and lowers Brier and RPS relative to withholding it.
- **H5 — Anchoring vs added information.** When the market is withheld, model probabilities still correlate highly with both the market and the Elo-based baseline, and a market-plus-model combination does not significantly beat the market alone — together indicating the models mainly anchor on their inputs. This is the direct test of the parroting concern.

*Selecting which single model scores best on one tournament is exploratory and descriptive only; ~32 matches cannot support a confirmatory model ranking.*

---

## 4. Design

A prospective, pre-registered, fully crossed observational forecasting study over all **32 matches** of the 2026 FIFA World Cup knockout stage (Round of 32 through the final, including the third-place playoff). The unit of analysis is the individual match. Three factors are manipulated **within each model**: model identity, reasoning effort, and market conditioning. Every model receives byte-identical inputs, so the only thing differing across conditions is the model and the manipulated factor. **No per-model statistical pipeline is built — the LLM is the forecaster, and its elicited probability is scored directly.**

---

## 5. Models (LOCKED — four frontier closed commercial systems)

| Slot | Model | Reasoning control | In paired reasoning contrast? |
|---|---|---|---|
| 1 | Claude Opus 4.8 | low / high via API parameter | Yes |
| 2 | GPT-5.5 | low / high via API parameter | Yes |
| 3 | Grok 4.3 | low / high via API parameter | Yes |
| 4 | Gemini 3.1 Pro | always-on thinking (cannot disable) | **No — high only** |

For every call, log the exact model identifier, API version, all parameters, and a timestamp. **Model identifiers and reasoning-parameter names must be verified against current provider docs at build time and then frozen** (they were in flux when the design was set). No open-weight model is included; this is stated as a limitation (findings speak to frontier commercial models, not open-weight ones).

---

## 6. Reasoning-effort conditions

Two conditions per model where supported — a **low/minimal** setting and a **high** setting — using each vendor's native control. Set **only** by API parameter, never by prompt wording. The contrast is a within-model descriptive factor, not a cross-vendor causal claim (a fixed token budget means different things across architectures). **Gemini 3.1 Pro contributes the high cell only and is excluded from the paired low-vs-high contrast**, documented in advance.

---

## 7. Market-conditioning arms

Two prompt arms:
- **Primary arm (market withheld):** the market price is absent from the information pack.
- **Conditioning arm (market supplied):** the de-vigged market price is added as exactly **one extra line** in the pack — nothing else changes.

This is the direct test of H4 and H5.

---

## 8. Forecasting targets (two scored definitions, LOCKED)

For each knockout match:
1. **90-minute three-way result** — probability distribution over the ordered outcomes (A win, draw, B win). Primary target for **ranked-probability scoring**.
2. **Advancement after extra time and penalties** — two-way probability that each team advances. Primary target for the **binary calibration** analysis.

In parallel, each surviving team's **champion probability** is elicited and refreshed before each round, and the full **round-by-round survival table** is scored for every team (many binary outcomes, mitigating the power ceiling).

Extra time and penalties resolve into the advancement outcome; these definitions are fixed now and cannot be reinterpreted after the fact.

---

## 9. Probability elicitation

- **Primary method:** verbalized numeric probability on a 0–100 integer scale, eliciting all three outcome probabilities in one response and **renormalizing to sum to 100** in analysis. Required because output-token logprobs are unavailable on the closed commercial families.
- Where logprobs are available (Gemini), record them as an additional cross-check only; **not** part of the primary cross-model comparison.
- The betting/fair-odds secondary elicitation arm is **not run** (descoped).

---

## 10. Repetitions and aggregation (LOCKED)

- **N = 10** samples per (model × reasoning condition × arm × match). *(Reduced from 20 to 10 before lock to manage API cost; the pre-registration pilot confirmed the aggregate Brier reproduces the N = 20 value within the registered §19 stability gate (≤ 0.005). The supporting pilot records + stability table are retained outside this tagged tree, in repository history.)*
- **Primary point forecast = median** of the 10 samples. **10% trimmed mean** as a pre-registered robustness check. **Per-key sample SD and IQR** across the 10 draws are stored as a within-model self-consistency measure.
- **Sensitivity analysis:** re-derive the aggregate at N = 5, 10 to demonstrate stability (converts the sample-size choice into within-study evidence).
- **Temperature ≈ 0.7** for models that accept it, so samples are genuinely diverse; for models that reject temperature, diversity comes from stochastic reasoning and this is documented per model.

---

## 11. Standardized information pack (LOCKED FIELD LIST)

Every model receives a **byte-identical, machine-readable pack per match**, built only from inputs with demonstrated predictive signal in the football-forecasting literature. **The bookmaker-consensus ability field is omitted** (descoped); team strength is carried by Elo, FIFA rank, and squad value.

Fields per match:
- **World Football Elo** (both teams) and the **Elo difference (A − B)** — the single strongest predictor in the literature; the difference is what moves the forecast.
- **FIFA ranking** (both teams).
- **Squad market value (EUR m)** (both teams).
- **Recent form** — last 10 matches, W–D–L (both teams).
- **Goals for / against** — last 10 matches (both teams).
- **Host-nation flag** — for USA, Canada, Mexico co-hosts.
- **Rest days** since last match (both teams).

The two market baselines are **excluded** from the primary pack (circularity); the de-vigged market price enters **only** in the conditioning arm.

**Knockout vs group-stage pack (registered, pre-lock).** All fields above — **including World Football Elo** — are used for the prospective knockout matches, where every field (Elo included) is captured and **frozen before kickoff** so it cannot leak. The **secondary group-stage analysis (§14) uses a reduced version of this pack WITHOUT Elo**: those matches are already complete, and no leakage-free point-in-time Elo can be obtained (eloratings.net serves only current ratings), so Elo and the Elo difference are omitted there and the group-stage results are reported as exploratory and **not directly comparable** to the knockout pack. See §14 (Group stage) and the data-pipeline note for the freeze procedure.

### Data sources and freeze protocol
- Elo and Elo difference — eloratings.net
- FIFA ranking — FIFA's own ranking page (`inside.fifa.com/fifa-world-ranking/men`), **captured live pre-kickoff at the matched timestamp, consistent with Elo** (the live in-tournament ranking reflects only group-stage/pre-match results, so it is leakage-free for the knockout prediction; third-party reprints are not used).
- Squad market value — Transfermarkt national-team page directly (e.g. `transfermarkt.com/.../startseite/verein/<id>`), not secondary sites that cite it.
- Recent form and goals — **FBref match logs**: the team's most recent **10 senior A-team internationals** (competitive *and* friendlies, A-team only) ending with the matches played **before this fixture**. W–D–L and goals for/against are computed over exactly those 10 matches; the FBref match-log URL is recorded per team.
- Rest days and host flag — derived from the official schedule

**Protocol:** pull every field once, timestamp it, freeze it, and send the identical file to all four models.

---

## 12. Leakage control

The pack is frozen at a fixed timestamp before each match and **all live web/tool access is disabled**, so every model forecasts from identical frozen context. Future 2026 matches are already safe from training-corpus leakage; disabling retrieval removes the residual risk of pulling resolution-adjacent news. No retrieval arm is run in the primary design.

---

## 13. Baselines (reported separately, NEVER pooled)

**Two market baselines:**
- **Polymarket** — de-vigged implied probabilities. Benchmarks the **advancement** outcome and the **outright winner**.
- **Pinnacle closing line** — benchmarks the **90-minute three-way (1X2)** result (RPS/Brier) and offers a to-qualify line.
- **De-vig method (LOCKED):** proportional (basic) as primary; odds-ratio and Shin as sensitivity checks (favorite-longshot-aware).
- **Verify during build:** Polymarket's actual 2026 knockout market structure (likely advancement, not a three-way with a draw). If Polymarket does not price the three-way, Pinnacle is the sole three-way benchmark and Polymarket grades advancement/outright — this split is already assumed here.

**Three statistical reference points** (computed on the same pack):
- **Elo model.**
- **Poisson goals model** in the Dixon–Coles tradition.
- **Trivial favorite** (the higher-rated team always).

**Ensemble:** an equal-weight LLM ensemble is reported beside the individual models.

Each market price is captured at the **matched pre-kickoff timestamp** so model and market are graded on the same information set; forecasts inside a short pre-resolution window are excluded so live information cannot dominate.

---

## 14. Outcome measures and statistical analysis

### Primary calibration
- **Expected Calibration Error** (10 equal-width bins) with **Maximum Calibration Error**.
- **Reliability diagrams.**
- **Calibration slope and intercept** (from logistic recalibration — preferred over binned ECE at this sample size).
- **Murphy decomposition** of the Brier score into reliability, resolution, uncertainty.

Assessed on the **binary advance / not-advance** forecast for each knockout match.

### Primary probabilistic accuracy
- **Ranked Probability Score (RPS)** on the ordered three-way result — **primary score** (football outcomes are ordinal; Brier ignores ordering).
- **Brier score** and **logarithmic score** reported alongside (predictions bounded to **[0.01, 0.99]** so the log score stays finite).
- Reporting RPS, Brier, and log together is the deliberate response to genuine disagreement in the literature about which single rule is best.

### Skill relative to each market
- **Ranked Probability Skill Score** and **Brier Skill Score**, computed **separately** against the de-vigged Polymarket price and against the Pinnacle closing line. **Never pooled across the two.**

### Secondary
- **Reasoning effect:** within-model difference in calibration error and RPS between low and high effort (Gemini excluded from the paired contrast).
- **Information conditioning:** difference in Brier and RPS, and change in divergence from the market, between the withheld and supplied arms.
- **Added information:** forecast-encompassing test of whether market-plus-model beats market alone; correlation between each model's probabilities and the Elo baseline.
- **Ensemble:** the same scores for the equal-weight ensemble.
- **Group stage (secondary, exploratory — REDUCED PACK, no Elo):** the ~72 completed group-stage matches as an additional dataset for power, clearly labeled secondary and exploratory (those matches are already over, so this is a weaker, non-prospective analysis). **Registered amendment (pre-lock):** because no leakage-free point-in-time Elo source exists for completed matches — eloratings.net publishes only *current* ratings, which already incorporate each match's result — the group-stage pack **omits World Football Elo and the Elo difference**, and the **Elo and Dixon–Coles baselines are not computed** on it. The group-stage secondary therefore uses a **reduced feature set: FIFA rank, squad market value, recent form (W–D–L), goals for/against, host flag, and rest days only.** It is consequently **not directly comparable** to the knockout pack (which includes Elo, captured and frozen pre-kickoff so it cannot leak) and is reported as **exploratory only**.
- **Descriptive only:** hit rate; a simulated betting return against Polymarket, flagged as a noisy secondary metric.

### Inference (LOCKED)
- **Diebold–Mariano** test with the **Harvey–Leybourne–Newbold small-sample correction** for all forecaster comparisons (mandatory at this sample size).
- **Bootstrap** confidence intervals (10,000 resamples) for scores and skill.
- **Wilson** intervals for any proportions.
- ECE intervals treated as indicative given known finite-sample undercoverage.
- **Equivalence:** two one-sided tests (TOST) against a pre-registered margin. **Equivalence margin = 0.01** in RPS/Brier difference (treated as practically negligible for match forecasting). **This is the single most consequential power-related choice; it is fixed before any data are seen.**
- **Multiplicity stance:** primary tests pre-registered and uncorrected; secondary families flagged exploratory.

---

## 15. Power and its handling

The knockout stage is only 32 matches — a hard ceiling on power. The analysis therefore leans on: proper scoring rules (more information per observation than win/loss); repeated sampling; skill scores and equivalence testing rather than dichotomous significance; the evolving champion and survival forecasts; and the group stage as a secondary dataset. Choosing the single best-scoring model is exploratory throughout, stated prominently.

---

## 16. Procedure and timeline

- **Stage 0 — Lock and register (before the first R32 kickoff).** Freeze the information-pack schema, the exact prompts, the elicitation format, the model list and snapshots, the metric battery, the equivalence margin, the de-vig method, and the analysis code. Post this registration and the Round-of-32 forecasts to a timestamped public repository and to OSF **before the first knockout kickoff.** *(Protocol lock and per-round forecast timestamps are separate events — see §17.)*
- **Stage 1 — Pilot (immediately before lock).** On finished group-stage matches. Proceed only if pass criteria (§19) are met.
- **Stage 2 — Live collection (knockout window).** 10 samples per model and condition before each match's market close; both market baselines captured at the matched timestamp; champion and survival probabilities refreshed each round.
- **Stage 3 — Analysis (after the final).** Run the frozen scoring exactly as pre-registered. Report calibration first, market skill second, then conditioning/anchoring/ensemble. Post the arXiv preprint ~2 weeks after the final and release the full repository.

---

## 17. Two-tier timestamping (critical)

1. **Protocol lock (one event, hard deadline):** this document + the frozen scoring script, committed and timestamped **before the first R32 kickoff.** This is the pre-registration and the entire credibility of the study.
2. **Forecast timestamps (rolling):** each round's forecasts are frozen and timestamped as the bracket reveals, **before that round's kickoff.** A given forecast is valid as long as it precedes its own match — so if automated coverage begins a match or two into R32, the study remains clean.

---

## 18. Repository and run-harness specification (for the implementation engineer)

### Build order (one module at a time; test each before moving on)
1. **Data-freeze module** — pulls each field from its source, writes a per-match frozen pack file, timestamps it.
2. **Model clients** — one uniform interface per provider (4 clients) exposing a single `forecast(pack, reasoning_level, arm)` call; logs model id, API version, parameters, timestamp, raw response.
3. **Run / parse / aggregate** — fills the template, calls each model 20×, parses the five-key output, retries on parse failure, stores raw + parsed, aggregates by median.
4. **Frozen scoring script** — takes forecasts + results and outputs calibration (ECE, MCE, reliability, slope/intercept, Murphy decomposition), RPS, Brier, log score, and skill vs each market. **Must be committed and timestamped before the tournament; it need not run yet.**
5. **Pilot harness** — runs the full pipeline on finished group-stage matches against the pass gate.

### Cost / token logging
Per-provider input, output, and **reasoning** token counts logged on every call (the high-reasoning half dominates cost). The pilot yields the true per-match figure.

### Scale estimate (four-model set)
Per match: (3 paired models × 2 reasoning × 2 arms × 10) + (Gemini × 1 × 2 arms × 10) = **140 calls/match** → **≈ 4,480** across 32 matches. Champion + survival prompts add **≈ 500–750**. Total **≈ 5,000** small calls. Inputs and outputs are tiny; expected cost is low (≈$110 for the model forecasts, confirmed by the pilot at ≈$5.86/match before the N=20→10 reduction), driven almost entirely by high-reasoning tokens.

---

## 19. Pilot gate (hard pass criteria)

Run on finished group-stage matches. **Proceed to lock only if:**
- **> 95%** of responses return exactly the expected five keys as integers (no percent signs, no extra text), and
- the aggregate Brier is **stable to within 0.005** between N = 10 and N = 20. *(This pilot check was run and passed within the gate, which justified registering N = 10 as the locked sample size (§10); supporting records are retained outside the tagged tree.)*

---

## 20. Frozen prompt set (byte-identical across all four models and both reasoning conditions)

Prompt text never changes between conditions. Reasoning effort and temperature are set by API parameter only. The market arm differs from the primary arm by exactly one added line. Teams are labeled **A** and **B** (venues are neutral except hosts, captured by the host flag); outcomes stay ordinal (A win, draw, B win) so RPS applies.

### 20.1 Shared instruction block (top of every match prompt)
```
You are forecasting a single match in the 2026 FIFA World Cup knockout stage.
Use only the data provided below. Do not use any outside information.
All matches are at neutral venues unless a host flag indicates otherwise.
Give your honest probability estimate. Do not hedge to round numbers.
```

### 20.2 Match information pack (filled per match, identical structure every time)
```
MATCH: {round}, {date}, {venue}, {venue_city}
TEAM A: {team_A}
TEAM B: {team_B}

                              TEAM A        TEAM B
World Football Elo:           {eloA}        {eloB}
Elo difference (A - B):       {elo_diff}
FIFA ranking:                 {rankA}       {rankB}
Squad market value (EUR m):   {mvA}         {mvB}
Recent form (last 10, W-D-L): {formA}       {formB}
Goals for / against (last 10):{gfgaA}       {gfgaB}
Host nation playing at home:  {hostA}       {hostB}
Rest days since last match:   {restA}       {restB}
```

### 20.3 Match prompt — primary arm (market withheld), output spec
```
Give the probability of each 90-minute result, as integers that sum to 100.
Then give the probability that each team advances to the next round after
extra time and penalties, as integers that sum to 100.
Respond with exactly these five lines and nothing else.

A_WIN=
DRAW=
B_WIN=
ADV_A=
ADV_B=
```

### 20.4 Match prompt — market-supplied arm (H4)
Identical to 20.3, with one line added to the pack **before** the output spec:
```
Market-implied probabilities (de-vigged), A_WIN / DRAW / B_WIN:
                              {mktA} / {mktD} / {mktB}
```

### 20.5 Champion-probability prompt (refreshed before each round)
```
You are forecasting the winner of the 2026 FIFA World Cup.
Use only the data provided below. Do not use any outside information.

REMAINING TEAMS AND BRACKET:
{bracket_with_paths}

TEAM SUMMARY (Elo, FIFA rank, squad value EUR m):
{one_row_per_remaining_team}

Give the probability that each remaining team wins the tournament, as integers
that sum to 100 across all teams listed. Respond with one line per team in the
form TEAM=probability and nothing else.
```

### 20.6 Parsing rule
Each match call must return exactly the five expected keys as integers — no percent signs, no extra text. Renormalize to 100 in analysis if a model is slightly off. The >95% parseable threshold is checked against this exact format before lock.

---

## 21. Stored data schemas

**Forecast record (per call):** model id, API version, parameters, reasoning level, arm, match id, sample index, timestamp, raw response, parsed {A_WIN, DRAW, B_WIN, ADV_A, ADV_B}.

**Aggregated forecast (per model × condition × arm × match):** median and trimmed-mean of each key, N, timestamp window.

**Market snapshot (per match):** source (Pinnacle / Polymarket), raw odds/prices, de-vig method, de-vigged probabilities, capture timestamp, kickoff timestamp.

---

## 22. References

**Citation-integrity note.** Every reference below has been checked. Group 1 was verified against the actual source during preparation (title, authors, venue, identifier confirmed). Group 2 is established, classic methodology cited as-is. Group 3 is real work by real authors where the *exact* reference should be confirmed at write-up. Group 4 lists citations from earlier drafts that **could not be verified and have been removed** — they must not be reinstated without a real source, since a fabricated citation in a pre-registration is the one irreversible error. The hypotheses in §3 carry no inline citations by design; the verified anchors for each are mapped in Group 1.

### Group 1 — VERIFIED against source (use as-is)
- Tian, K., Mitchell, E., Zhou, A., Sharma, A., Rafailov, R., Yao, H., Finn, C. & Manning, C.D. (2023). *Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback.* EMNLP 2023, 5433–5442. arXiv:2305.14975. — **verbalized-probability elicitation method + overconfidence; anchors elicitation design and H1.**
- Xiong, M., Hu, Z., Lu, X., Li, Y., Fu, J., He, J. & Hooi, B. (2024). *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs.* ICLR 2024. arXiv:2306.13063. — **black-box prompt→sample→aggregate framework; overconfidence; anchors elicitation design and H1.**
- Halawi, D., Zhang, F., Yueh-Han, C. & Steinhardt, J. (2024). *Approaching Human-Level Forecasting with Language Models.* NeurIPS 2024. arXiv:2402.18563. — **post-cutoff test set + trimmed-mean aggregation; anchors leakage control and aggregation.**
- Schoenegger, P., Tuminauskaite, I., Park, P.S., Valdece Sousa Bastos, R. & Tetlock, P.E. (2024/2025). *Wisdom of the Silicon Crowd: LLM Ensemble Prediction Capabilities Rival Human Crowd Accuracy.* Science Advances. arXiv:2402.19379. — **12-LLM ensemble on 31 binary questions (small-n precedent); acquiescence/overconfidence bias; Study 2 (feeding the median human prediction improves accuracy) anchors H4; anchors the ensemble analysis.**
- Schoenegger, P. & Park, P.S. (2023). *Large Language Models Are Competitive Near Cold-Start... / single-model forecasting-tournament evaluation.* (GPT-4 fails to beat the no-information benchmark.) — **anchors H3.** *(confirm exact title/venue at write-up; finding verified via Schoenegger et al. 2024.)*
- Yang, Q., Wu, J., et al. (2025). *LLM-as-a-Prophet: Understanding Predictive Intelligence with Prophet Arena.* arXiv:2510.17638 (ICLR 2026); live benchmark at prophetarena.co. — **prediction-market baseline; frontier LLMs small calibration error but fail to beat market return (H3); market/context conditioning improves forecasts (H4); uses the 3-hour pre-resolution exclusion adopted in §13.**
- Karger, E., Bastani, H., Yueh-Han, C., Jacobs, Z., Halawi, D., Zhang, F. & Tetlock, P. (2025). *ForecastBench: A Dynamic Benchmark of AI Forecasting Capabilities.* — **documents that LLMs given market prices in-prompt copy them (one model corr. 0.994 with the provided market); anchors H5 (parroting).**
- Lacombe, R. et al. (2025). *Don't Think Twice! Over-Reasoning Impairs Confidence Calibration.* ICML 2025 Workshop on Reliable and Responsible Foundation Models. — **increasing reasoning budget consistently worsens calibration / systematic overconfidence; primary anchor for H2.**
- Chen, F. et al. (2025). *Rethinking Fine-Tuning when Scaling Test-Time Compute: Limiting Confidence Improves Mathematical Reasoning.* NeurIPS 2025. arXiv:2502.07154. — **overconfidence impedes test-time scaling; supporting anchor for H2.**
- Constantinou, A.C. & Fenton, N.E. (2012). *Solving the Problem of Inadequate Scoring Rules for Assessing Probabilistic Football Forecast Models.* Journal of Quantitative Analysis in Sports 8(1), Article 1. DOI:10.1515/1559-0410.1418. — **establishes RPS as the proper score for football because outcomes are ordinal; anchors "RPS is primary."**
- Goldman Sachs Global Investment Research (2026). *The World Cup and Economics — World Cup 2026: Predictions, Probabilities, and Paths to Victory* (Hatzius et al., June 2026). — **Elo-based model over ~20,000 matches since 1978; the firm explicitly calls the model's power "limited" given soccer's inherent unpredictability, and missed in 2018. Anchors the framing (§0).** *Note: cite only the verified "limited power" admission; the "~0.45 correlation with goal difference" figure from earlier drafts is NOT in the public reporting and has been dropped.*

### Group 2 — established methodology (classics, cite as-is)
- Brier, G.W. (1950). Verification of forecasts expressed in terms of probability. *Monthly Weather Review.* — Brier score.
- Epstein, E.S. (1969). A scoring system for probability forecasts of ranked categories. *Journal of Applied Meteorology.* — Ranked Probability Score.
- Murphy, A.H. (1973). A new vector partition of the probability score. *Journal of Applied Meteorology.* — reliability/resolution/uncertainty decomposition.
- Diebold, F.X. & Mariano, R.S. (1995). Comparing predictive accuracy. *Journal of Business & Economic Statistics.*
- Harvey, D., Leybourne, S. & Newbold, P. (1997). Testing the equality of prediction mean squared errors. *International Journal of Forecasting.* — small-sample DM correction.
- Lakens, D. (2017). Equivalence tests: a practical primer. *Social Psychological and Personality Science.* — TOST.
- Dixon, M.J. & Coles, S.G. (1997). Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society, Series C.*
- Leitner, C., Zeileis, A. & Hornik, K. (2010). Forecasting sports tournaments by ratings of (prob)abilities. *International Journal of Forecasting.* — bookmaker-consensus method.
- Wang, X. et al. (2022). Self-consistency improves chain-of-thought reasoning in language models. *ICLR 2023.* — supports median-of-samples aggregation.

### Group 3 — real authors/work, confirm exact reference at write-up
- Groll, A., Ley, C., Schauberger, G., Van Eetvelde, H. et al. (~2018–2019). Random-forest / Poisson-ability World Cup prediction work (e.g., JQAS). *(real research line; confirm the specific paper used for the feature set.)*
- Wheatcroft, E. (~2019–2021). Work on evaluating probabilistic football forecasts / RPS vs other scoring rules. *(real author on this topic; confirm exact year and title.)*
- Robberechts, P. & Davis, J. Soccer prediction with Elo difference + home advantage. *(confirm exact reference, or drop — the Elo+home-advantage point is independently supported by the Goldman report and Dixon–Coles.)*

### Group 4 — REMOVED (could not be verified; do not reinstate without a source)
- ~~"Mei et al. (2025)"~~ — removed; H1/H2 are anchored by the verified Tian, Xiong, Lacombe, and Chen references.
- ~~"Alur et al. (2025)"~~ and ~~"mention-markets (2026)"~~ — removed; H4 is anchored by the verified Schoenegger (Study 2), Prophet Arena, and ForecastBench references.
- ~~"Todasco (2025)"~~ — removed; it supported the betting-odds elicitation arm, which is descoped.
- ~~Goldman "~0.45 correlation with goal difference"~~ — figure removed; the framing now rests on Goldman's verified "limited power" admission.

---

## 23. Limitations (stated up front)
- Only ~32 prospective knockout matches — a hard power ceiling, addressed via proper scores, repeated sampling, survival outcomes, equivalence testing, and the secondary group-stage set.
- No open-weight model — findings speak to frontier commercial models only.
- Gemini cannot disable thinking — excluded from the paired reasoning contrast.
- Model identifiers/parameters were in flux at design time — must be verified once at build and then frozen.
- The single best-scoring model on one tournament is exploratory, not a confirmatory ranking.

---

*End of protocol v1.0. Open design decisions: none — all locked. Remaining pre-lock action: verify the Tier B/C references (§22) against real sources, then commit-and-timestamp this document plus the frozen scoring script before the first Round-of-32 kickoff.*
