"""Offline tests for the per-match Polymarket parsers (§13 + AMENDMENT_001).

Fixtures mirror the live Gamma `public-search` payload shape captured pre-kickoff
for R32 match 73 (South Africa vs Canada), 2026-06-28 16:51Z. Pure parsers; no
network. The expected de-vigged values match the archived prices.
"""
import pytest

from src.markets import polymarket as PM

# --- per-match 3-way event (A = South Africa, B = Canada) — real archived Yes prices ---
MATCH_EVENT = {
    "title": "South Africa vs. Canada", "slug": "fifwc-rsa-can-2026-06-28",
    "markets": [
        {"question": "Will Canada win on 2026-06-28?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.555", "0.445"],
         "lastTradePrice": 0.56, "bestBid": 0.55, "bestAsk": 0.56, "volume": 12930397.4},
        {"question": "Will South Africa win on 2026-06-28?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.165", "0.835"],
         "lastTradePrice": 0.17, "bestBid": 0.16, "bestAsk": 0.17, "volume": 1338649.6},
        {"question": "Will South Africa vs. Canada end in a draw?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.275", "0.725"],
         "lastTradePrice": 0.28, "bestBid": 0.27, "bestAsk": 0.28, "volume": 1549178.2},
    ],
}

# --- advancement event: 'Nation To Reach Round of 16' (real archived Yes prices) ---
REACH_R16_EVENT = {
    "title": "World Cup: Nation To Reach Round of 16",
    "slug": "world-cup-nation-to-reach-round-of-16",
    "markets": [
        {"question": "Will South Africa reach the Round of 16 at the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.247", "0.753"]},
        {"question": "Will Canada reach the Round of 16 at the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.755", "0.245"]},
        {"question": "Will Brazil reach the Round of 16 at the 2026 FIFA World Cup?",
         "outcomes": ["Yes", "No"], "outcomePrices": ["0.98", "0.02"]},   # ignored (other team)
    ],
}

SEARCH = {"events": [MATCH_EVENT, REACH_R16_EVENT]}
A, B = "South Africa", "Canada"


def test_parse_match_3way_orders_AB_and_draw():
    raw = PM.parse_match_3way(MATCH_EVENT, A, B)
    assert raw == {"A_win": pytest.approx(0.165), "draw": pytest.approx(0.275),
                   "B_win": pytest.approx(0.555)}


def test_devig_3way_proportional_matches_archive():
    raw = PM.parse_match_3way(MATCH_EVENT, A, B)
    dv = PM.devig_match_3way(raw, method="proportional")
    assert sum(dv.values()) == pytest.approx(1.0)
    assert dv["A_WIN"] == pytest.approx(0.166, abs=1e-3)
    assert dv["DRAW"] == pytest.approx(0.276, abs=1e-3)
    assert dv["B_WIN"] == pytest.approx(0.558, abs=1e-3)


def test_parse_advancement_pair_picks_the_two_teams():
    raw = PM.parse_advancement_pair(REACH_R16_EVENT, A, B)
    assert raw == {"A": pytest.approx(0.247), "B": pytest.approx(0.755)}


def test_devig_advancement_complementary():
    raw = PM.parse_advancement_pair(REACH_R16_EVENT, A, B)
    dv = PM.devig_advancement(raw, method="proportional")
    assert dv["ADV_A"] + dv["ADV_B"] == pytest.approx(1.0)
    assert dv["ADV_A"] == pytest.approx(0.247, abs=1e-3)
    assert dv["ADV_B"] == pytest.approx(0.753, abs=1e-3)


def test_missing_leg_raises_not_fabricates():
    bad = {"markets": MATCH_EVENT["markets"][:2]}   # drop the draw market
    with pytest.raises(ValueError):
        PM.parse_match_3way(bad, A, B)


def test_json_string_arrays_supported():
    ev = {"markets": [
        {"question": "Will Canada win on 2026-06-28?",
         "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.555\", \"0.445\"]"},
        {"question": "Will South Africa win on 2026-06-28?",
         "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.165\", \"0.835\"]"},
        {"question": "Will it end in a draw?",
         "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.275\", \"0.725\"]"},
    ]}
    raw = PM.parse_match_3way(ev, A, B)
    assert raw["B_win"] == pytest.approx(0.555)


def test_build_benchmark_full_with_sensitivity():
    bench = PM.build_match_benchmark(SEARCH, A, B, next_round="Round of 16")
    tw = bench["three_way"]
    assert tw["captured"] is True and tw["event_slug"] == "fifwc-rsa-can-2026-06-28"
    # all three locked methods present
    assert set(tw["devigged"]) == {"proportional", "odds_ratio", "shin"}
    assert tw["devigged"]["proportional"]["B_WIN"] == pytest.approx(0.558, abs=1e-3)
    assert tw["overround_pct"] == pytest.approx(-0.5, abs=0.05)   # booksum 0.995
    # per-market provenance retained
    assert any("lastTradePrice" in pm for pm in tw["per_market"])
    adv = bench["advancement"]
    assert adv["captured"] is True and adv["next_round"] == "Round of 16"
    assert adv["devigged"]["proportional"]["ADV_B"] == pytest.approx(0.753, abs=1e-3)


def test_build_benchmark_honest_absence():
    bench = PM.build_match_benchmark({"events": []}, A, B, next_round="Round of 16")
    assert bench["three_way"]["captured"] is False
    assert bench["advancement"]["captured"] is False
