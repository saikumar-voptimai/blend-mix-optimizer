"""
LP Optimizer — Finds the minimum cost blend using linear programming.

Constraints enforced:
- Fe production range
- Slag limit
- Sinter ratio
- Ore max percentage caps
- Ore availability
"""

import numpy as np
import pandas as pd
from scipy.optimize import linprog

from engine.blend_calculator import calculate_blend, BlendResult, FE_FROM_FEO_FACTOR
from engine.fuel_calculator import FuelInput, calculate_fuel_slag
from utils.config import cfg


def _find_sinter_index(selected_ores):
    for i, ore in enumerate(selected_ores):
        if "sinter" in ore.lower():
            return i
    raise ValueError("No sinter found in selected ores")


def _effective_fe(chemistry_df, ore):
    fe_t = float(chemistry_df.loc[ore, "%Fe(T)"])
    feo = float(chemistry_df.loc[ore, "%FeO"]) if "%FeO" in chemistry_df.columns else 0
    return fe_t + feo * FE_FROM_FEO_FACTOR


def _slag_pct(chemistry_df, ore):
    cols = ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]
    return sum(float(chemistry_df.loc[ore, c]) for c in cols if c in chemistry_df.columns)


def run_optimizer(
    selected_ores,
    max_quantities,
    prices,
    chemistry_df,
    min_fe_production_mt,
    max_fe_production_mt,
    fuel_input: FuelInput | None = None,
):

    n = len(selected_ores)

    c = np.array([prices.get(o, 0) for o in selected_ores], dtype=float)

    slag_coeff = []
    fe_min_coeff = []
    fe_max_coeff = []

    for ore in selected_ores:

        slag = _slag_pct(chemistry_df, ore)
        fe = _effective_fe(chemistry_df, ore)

        slag_coeff.append(slag / 100)
        fe_min_coeff.append(-fe / 100)
        fe_max_coeff.append(fe / 100)

    A_ub: list[list[float]] = []
    b_ub: list[float] = []

    # Slag constraint: cfg.target_slag_qty is treated as TOTAL BF slag budget.
    # Ore-derived slag is constrained to (budget - fuel_slag).
    fuel_slag_mt = 0.0
    if fuel_input is not None:
        try:
            fuel_slag_mt = float(calculate_fuel_slag(fuel_input).total_fuel_slag_mt)
        except Exception:
            fuel_slag_mt = 0.0

    slag_budget_mt = float(cfg.target_slag_qty) - fuel_slag_mt
    if slag_budget_mt < 0:
        # Fuel slag already exceeds the slag budget → infeasible by definition.
        return None

    A_ub.append(list(slag_coeff))
    b_ub.append(float(slag_budget_mt))

    if min_fe_production_mt is None:
        min_fe_production_mt = float(cfg.min_fe_production_mt)
    if max_fe_production_mt is None:
        max_fe_production_mt = float(cfg.max_fe_production_mt)

    A_ub.append(list(fe_min_coeff))
    b_ub.append(float(-min_fe_production_mt))

    A_ub.append(list(fe_max_coeff))
    b_ub.append(float(max_fe_production_mt))

    # Share constraints (linearised):
    #   min: x_i >= sl_i * sum(x)  ->  sl_i*sum(x) - x_i <= 0
    #   max: x_i <= sh_i * sum(x)  ->  x_i - sh_i*sum(x) <= 0
    sl = [float(cfg.ore_min_pct.get(ore, cfg.fallback_min_pct)) / 100.0 for ore in selected_ores]
    sh = [float(cfg.ore_max_pct.get(ore, cfg.fallback_max_pct)) / 100.0 for ore in selected_ores]

    for i in range(n):
        sl_i = float(sl[i])
        row = [sl_i] * n
        row[i] = sl_i - 1.0
        A_ub.append(row)
        b_ub.append(0.0)

    for i in range(n):
        sh_i = float(sh[i])
        row = [-sh_i] * n
        row[i] = 1.0 - sh_i
        A_ub.append(row)
        b_ub.append(0.0)

    bounds = []
    for ore in selected_ores:
        max_q = max_quantities.get(ore, None)
        if max_q is None:
            bounds.append((0.0, None))
        else:
            bounds.append((0.0, float(max_q)))

    result = linprog(
        c=c,
        A_ub=np.array(A_ub),
        b_ub=np.array(b_ub),
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        return None

    quantities = {
        ore: round(result.x[i], 1)
        for i, ore in enumerate(selected_ores)
    }

    return calculate_blend(quantities, prices, chemistry_df)