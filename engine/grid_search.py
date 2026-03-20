"""
Grid Search Engine — Generates comparison blends around the optimal solution.

Design:
- Search near the LP optimum, not across the full space
- Enforce ore min/max share constraints from config
- Enforce Fe production range provided by UI
- Enforce slag limit from config
"""

from __future__ import annotations

import itertools
import time
import numpy as np
import pandas as pd

from engine.blend_calculator import calculate_blend, blend_results_to_dict
from config.config import cfg

MAX_RESULTS = 5000
MAX_EVALUATIONS = 150_000
MAX_SECONDS = 100.0
SEARCH_RADIUS = 0.30
MIN_QTY = 0.0
_EPS = 1e-9


def _build_candidates(opt_qty: float, max_q: float, step_size: float) -> list[float]:
    low = max(MIN_QTY, opt_qty * (1 - SEARCH_RADIUS))
    high = min(max_q, opt_qty * (1 + SEARCH_RADIUS))

    if high - low < step_size * 2:
        low = max(MIN_QTY, opt_qty - step_size * 2)
        high = min(max_q, opt_qty + step_size * 2)

    low_snapped = np.ceil(low / step_size) * step_size
    high_snapped = np.floor(high / step_size) * step_size

    candidates = list(np.arange(low_snapped, high_snapped + step_size * 0.5, step_size))
    candidates = [float(c) for c in candidates if MIN_QTY <= c <= max_q]

    opt_rounded = round(opt_qty / step_size) * step_size
    opt_rounded = max(MIN_QTY, min(max_q, opt_rounded))
    candidates.append(float(opt_rounded))

    if not candidates:
        candidates = [max(MIN_QTY, min(max_q, opt_qty))]

    candidates = sorted({round(float(c), 10) for c in candidates})
    candidates.sort(key=lambda c: (abs(c - opt_qty), c))
    return candidates


def run_grid_search(
    selected_ores: list[str],
    optimal_quantities: dict[str, float],
    max_quantities: dict[str, float],
    prices: dict[str, float],
    step_size: float,
    chemistry_df: pd.DataFrame,
    min_fe_production_mt: float | None = None,
    max_fe_production_mt: float | None = None,
) -> pd.DataFrame:
    if min_fe_production_mt is None:
        min_fe_production_mt = float(cfg.min_fe_production_mt)
    if max_fe_production_mt is None:
        max_fe_production_mt = float(cfg.max_fe_production_mt)

    candidate_ranges: list[list[float]] = []
    min_pcts = []
    max_pcts = []

    for ore in selected_ores:
        opt_qty = float(optimal_quantities.get(ore, 0.0))
        max_q = float(max_quantities.get(ore, opt_qty))
        candidate_ranges.append(_build_candidates(opt_qty, max_q, step_size))
        min_pcts.append(float(cfg.ore_min_pct.get(ore, cfg.fallback_min_pct)) / 100.0)
        max_pcts.append(float(cfg.ore_max_pct.get(ore, cfg.fallback_max_pct)) / 100.0)

    results = []
    started = time.perf_counter()
    evaluated = 0

    for combo in itertools.product(*candidate_ranges):
        if len(results) >= MAX_RESULTS:
            break
        if evaluated >= MAX_EVALUATIONS:
            break
        if time.perf_counter() - started > MAX_SECONDS:
            break

        total_qty = float(sum(combo))
        if total_qty <= 0:
            continue

        # Cheap share checks first
        share_failed = False
        for i, qty in enumerate(combo):
            share = qty / total_qty
            if share < min_pcts[i] - _EPS:
                share_failed = True
                break
            if share > max_pcts[i] + _EPS:
                share_failed = True
                break
        if share_failed:
            continue

        quantities = {ore: float(combo[i]) for i, ore in enumerate(selected_ores)}

        try:
            evaluated += 1
            blend = calculate_blend(quantities, prices, chemistry_df)
        except Exception:
            continue

        fe_production_mt = float(blend.effective_fe_pct) / 100.0 * float(blend.total_qty)
        if fe_production_mt < min_fe_production_mt - _EPS:
            continue
        if fe_production_mt > max_fe_production_mt + _EPS:
            continue

        if float(blend.slag_mt) > float(cfg.target_slag_qty) + _EPS:
            continue

        row = blend_results_to_dict(blend)
        row["Fe Production (MT)"] = round(fe_production_mt, 1)
        results.append(row)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("Cost/MT (₹)", ascending=True).reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"
    return df


def estimate_combination_count(
    selected_ores: list[str],
    optimal_quantities: dict[str, float],
    max_quantities: dict[str, float],
    step_size: float,
) -> int:
    total = 1
    for ore in selected_ores:
        opt_qty = float(optimal_quantities.get(ore, 0.0))
        max_q = float(max_quantities.get(ore, opt_qty))
        total *= max(1, len(_build_candidates(opt_qty, max_q, step_size)))
    return int(total)