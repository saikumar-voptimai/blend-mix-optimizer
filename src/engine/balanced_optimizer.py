"""
Balanced Optimizer — Multi-objective blend optimization.

Algorithm:
  Step 1: Run LP for each goal → 3 anchor blends (best possible per objective)
  Step 2: Run grid search around EACH anchor → 3 candidate pools
  Step 3: Merge all candidates into a single pool (union, deduplicated)
  Step 4: Score every candidate blend on all 3 normalised objectives:
            balance_score = (cost_norm + (1 - fe_norm) + slag_norm) / 3
            Lower = better balanced
  Step 5: Rank by balance score → return top blends

Note: The LP solver in optimizer.py now enforces P25 percentage-based minimums
per ore (derived from BF-02 DPR actuals). Minimums scale with target quantity:
  min_qty_i = (P25_pct / 100) × target_qty
This ensures all blends are operationally practical regardless of blend size.
"""

import pandas as pd
import numpy as np
from engine.optimizer import run_optimizer
from engine.grid_search import run_grid_search
from engine.blend_calculator import blend_results_to_dict, calculate_blend

GOALS = ["Minimize Cost", "Maximize Fe%", "Minimize Slag%"]


def _qty_key(row: pd.Series, ore_qty_cols: list) -> tuple:
    return tuple(round(float(row[c]), 0) for c in ore_qty_cols)


def run_balanced_optimization(
    selected_ores: list,
    max_quantities: dict,
    prices: dict,
    target_qty: float,
    step_size: float,
    chemistry_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Returns:
        balanced_df — all candidates ranked by combined balance score
        anchors     — {goal: BlendResult} for the 3 individual optima
    """
    ore_qty_cols = [f"qty_{ore}" for ore in selected_ores]

    # ── Step 1: LP optimizer for each goal ───────────────────────────────────
    anchors = {}
    for goal in GOALS:
        result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            goal=goal,
            chemistry_df=chemistry_df,
        )
        anchors[goal] = result

    # ── Step 2: Grid search around each anchor ────────────────────────────────
    all_frames = []
    for goal in GOALS:
        if anchors[goal] is None:
            continue
        gdf = run_grid_search(
            selected_ores=selected_ores,
            optimal_quantities=anchors[goal].quantities,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            step_size=step_size,
            goal=goal,
            chemistry_df=chemistry_df,
        )
        if not gdf.empty:
            all_frames.append(gdf)

    # Also add the 3 anchor blends themselves as explicit candidates
    for goal in GOALS:
        if anchors[goal] is None:
            continue
        row = blend_results_to_dict(anchors[goal])
        all_frames.append(pd.DataFrame([row]))

    if not all_frames:
        return pd.DataFrame(), anchors

    # ── Step 3: Union — deduplicated by qty key ───────────────────────────────
    combined = pd.concat(all_frames, ignore_index=True)

    # Add key for deduplication
    combined["_key"] = combined.apply(
        lambda r: _qty_key(r, [c for c in ore_qty_cols if c in combined.columns]),
        axis=1
    )
    combined = combined.drop_duplicates(subset=["_key"]).drop(columns=["_key"])

    # ── Step 4-5: Score and rank ───────────────────────────────────────────────
    balanced_df = _score_and_rank(combined)

    return balanced_df, anchors


def _score_and_rank(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise cost, Fe%, slag% each to [0,1] then compute balance score.
    balance_score = (cost_norm + (1 - fe_norm) + slag_norm) / 3
    Lower score = better across all three objectives.
    """
    if df.empty:
        return df

    df = df.copy()

    def norm(series: pd.Series, invert: bool = False) -> pd.Series:
        mn, mx = series.min(), series.max()
        if abs(mx - mn) < 1e-9:
            return pd.Series([0.5] * len(series), index=series.index)
        n = (series - mn) / (mx - mn)
        return (1 - n) if invert else n

    cost_norm = norm(df["Cost/MT (₹)"],  invert=False)   # lower cost → lower norm → better
    fe_norm   = norm(df["Fe%"],           invert=True)    # higher Fe  → lower norm → better
    slag_norm = norm(df["Slag%"],         invert=False)   # lower slag → lower norm → better

    df["Balance Score"] = (cost_norm + fe_norm + slag_norm) / 3.0

    df = df.sort_values("Balance Score", ascending=True)
    df = df.reset_index(drop=True)
    df.index = df.index + 1
    df.index.name = "Rank"

    return df