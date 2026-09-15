import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict

from configs.settings import settings
from src.ai_balancer.ingestion.opendota import rank_bucket
from src.ai_balancer.quality.dataset_summary import load_processed_matches
from src.ai_balancer.reference import hero_display_names, item_display_names

STARTING_ITEM_KEYS = {
    "tango", "branches", "blood_grenade", "faerie_fire", "magic_stick", "magic_wand",
    "clarity", "flask", "enchanted_mango", "ward_observer", "ward_sentry", "tpscroll",
    "smoke_of_deceit", "circlet", "gauntlets_of_strength", "mantle_of_intelligence",
    "slippers_of_agility", "sobi_mask", "ring_of_basilius", "robe", "null_talisman",
    "wraith_band", "bracer", "dagger", "buckler", "boots", "mantle", "quelling_blade",
}

COMPONENT_ITEM_KEYS = {
    "point_booster", "blade_of_alacrity", "staff_of_wizardry", "robe_of_magi",
    "ogre_axe", "belt_of_strength", "band_of_elvenskin", "boots_of_elves",
    "chainmail", "platemail", "helm_of_iron_will", "broadsword", "claymore",
    "mithril_hammer", "javelin", "quarterstaff", "vitality_booster", "energy_booster",
    "mystic_staff", "reaver", "eagle", "ghost_scepter", "demon_edge", "sacred_relic",
    "void_stone", "pers", "ring_of_health", "ring_of_regen", "ring_of_tarrasque",
    "spirit_vessel_recipe", "orb_of_corrosion_recipe", "cornucopia", "fluffy_hat",
    "diadem", "gauntlets", "ring_of_protection", "blades_of_attack", "gloves",
    "wind_lace", "splintmail", "blitz_knuckles", "blight_stone", "orb_of_venom",
}

NOISE_ITEM_KEYS = STARTING_ITEM_KEYS | COMPONENT_ITEM_KEYS

GROUPS = {
    "hero-item": (False, False),
    "hero-item-rank": (True, False),
    "hero-item-timing": (False, True),
    "hero-item-rank-timing": (True, True),
}


def timing_bucket(seconds: int) -> str:
    minutes = max(0, seconds) / 60
    if minutes < 15:
        return "00-15"
    if minutes < 20:
        return "15-20"
    if minutes < 25:
        return "20-25"
    if minutes < 30:
        return "25-30"
    if minutes < 40:
        return "30-40"
    return "40+"


def ci95(wins: int, games: int) -> float:
    if games == 0:
        return 0.0
    p = wins / games
    return 1.96 * math.sqrt(p * (1 - p) / games)


def signal_status(row: dict, min_signal_games: int = 100) -> str:
    if row["games"] < min_signal_games:
        return "thin"
    combined_ci = row["ci"] + row["baseline_ci"]
    if abs(row["delta"]) > combined_ci:
        return "signal"
    return "unclear"


def farm_bias_status(row: dict) -> str:
    """Winning-state bias check based on PRE-purchase farm (GPM at minute 10).

    Final GPM is deliberately not used here: farm-accelerating items (Maelstrom,
    Yasha, Battle Fury...) legitimately raise final GPM of buyers, so it is an
    outcome of the item as much as a confounder. Early GPM measures the state
    before most core purchases.
    """
    avg_gpm = row.get("avg_early_gpm")
    baseline_gpm = row.get("baseline_avg_early_gpm")
    if avg_gpm is None or baseline_gpm is None or baseline_gpm <= 0:
        return "unknown"

    diff = avg_gpm - baseline_gpm
    relative = diff / baseline_gpm
    if diff >= 50 or relative >= 0.10:
        return "high"
    if diff >= 25 or relative >= 0.05:
        return "medium"
    if diff <= -50 or relative <= -0.10:
        return "negative"
    return "low"


def signal_sort_key(row: dict):
    status_score = {"signal": 2, "unclear": 1, "thin": 0}[signal_status(row)]
    return (status_score, abs(row["delta"]), row["games"])


def add_farm(stats: dict, player) -> None:
    if player.gpm is not None:
        stats["gpm_sum"] += player.gpm
        stats["gpm_count"] += 1
    if player.net_worth is not None:
        stats["net_worth_sum"] += player.net_worth
        stats["net_worth_count"] += 1
    if player.early_gpm is not None:
        stats["early_gpm_sum"] += player.early_gpm
        stats["early_gpm_count"] += 1


def avg_or_none(total: float, count: int):
    return total / count if count else None


def normalize_group(group: str, all_ranks: bool) -> str:
    if not all_ranks:
        return group
    if group == "hero-item-rank":
        return "hero-item"
    if group == "hero-item-rank-timing":
        return "hero-item-timing"
    return group


def analyze(
    matches,
    group: str = "hero-item",
    skip_noise: bool = True,
    all_ranks: bool = False,
    filter_hero_id: int | None = None,
    filter_item: str | None = None,
    filter_rank: str | None = None,
):
    group = normalize_group(group, all_ranks)
    include_rank, include_timing = GROUPS[group]
    baseline_totals = defaultdict(lambda: {
        "games": 0,
        "wins": 0,
        "gpm_sum": 0,
        "gpm_count": 0,
        "early_gpm_sum": 0,
        "early_gpm_count": 0,
        "net_worth_sum": 0,
        "net_worth_count": 0,
    })
    item_stats = defaultdict(lambda: {
        "games": 0,
        "wins": 0,
        "gpm_sum": 0,
        "gpm_count": 0,
        "early_gpm_sum": 0,
        "early_gpm_count": 0,
        "net_worth_sum": 0,
        "net_worth_count": 0,
    })

    for match in matches:
        rb = rank_bucket(match.avg_rank_tier)
        if filter_rank and rb != filter_rank:
            continue
        rank_key = rb if include_rank else "all"
        for player in match.players:
            if filter_hero_id is not None and player.hero_id != filter_hero_id:
                continue
            won = match.radiant_win if player.team == 0 else not match.radiant_win
            baseline_key = (player.hero_id, rank_key)
            baseline_totals[baseline_key]["games"] += 1
            baseline_totals[baseline_key]["wins"] += int(won)
            add_farm(baseline_totals[baseline_key], player)

            seen_items = set()
            for purchase in sorted(player.purchases, key=lambda p: p.time):
                item = purchase.item_name
                if filter_item is not None and item != filter_item:
                    continue
                if item in seen_items:
                    continue
                if skip_noise and item in NOISE_ITEM_KEYS:
                    continue
                timing_key = timing_bucket(purchase.time) if include_timing else "all"
                item_key = (player.hero_id, item, rank_key, timing_key)
                item_stats[item_key]["games"] += 1
                item_stats[item_key]["wins"] += int(won)
                add_farm(item_stats[item_key], player)
                seen_items.add(item)

    rows = []
    for (hero_id, item, rank, timing), stats in item_stats.items():
        games = stats["games"]
        wins = stats["wins"]
        baseline_stats = baseline_totals[(hero_id, rank)]
        baseline_games = baseline_stats["games"]
        baseline_wins = baseline_stats["wins"]
        baseline = baseline_wins / baseline_games if baseline_games else 0.0
        wr = wins / games
        rows.append({
            "hero_id": hero_id,
            "item": item,
            "rank": rank,
            "timing": timing,
            "games": games,
            "wr": wr,
            "delta": wr - baseline,
            "baseline": baseline,
            "ci": ci95(wins, games),
            "baseline_ci": ci95(baseline_wins, baseline_games),
            "baseline_games": baseline_games,
            "avg_gpm": avg_or_none(stats["gpm_sum"], stats["gpm_count"]),
            "baseline_avg_gpm": avg_or_none(baseline_stats["gpm_sum"], baseline_stats["gpm_count"]),
            "avg_early_gpm": avg_or_none(stats["early_gpm_sum"], stats["early_gpm_count"]),
            "baseline_avg_early_gpm": avg_or_none(
                baseline_stats["early_gpm_sum"], baseline_stats["early_gpm_count"]
            ),
            "avg_net_worth": avg_or_none(stats["net_worth_sum"], stats["net_worth_count"]),
            "baseline_avg_net_worth": avg_or_none(
                baseline_stats["net_worth_sum"], baseline_stats["net_worth_count"]
            ),
        })
    return rows


def analyze_compare(matches, hero_id: int, item: str, minute: float,
                    rank: str | None = None) -> Dict[str, dict]:
    threshold = minute * 60
    groups = {name: {
        "games": 0,
        "wins": 0,
        "gpm_sum": 0,
        "gpm_count": 0,
        "early_gpm_sum": 0,
        "early_gpm_count": 0,
        "net_worth_sum": 0,
        "net_worth_count": 0,
    } for name in ("bought_early", "bought_late", "not_bought")}

    for match in matches:
        rb = rank_bucket(match.avg_rank_tier)
        if rank and rb != rank:
            continue
        for player in match.players:
            if player.hero_id != hero_id:
                continue
            won = match.radiant_win if player.team == 0 else not match.radiant_win
            first_time = None
            for purchase in sorted(player.purchases, key=lambda p: p.time):
                if purchase.item_name == item:
                    first_time = purchase.time
                    break
            if first_time is None:
                group = "not_bought"
            elif first_time <= threshold:
                group = "bought_early"
            else:
                group = "bought_late"
            groups[group]["games"] += 1
            groups[group]["wins"] += int(won)
            add_farm(groups[group], player)

    for stats in groups.values():
        stats["wr"] = stats["wins"] / stats["games"] if stats["games"] else None
        stats["ci"] = ci95(stats["wins"], stats["games"]) if stats["games"] else None
        stats["avg_gpm"] = avg_or_none(stats["gpm_sum"], stats["gpm_count"])
        stats["avg_early_gpm"] = avg_or_none(stats["early_gpm_sum"], stats["early_gpm_count"])
        stats["avg_net_worth"] = avg_or_none(stats["net_worth_sum"], stats["net_worth_count"])
    return groups


def print_compare(groups: dict, hero_name: str, item_name: str, minute: float, rank: str | None) -> None:
    print(f"Hero: {hero_name} | Item: {item_name} | Threshold: minute {minute:.0f} | Rank: {rank or 'all'}")
    none_wr = groups["not_bought"]["wr"]
    for label in ("bought_early", "bought_late", "not_bought"):
        stats = groups[label]
        if stats["games"] == 0:
            print(f"  {label:<14}: no games")
            continue
        delta = ""
        if label != "not_bought" and none_wr is not None and stats["wr"] is not None:
            delta = f" delta={((stats['wr'] - none_wr) * 100):+.1f}pp"
        print(
            f"  {label:<14}: games={stats['games']:>6} wr={stats['wr'] * 100:5.1f}% "
            f"+-{stats['ci'] * 100:4.1f}pp "
            f"egpm10={stats['avg_early_gpm'] or 0:5.1f} nw={stats['avg_net_worth'] or 0:7.0f}{delta}"
        )


def enrich_rows(rows: list[dict], hero_names: dict[int, str], item_names: dict[str, str]) -> list[dict]:
    enriched = []
    for row in rows:
        enriched.append({
            "hero_id": row["hero_id"],
            "hero": hero_names.get(row["hero_id"], str(row["hero_id"])),
            "item_key": row["item"],
            "item": item_names.get(row["item"], row["item"]),
            "rank": row["rank"],
            "timing": row["timing"],
            "games": row["games"],
            "wr": row["wr"],
            "ci95": row["ci"],
            "baseline_wr": row["baseline"],
            "baseline_games": row["baseline_games"],
            "baseline_ci95": row["baseline_ci"],
            "delta": row["delta"],
            "avg_gpm": row["avg_gpm"],
            "baseline_avg_gpm": row["baseline_avg_gpm"],
            "avg_early_gpm": row["avg_early_gpm"],
            "baseline_avg_early_gpm": row["baseline_avg_early_gpm"],
            "avg_net_worth": row["avg_net_worth"],
            "baseline_avg_net_worth": row["baseline_avg_net_worth"],
            "status": signal_status(row),
            "farm_bias": farm_bias_status(row),
        })
    return enriched


def write_report(rows: list[dict], output_path: str, output_format: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    fieldnames = [
        "hero_id", "hero", "item_key", "item", "rank", "timing", "games", "wr", "ci95",
        "baseline_wr", "baseline_games", "baseline_ci95", "delta", "avg_gpm", "baseline_avg_gpm",
        "avg_early_gpm", "baseline_avg_early_gpm",
        "avg_net_worth", "baseline_avg_net_worth", "status", "farm_bias",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Analyze item timing win rates")
    parser.add_argument("--processed-dir", default=settings.RANKED_PROCESSED_DATA_DIR)
    parser.add_argument("--group", default="hero-item", choices=sorted(GROUPS))
    parser.add_argument("--min-games", type=int, default=50)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--hero-id", type=int, default=None)
    parser.add_argument("--item", type=str, default=None)
    parser.add_argument("--minute", type=float, default=20.0)
    parser.add_argument("--rank", type=str, default=None,
                        choices=["herald", "guardian", "crusader", "archon", "legend", "ancient", "divine", "immortal"])
    parser.add_argument("--include-noise", action="store_true",
                        help="Include consumables and recipe components")
    parser.add_argument("--all-ranks", action="store_true",
                        help="Deprecated alias: remove rank dimension from the selected group")
    parser.add_argument("--compare", action="store_true",
                        help="Hero x item x minute comparison: early vs late vs not bought")
    parser.add_argument("--output", default=None, help="Optional report path")
    parser.add_argument("--format", default="csv", choices=["csv", "json"])
    parser.add_argument("--status", default="all", choices=["all", "signal", "unclear", "thin"],
                        help="Filter displayed/exported rows by signal status")
    parser.add_argument("--bias", default="all",
                        choices=["all", "low", "medium", "high", "negative", "unknown"],
                        help="Filter rows by pre-purchase farm bias")
    args = parser.parse_args()

    matches = load_processed_matches(args.processed_dir)
    hero_names = hero_display_names()
    item_names = item_display_names()

    if args.hero_id is not None and args.item and args.compare:
        groups = analyze_compare(matches, args.hero_id, args.item, args.minute, args.rank)
        print_compare(
            groups,
            hero_names.get(args.hero_id, str(args.hero_id)),
            item_names.get(args.item, args.item),
            args.minute,
            args.rank,
        )
        return

    rows = analyze(
        matches,
        group=args.group,
        skip_noise=not args.include_noise,
        all_ranks=args.all_ranks,
        filter_hero_id=args.hero_id,
        filter_item=args.item,
        filter_rank=args.rank,
    )
    filtered = [row for row in rows if row["games"] >= args.min_games]
    filtered.sort(key=signal_sort_key, reverse=True)
    enriched = enrich_rows(filtered, hero_names, item_names)
    if args.status != "all":
        enriched = [row for row in enriched if row["status"] == args.status]
    if args.bias != "all":
        enriched = [row for row in enriched if row["farm_bias"] == args.bias]

    print(f"Processed matches: {len(matches)}")
    print(f"Group: {normalize_group(args.group, args.all_ranks)}")
    print(f"Item timing rows before filter: {len(rows)}; after min-games: {len(filtered)}\n")
    print(
        f"{'hero':<20} {'item':<24} {'rank':<9} {'timing':<6} {'games':>6} "
        f"{'wr':>11} {'delta':>8} {'egpm10':>6} {'ebase':>6} {'status':<8} {'bias':<7}"
    )
    for row in enriched[: args.top]:
        print(
            f"{row['hero']:<20.20} {row['item']:<24.24} {row['rank']:<9} {row['timing']:<6} "
            f"{row['games']:>6} {row['wr']*100:5.1f}%+-{row['ci95']*100:3.1f} "
            f"{row['delta']*100:>+7.1f}% {row['avg_early_gpm'] or 0:6.1f} "
            f"{row['baseline_avg_early_gpm'] or 0:6.1f} {row['status']:<8} {row['farm_bias']:<7}"
        )

    thin_count = sum(1 for row in enriched if row["status"] == "thin")
    unclear_count = sum(1 for row in enriched if row["status"] == "unclear")
    signal_count = sum(1 for row in enriched if row["status"] == "signal")
    print(f"\nStatus counts: signal={signal_count}, unclear={unclear_count}, thin={thin_count}")
    if signal_count == 0:
        print("Warning: no statistically separated signal found at this grouping/sample threshold.")

    if args.output:
        write_report(enriched, args.output, args.format)
        print(f"Report saved to {args.output}")


if __name__ == "__main__":
    main()
