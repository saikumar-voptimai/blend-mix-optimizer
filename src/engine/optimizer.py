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

    A_ub = []
    b_ub = []

    A_ub.append(slag_coeff)
    b_ub.append(cfg.target_slag_qty)

    if min_fe_production_mt is None:
        min_fe_production_mt = float(cfg.min_fe_production_mt)
    if max_fe_production_mt is None:
        max_fe_production_mt = float(cfg.max_fe_production_mt)

    A_ub.append(fe_min_coeff)
    b_ub.append(-min_fe_production_mt)

    A_ub.append(fe_max_coeff)
    b_ub.append(max_fe_production_mt)

    sl = []
    sh = []
    for ore in selected_ores:
        sl.append(cfg.ore_min_pct.get(ore, cfg.fallback_min_pct) / 100)
        sh.append(cfg.ore_max_pct.get(ore, cfg.fallback_max_pct) / 100)

    A_ub = np.array(A_ub)

    ar_low = []
    for i in range(n):
        row = list(sl)
        row[i] = -(1 - sl[i])
        ar_low.append(row)
        b_ub.append(0)

    ar_low = np.transpose(np.array(ar_low))

    ar_high = []
    for i in range(n):
        row = [-val for val in sh]
        row[i] = (1 - sh[i])
        ar_high.append(row)
        b_ub.append(0)

    ar_high = np.transpose(np.array(ar_high))

    A_ub = np.vstack([A_ub, ar_low, ar_high])

    result = linprog(
        c=c,
        A_ub=np.array(A_ub),
        b_ub=np.array(b_ub),
        bounds=None,
        method="highs",
    )

    if not result.success:
        return None

    quantities = {
        ore: round(result.x[i], 1)
        for i, ore in enumerate(selected_ores)
    }

    return calculate_blend(quantities, prices, chemistry_df)