import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from configs.settings import settings
from src.ai_balancer.quality.dataset_summary import load_processed_matches
from src.ai_balancer.reference import hero_display_names, item_display_names
from analyze_item_timings import analyze, enrich_rows


def select_rows(matches, min_games: int, include_unclear: bool):
    rows = analyze(matches, group="hero-item")
    filtered = [row for row in rows if row["games"] >= min_games]
    enriched = enrich_rows(filtered, hero_display_names(), item_display_names())
    allowed = {"signal"} if not include_unclear else {"signal", "unclear"}
    return [row for row in enriched if row["status"] in allowed]


def group_by_hero(rows: list[dict]) -> dict[str, list[dict]]:
    by_hero: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_hero[row["hero"]].append(row)
    for items in by_hero.values():
        items.sort(key=lambda r: r["delta"], reverse=True)
    return dict(sorted(by_hero.items(), key=lambda kv: kv[1][0]["delta"], reverse=True))


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def format_pct(value) -> str:
    return f"{value * 100:.1f}%" if value is not None else "-"


def write_markdown(by_hero: dict[str, list[dict]], path: Path, top_per_hero: int,
                   matches_count: int, min_games: int) -> None:
    lines = [
        "# Per-Hero Item Recommendations",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"Dataset: {matches_count} ranked matches; minimum {min_games} games per hero-item cell.",
        "",
        "Winrate deltas are versus the same hero's overall winrate in the dataset.",
        "`egpm10` / `ebase` = pre-purchase GPM by minute 10 of buyers vs hero baseline;",
        "`bias` flags whether buyers were already farming better before buying",
        "(low/negative = cleaner, medium/high = interpret with care).",
        "",
    ]

    for hero, items in by_hero.items():
        best_status = items[0]["status"]
        header_suffix = "" if best_status == "signal" else " *(no statistically separated signals yet)*"
        lines.append(f"## {hero}{header_suffix}")
        lines.append("")
        lines.append("| item | games | wr | delta | egpm10 | ebase | bias | status |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for row in items[:top_per_hero]:
            lines.append(
                f"| {row['item']} | {row['games']} | {format_pct(row['wr'])} "
                f"| {row['delta'] * 100:+.1f}pp | {row['avg_early_gpm'] or 0:.0f} "
                f"| {row['baseline_avg_early_gpm'] or 0:.0f} | {row['farm_bias']} | {row['status']} |"
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate per-hero item recommendation reports")
    parser.add_argument("--processed-dir", default=settings.RANKED_PROCESSED_DATA_DIR)
    parser.add_argument("--min-games", type=int, default=50)
    parser.add_argument("--top-per-hero", type=int, default=5)
    parser.add_argument("--signal-only", action="store_true",
                        help="Include only statistically separated signal rows")
    parser.add_argument("--output-prefix", default="reports/item_recommendations",
                        help="Path prefix; .csv and .md are appended")
    args = parser.parse_args()

    matches = load_processed_matches(args.processed_dir)
    if not matches:
        print("No processed matches found")
        return

    rows = select_rows(matches, args.min_games, include_unclear=not args.signal_only)
    by_hero = group_by_hero(rows)

    signal_count = sum(1 for row in rows if row["status"] == "signal")
    print(f"Processed matches: {len(matches)}")
    print(f"Heroes with recommendations: {len(by_hero)}")
    print(f"Rows kept: {len(rows)} (signals={signal_count}, unclear={len(rows) - signal_count})")

    prefix = Path(args.output_prefix)
    csv_path = prefix.with_suffix(".csv")
    md_path = prefix.with_suffix(".md")

    write_csv(rows, csv_path)
    write_markdown(by_hero, md_path, args.top_per_hero, len(matches), args.min_games)
    print(f"Saved: {csv_path}")
    print(f"Saved: {md_path}")


if __name__ == "__main__":
    main()
