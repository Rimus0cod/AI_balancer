from generate_item_report import group_by_hero, write_markdown


def make_row(hero, item, delta, status="signal", games=100):
    return {
        "hero_id": 1,
        "hero": hero,
        "item_key": item,
        "item": item,
        "rank": "all",
        "timing": "all",
        "games": games,
        "wr": 0.6,
        "ci95": 0.05,
        "baseline_wr": 0.5,
        "baseline_games": 10000,
        "baseline_ci95": 0.01,
        "delta": delta,
        "avg_gpm": 500,
        "baseline_avg_gpm": 480,
        "avg_early_gpm": 250,
        "baseline_avg_early_gpm": 240,
        "avg_net_worth": 15000,
        "baseline_avg_net_worth": 14000,
        "status": status,
        "farm_bias": "low",
    }


def test_group_by_hero_sorts_items_and_heroes():
    rows = [
        make_row("Lina", "yasha", 0.10),
        make_row("Lina", "aghanims_scepter", 0.12),
        make_row("Pudge", "blink", 0.08),
    ]

    by_hero = group_by_hero(rows)

    assert list(by_hero.keys()) == ["Lina", "Pudge"]
    assert [row["item"] for row in by_hero["Lina"]] == ["aghanims_scepter", "yasha"]


def test_write_markdown_creates_readable_report(tmp_path):
    rows = [make_row("Rubick", "blink", 0.10)]
    by_hero = group_by_hero(rows)
    path = tmp_path / "report.md"

    write_markdown(by_hero, path, top_per_hero=5, matches_count=89149, min_games=50)

    content = path.read_text(encoding="utf-8")
    assert "# Per-Hero Item Recommendations" in content
    assert "## Rubick" in content
    assert "| blink | 100 | 60.0% | +10.0pp | 250 | 240 | low | signal |" in content
