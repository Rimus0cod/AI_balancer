"""
balance_simulator.py

Модуль A ("баланс") из схемы Кардинала — но БЕЗ Reinforcement Learning.
Вместо RL используется grid search: перебор значений урона и поиск
комбинации, при которой все классы побеждают друг друга примерно поровну
(идеал — 50% win rate в каждой паре).

Как это устроено:
1. simulate_fight()   — один бой между двумя классами (тиковая симуляция)
2. simulate_many()    — прогоняет N боёв между парой классов, считает win rate
3. balance_report()   — прогоняет все пары классов, печатает таблицу
4. grid_search()      — перебирает урон классов, ищет самую сбалансированную комбинацию

Запуск: python3 balance_simulator.py
"""

import random
from itertools import product

random.seed(42)  # чтобы результаты были воспроизводимы между запусками


# ─────────────────────────────────────────────
# 1. ХАРАКТЕРИСТИКИ КЛАССОВ (стартовые, специально немного разбалансированные)
# ─────────────────────────────────────────────
# attack_speed — сколько тиков нужно классу между атаками.
# Чем МЕНЬШЕ число — тем ЧАЩЕ класс атакует (он быстрее).

BASE_CLASSES = {
    "Воин":   {"hp": 120, "damage": 16, "attack_speed": 10},
    "Маг":    {"hp": 70,  "damage": 30, "attack_speed": 16},
    "Лучник": {"hp": 90,  "damage": 17, "attack_speed": 11},
}


def simulate_fight(name_a, stats_a, name_b, stats_b, max_ticks=400):
    """Симулирует один бой. Возвращает имя победителя или None (ничья)."""
    hp_a, hp_b = stats_a["hp"], stats_b["hp"]
    cd_a, cd_b = stats_a["attack_speed"], stats_b["attack_speed"]

    for _ in range(max_ticks):
        cd_a -= 1
        cd_b -= 1

        if cd_a <= 0:
            dmg = random.randint(round(stats_a["damage"] * 0.8), round(stats_a["damage"] * 1.2))
            hp_b -= dmg
            cd_a = stats_a["attack_speed"]

        if cd_b <= 0:
            dmg = random.randint(round(stats_b["damage"] * 0.8), round(stats_b["damage"] * 1.2))
            hp_a -= dmg
            cd_b = stats_b["attack_speed"]

        if hp_a <= 0 and hp_b <= 0:
            return None
        if hp_b <= 0:
            return name_a
        if hp_a <= 0:
            return name_b

    return None


def simulate_many(name_a, stats_a, name_b, stats_b, n=300):
    """Прогоняет n боёв, возвращает win rate класса A (0.0-1.0)."""
    wins_a = 0
    decided = 0
    for _ in range(n):
        winner = simulate_fight(name_a, stats_a, name_b, stats_b)
        if winner == name_a:
            wins_a += 1
            decided += 1
        elif winner == name_b:
            decided += 1
    return wins_a / decided if decided else 0.5


def balance_report(classes, n=400, verbose=True):
    """
    Прогоняет все пары классов. Возвращает (ошибка_баланса, {(a,b): win_rate_a}).
    Ошибка баланса - сумма квадратов отклонений от 50%. Чем меньше, тем лучше.
    """
    names = list(classes.keys())
    total_error = 0.0
    results = {}

    if verbose:
        print(f"{'Матчап':<20}{'Win rate':>7}")

    for a, b in product(names, names):
        if a >= b:
            continue
        wr = simulate_many(a, classes[a], b, classes[b], n=n)
        results[(a, b)] = wr
        total_error += (wr - 0.5) ** 2
        if verbose:
            label = f"{a} vs {b}"
            print(f"{label:<20}{wr*100:>6.1f}%")

    if verbose:
        print(f"\nОшибка баланса: {total_error:.4f} (0.0 = идеальный баланс)")

    return total_error, results


def per_class_winrate(classes, results):
    """Средний win rate каждого класса против остальных двух."""
    rates = {name: [] for name in classes}
    for (a, b), wr in results.items():
        rates[a].append(wr)
        rates[b].append(1 - wr)
    return {name: sum(v) / len(v) for name, v in rates.items()}


def grid_search(base_classes, damage_delta=range(-12, 13, 2), n=200):
    """
    Перебирает изменения урона для каждого класса (grid search)
    и возвращает комбинацию с минимальной ошибкой баланса.
    """
    names = list(base_classes.keys())
    best_error = float("inf")
    best_classes = None
    tested = 0

    for deltas in product(damage_delta, repeat=len(names)):
        candidate = {}
        for name, delta in zip(names, deltas):
            candidate[name] = dict(base_classes[name])
            candidate[name]["damage"] = max(1, base_classes[name]["damage"] + delta)

        error, _ = balance_report(candidate, n=n, verbose=False)
        tested += 1

        if error < best_error:
            best_error = error
            best_classes = candidate

    print(f"Проверено комбинаций урона: {tested}")
    return best_classes, best_error


if __name__ == "__main__":
    print("========== ДО балансировки ==========")
    err_before, results_before = balance_report(BASE_CLASSES, n=500)

    print("\n========== Запускаю grid search ==========")
    best_classes, best_error = grid_search(BASE_CLASSES)

    print("\n========== ПОСЛЕ балансировки ==========")
    for name, stats in best_classes.items():
        original = BASE_CLASSES[name]["damage"]
        print(f"{name}: damage {original} -> {stats['damage']}")

    err_after, results_after = balance_report(best_classes, n=500)

    print(f"\nОшибка баланса: {err_before:.4f} -> {err_after:.4f}")

    wr_before = per_class_winrate(BASE_CLASSES, results_before)
    wr_after = per_class_winrate(best_classes, results_after)
    print("\nСредний win rate по классам (ДО):   ", {k: round(v*100, 1) for k, v in wr_before.items()})
    print("Средний win rate по классам (ПОСЛЕ):", {k: round(v*100, 1) for k, v in wr_after.items()})
