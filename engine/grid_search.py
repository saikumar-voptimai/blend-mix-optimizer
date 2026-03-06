"""
Grid Search Engine — Generates comparison blends around the optimal solution.
"""

import numpy as np
import pandas as pd
import itertools
from engine.blend_calculator import calculate_blend, blend_results_to_dict, BlendResult

MAX_COMBINATIONS = 5000
SEARCH_RADIUS    = 0.30
MIN_QTY          = 1.0


def run_grid_search(
    selected_ores: list,
    optimal_quantities: dict,
    max_quantities: dict,
    prices: dict,
    target_qty: float,
    step_size: float,
    chemistry_df: pd.DataFrame,
) -> pd.DataFrame:
    n = len(selected_ores)

    # Build candidate values per ore
    candidate_ranges = []
    for ore in selected_ores:
        opt_qty = optimal_quantities.get(ore, target_qty / n)
        max_q   = max_quantities.get(ore, target_qty)

        low  = max(MIN_QTY, opt_qty * (1 - SEARCH_RADIUS))
        high = min(max_q, opt_qty * (1 + SEARCH_RADIUS))

        # Ensure at least 2 steps wide
        if high - low < step_size * 2:
            low  = max(MIN_QTY, opt_qty - step_size * 2)
            high = min(max_q,   opt_qty + step_size * 2)

        low_snapped  = np.ceil(low  / step_size) * step_size
        high_snapped = np.floor(high / step_size) * step_size

        candidates = list(np.arange(low_snapped, high_snapped + step_size * 0.5, step_size))
        candidates = [c for c in candidates if MIN_QTY <= c <= max_q]

        # Always include rounded optimal
        opt_rounded = round(opt_qty / step_size) * step_size
        opt_rounded = max(MIN_QTY, min(max_q, opt_rounded))
        if opt_rounded not in candidates:
            candidates.append(opt_rounded)
            candidates.sort()

        if not candidates:
            candidates = [max(MIN_QTY, min(max_q, opt_qty))]

        candidate_ranges.append(candidates)

    # Generate combinations summing to target
    results = []
    tolerance = step_size * 0.6

    count = 0
    for combo in itertools.product(*candidate_ranges):
        if abs(sum(combo) - target_qty) <= tolerance:
            quantities = {ore: combo[i] for i, ore in enumerate(selected_ores)}
            try:
                blend = calculate_blend(quantities, prices, chemistry_df)
                row = blend_results_to_dict(blend)
                results.append(row)
            except Exception:
                continue
            count += 1
            if count >= MAX_COMBINATIONS:
                break

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values("Cost/MT (₹)", ascending=True)

    df = df.reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"
    return df


def estimate_combination_count(
    selected_ores: list,
    optimal_quantities: dict,
    max_quantities: dict,
    target_qty: float,
    step_size: float,
) -> int:
    n = len(selected_ores)
    total = 1
    for ore in selected_ores:
        opt_qty = optimal_quantities.get(ore, target_qty / n)
        low  = max(MIN_QTY, opt_qty * (1 - SEARCH_RADIUS))
        high = min(max_quantities.get(ore, target_qty), opt_qty * (1 + SEARCH_RADIUS))
        if high - low < step_size * 2:
            low  = max(MIN_QTY, opt_qty - step_size * 2)
            high = min(max_quantities.get(ore, target_qty), opt_qty + step_size * 2)
        count = max(1, int((high - low) / step_size) + 1)
        total *= count
    return min(MAX_COMBINATIONS, max(1, int(total / (n * 2))))