from analyze_item_timings import (
    NOISE_ITEM_KEYS,
    analyze,
    analyze_compare,
    ci95,
    enrich_rows,
    farm_bias_status,
    signal_status,
    timing_bucket,
)
from tests.test_transformer import make_raw_match
from src.ai_balancer.processing.transformer import transform_opendota_match


def test_timing_bucket_ranges():
    assert timing_bucket(-90) == "00-15"
    assert timing_bucket(14 * 60) == "00-15"
    assert timing_bucket(19 * 60) == "15-20"
    assert timing_bucket(24 * 60) == "20-25"
    assert timing_bucket(29 * 60) == "25-30"
    assert timing_bucket(39 * 60) == "30-40"
    assert timing_bucket(40 * 60) == "40+"


def test_analyze_skips_noise_but_keeps_real_items():
    match = transform_opendota_match(make_raw_match())  # has tango (-90), power_treads (300), black_king_bar (1200)
    rows = analyze([match])

    items = {row["item"] for row in rows}
    assert "tango" not in items            # starting item -> filtered
    assert "power_treads" in items         # real item stays
    assert "black_king_bar" in items
    assert "black_king_bar" not in NOISE_ITEM_KEYS


def test_analyze_group_controls_rank_and_timing_dimensions():
    match = transform_opendota_match(make_raw_match())

    rows = analyze([match], group="hero-item")
    bkb_rows = [row for row in rows if row["item"] == "black_king_bar"]
    assert bkb_rows
    assert {row["rank"] for row in bkb_rows} == {"all"}
    assert {row["timing"] for row in bkb_rows} == {"all"}

    rows = analyze([match], group="hero-item-rank-timing")
    bkb_rows = [row for row in rows if row["item"] == "black_king_bar"]
    assert bkb_rows
    assert {row["rank"] for row in bkb_rows} == {"legend"}
    assert {row["timing"] for row in bkb_rows} == {"20-25"}


def test_analyze_compare_splits_early_late_none():
    match = transform_opendota_match(make_raw_match())
    # all 10 fake players bought BKB at 1200s; threshold 21min => all early
    groups = analyze_compare([match], hero_id=1, item="black_king_bar", minute=21)
    assert groups["bought_early"]["games"] == 1
    assert groups["bought_late"]["games"] == 0
    assert groups["not_bought"]["games"] == 0

    # threshold below purchase time => late
    groups = analyze_compare([match], hero_id=1, item="black_king_bar", minute=15)
    assert groups["bought_early"]["games"] == 0
    assert groups["bought_late"]["games"] == 1

    # unknown item => not bought for everyone
    groups = analyze_compare([match], hero_id=1, item="nonexistent_item", minute=21)
    assert groups["not_bought"]["games"] == 1


def test_ci95_bounds():
    assert ci95(50, 100) > 0.0
    assert ci95(50, 10000) < ci95(50, 100)
    assert ci95(0, 0) == 0.0


def test_signal_status_and_enrichment():
    row = {
        "hero_id": 25,
        "item": "black_king_bar",
        "rank": "all",
        "timing": "all",
        "games": 200,
        "wr": 0.60,
        "ci": 0.03,
        "baseline": 0.50,
        "baseline_ci": 0.02,
        "baseline_games": 1000,
        "avg_gpm": 620,
        "baseline_avg_gpm": 500,
        "avg_early_gpm": 551,
        "baseline_avg_early_gpm": 500,
        "avg_net_worth": 25000,
        "baseline_avg_net_worth": 20000,
        "delta": 0.10,
    }

    assert signal_status(row) == "signal"
    enriched = enrich_rows([row], {25: "Lina"}, {"black_king_bar": "Black King Bar"})
    assert enriched[0]["hero"] == "Lina"
    assert enriched[0]["item"] == "Black King Bar"
    assert enriched[0]["status"] == "signal"
    assert enriched[0]["avg_gpm"] == 620
    assert enriched[0]["farm_bias"] == "high"


def test_farm_bias_status():
    assert farm_bias_status({"avg_early_gpm": 551, "baseline_avg_early_gpm": 500}) == "high"
    assert farm_bias_status({"avg_early_gpm": 526, "baseline_avg_early_gpm": 500}) == "medium"
    assert farm_bias_status({"avg_early_gpm": 510, "baseline_avg_early_gpm": 500}) == "low"
    assert farm_bias_status({"avg_early_gpm": 440, "baseline_avg_early_gpm": 500}) == "negative"


def test_analyze_includes_early_gpm_context():
    match = transform_opendota_match(make_raw_match())  # gold_t[10]=2200 -> early_gpm=220.0
    rows = analyze([match])
    bkb_rows = [row for row in rows if row["item"] == "black_king_bar"]
    assert bkb_rows
    assert bkb_rows[0]["avg_early_gpm"] == 220.0
    assert bkb_rows[0]["baseline_avg_early_gpm"] == 220.0
