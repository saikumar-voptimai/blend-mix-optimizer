"""
LP Optimizer — Finds the minimum cost blend using linear programming.

Objective: Minimize Cost = Σ(x_i × price_i)

Constraints:
  Σ x_i = target_qty                          (equality)
  Σ(x_i × slag_i/100) ≤ target_slag_qty      (inequality — max slag MT)
  x_i ≤ ore_max_pct[i]/100 × target_qty      (upper bound — % cap per ore)
  x_i ≤ max_qty_i                             (upper bound — availability)

All thresholds are read from config.yaml via config.py.
"""

import numpy as np
from scipy.optimize import linprog
import pandas as pd
from engine.blend_calculator import calculate_blend, BlendResult, FE_FROM_FEO_FACTOR
from config.config import cfg


def run_optimizer(
    selected_ores: list[str],
    max_quantities: dict,
    prices: dict,
    target_qty: float,
    chemistry_df: pd.DataFrame,
) -> BlendResult | None:
    """
    Run LP cost minimization and return the optimal BlendResult, or None if infeasible.
    """
    n = len(selected_ores)

    # ── Objective: Minimize Cost = Σ(x_i × price_i) ──────────────────────────
    c = np.array([prices.get(ore, 0) for ore in selected_ores], dtype=float)

    # ── Equality constraint: Σ x_i = target_qty ──────────────────────────────
    A_eq = np.ones((1, n))
    b_eq = np.array([target_qty])

    # ── Inequality constraint 1: total slag MT ≤ target_slag_qty ─────────────
    slag_coeffs = []
    for ore in selected_ores:
        slag = sum(
            float(chemistry_df.loc[ore, col])
            for col in ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]
            if col in chemistry_df.columns
        )
        slag_coeffs.append(slag * 0.01)

    # ── Inequality constraint 2: Fe production ≥ min_fe_production_mt ───────
    # Fe production = Σ(x_i × effective_fe_i / 100)
    # Effective Fe = Fe(T)% + FeO%×0.7773  (FeO is a separate column for Sinter)
    # Rewrite as ≤: -Σ(x_i × effective_fe_i / 100) ≤ -min_fe_production_mt
    fe_coeffs = []
    for ore in selected_ores:
        fe_t = float(chemistry_df.loc[ore, "%Fe(T)"]) if "%Fe(T)" in chemistry_df.columns else 0.0
        feo  = float(chemistry_df.loc[ore, "%FeO"])   if "%FeO"   in chemistry_df.columns else 0.0
        effective_fe = fe_t + feo * FE_FROM_FEO_FACTOR
        fe_coeffs.append(-effective_fe * 0.01)   # negative to flip ≥ into ≤

    A_ub = np.array([slag_coeffs, fe_coeffs])
    b_ub = np.array([cfg.target_slag_qty, -cfg.min_fe_production_mt])

    # ── Bounds per ore ────────────────────────────────────────────────────────
    # Sinter: hard min/max % from config (sinter_min_pct / sinter_max_pct)
    # Others: lo=0, hi=min(ore_max_pct% of target, operator availability)
    bounds = []
    for ore in selected_ores:
        if "sinter" in ore.lower():
            lo = cfg.sinter_min_pct * target_qty
            hi = min(cfg.sinter_max_pct * target_qty, max_quantities.get(ore, target_qty))
        else:
            lo = 0.0
            max_pct_hi = (cfg.ore_max_pct.get(ore, cfg.fallback_max_pct) / 100.0) * target_qty
            avail_hi   = max_quantities.get(ore, target_qty)
            hi = min(max_pct_hi, avail_hi)
        bounds.append((lo, hi))


    # ── Solve ─────────────────────────────────────────────────────────────────
    result = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub,
                     bounds=bounds, method="highs")

    fe_relaxed = False
    if not result.success:
        # Retry without Fe constraint — selected ore combo may not reach fe_min_pct
        # Accept whatever Fe% the blend achieves naturally
        result = linprog(c, A_eq=A_eq, b_eq=b_eq,
                         A_ub=A_ub[:1], b_ub=b_ub[:1],   # slag constraint only
                         bounds=bounds, method="highs")
        if not result.success:
            return None
        fe_relaxed = True

    quantities = {}
    for i, ore in enumerate(selected_ores):
        quantities[ore] = round(result.x[i], 1)

    blend = calculate_blend(quantities, prices, chemistry_df)
    blend.fe_constraint_relaxed = fe_relaxed
    return blend