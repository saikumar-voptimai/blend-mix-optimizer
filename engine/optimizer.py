"""
LP Optimizer — Finds the single optimal blend using linear programming.
Uses scipy.optimize.linprog to solve the blend problem.

Objectives:
  - Minimize Cost:  minimize Σ(x_i × price_i)
  - Maximize Fe%:   minimize -Σ(x_i × Fe_i) / total  →  minimize -Σ(x_i × Fe_i)
  - Minimize Slag%: minimize Σ(x_i × Slag_i) / total  →  minimize Σ(x_i × Slag_i)

Constraints:
  Σ x_i = target_qty         (equality)
  x_i ≥ min_qty (>0)         (lower bound, use small epsilon)
  x_i ≤ max_qty_i            (upper bound = availability)
"""

import numpy as np
from scipy.optimize import linprog
import pandas as pd
from engine.blend_calculator import calculate_blend, BlendResult

EPSILON = 1.0   # minimum contribution per ore (1 MT)


def run_optimizer(
    selected_ores: list[str],
    max_quantities: dict,       # {ore_name: max_MT}
    prices: dict,               # {ore_name: ₹/MT}
    target_qty: float,
    goal: str,                  # "Minimize Cost" | "Maximize Fe%" | "Minimize Slag%"
    chemistry_df: pd.DataFrame,
) -> BlendResult | None:
    """
    Run LP optimizer and return the optimal BlendResult, or None if infeasible.
    """
    n = len(selected_ores)
    idx = {ore: i for i, ore in enumerate(selected_ores)}

    # ── Objective vector ──────────────────────────────────────────────────────
    if goal == "Minimize Cost":
        c = np.array([prices.get(ore, 0) for ore in selected_ores], dtype=float)

    elif goal == "Maximize Fe%":
        # Maximize Fe% = minimize -Fe%
        # Fe%_blend = Σ(x_i × Fe_i) / target  →  minimize -Σ(x_i × Fe_i)
        c = np.array(
            [-float(chemistry_df.loc[ore, "%Fe(T)"]) for ore in selected_ores],
            dtype=float,
        )

    elif goal == "Minimize Slag%":
        # Slag_i = SiO2_i + Al2O3_i + CaO_i + MgO_i
        slag_vals = []
        for ore in selected_ores:
            slag = sum(
                float(chemistry_df.loc[ore, col])
                for col in ["%SiO2", "%Al2O3", "%CaO", "%MgO"]
                if col in chemistry_df.columns
            )
            slag_vals.append(slag)
        c = np.array(slag_vals, dtype=float)
    else:
        raise ValueError(f"Unknown goal: {goal}")

    # ── Equality constraint: Σ x_i = target_qty ──────────────────────────────
    A_eq = np.ones((1, n))
    b_eq = np.array([target_qty])

    # ── Bounds: EPSILON ≤ x_i ≤ max_qty_i ────────────────────────────────────
    bounds = [
        (EPSILON, max_quantities.get(ore, target_qty))
        for ore in selected_ores
    ]

    # Sanity check: sum of max quantities must be >= target
    total_max = sum(max_quantities.get(ore, 0) for ore in selected_ores)
    if total_max < target_qty:
        return None   # infeasible — not enough ore available

    # ── Solve ─────────────────────────────────────────────────────────────────
    result = linprog(
        c,
        A_eq=A_eq,
        b_eq=b_eq,
        bounds=bounds,
        method="highs",
    )

    if not result.success:
        return None

    # Round tiny values to EPSILON
    quantities = {}
    for i, ore in enumerate(selected_ores):
        qty = max(EPSILON, round(result.x[i], 1))
        quantities[ore] = qty

    # Normalize to exactly hit target
    total = sum(quantities.values())
    if abs(total - target_qty) > 1.0:
        scale = target_qty / total
        quantities = {ore: round(qty * scale, 1) for ore, qty in quantities.items()}

    return calculate_blend(quantities, prices, chemistry_df)