"""
Blend Calculator — Computes chemistry, slag and cost for any blend combination.
This is the core calculation engine used by both optimizer and grid search.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class BlendResult:
    """Holds all calculated properties of a blend."""
    quantities: dict          # {ore_name: qty_MT}
    total_qty: float          # total MT
    fe_pct: float             # weighted avg Fe%
    sio2_pct: float           # weighted avg SiO2%
    al2o3_pct: float          # weighted avg Al2O3%
    cao_pct: float            # weighted avg CaO%
    mgo_pct: float            # weighted avg MgO%
    tio2_pct: float           # weighted avg TiO2%
    p_pct: float              # weighted avg P%
    mno_pct: float            # weighted avg MnO%
    slag_pct: float           # SiO2+Al2O3+CaO+MgO
    slag_mt: float            # slag MT in absolute tonnes
    cost_per_mt: float        # ₹ per MT of blend
    total_cost: float         # ₹ total cost


def calculate_blend(
    quantities: dict,       # {ore_name: qty_MT}
    prices: dict,           # {ore_name: price_per_MT}
    chemistry_df: pd.DataFrame,
) -> BlendResult:
    """
    Calculate all properties of a blend given quantities and prices.
    
    quantities: dict of {ore_name: tonnes}
    prices:     dict of {ore_name: ₹/MT}
    chemistry_df: DataFrame indexed by ore name
    """
    total_qty = sum(quantities.values())
    if total_qty <= 0:
        raise ValueError("Total blend quantity must be > 0")

    # Weight fractions
    weights = {ore: qty / total_qty for ore, qty in quantities.items()}

    def weighted_avg(col: str) -> float:
        return sum(
            weights[ore] * float(chemistry_df.loc[ore, col])
            for ore in quantities
            if ore in chemistry_df.index and col in chemistry_df.columns
        )

    fe    = weighted_avg("%Fe(T)")
    sio2  = weighted_avg("%SiO2")
    al2o3 = weighted_avg("%Al2O3")
    cao   = weighted_avg("%CaO")
    mgo   = weighted_avg("%MgO")
    tio2  = weighted_avg("%TiO2")
    p     = weighted_avg("%P")
    mno   = weighted_avg("%MnO")

    slag_pct = sio2 + al2o3 + cao + mgo
    slag_mt  = slag_pct / 100.0 * total_qty

    total_cost   = sum(quantities[ore] * prices.get(ore, 0) for ore in quantities)
    cost_per_mt  = total_cost / total_qty if total_qty > 0 else 0

    return BlendResult(
        quantities=quantities,
        total_qty=total_qty,
        fe_pct=round(fe, 3),
        sio2_pct=round(sio2, 3),
        al2o3_pct=round(al2o3, 3),
        cao_pct=round(cao, 3),
        mgo_pct=round(mgo, 3),
        tio2_pct=round(tio2, 3),
        p_pct=round(p, 4),
        mno_pct=round(mno, 3),
        slag_pct=round(slag_pct, 3),
        slag_mt=round(slag_mt, 2),
        cost_per_mt=round(cost_per_mt, 2),
        total_cost=round(total_cost, 2),
    )


def blend_results_to_dict(result: BlendResult) -> dict:
    """Convert BlendResult to flat dict for DataFrame rows."""
    row = {
        "Fe%": result.fe_pct,
        "SiO2%": result.sio2_pct,
        "Al2O3%": result.al2o3_pct,
        "CaO%": result.cao_pct,
        "MgO%": result.mgo_pct,
        "TiO2%": result.tio2_pct,
        "Slag%": result.slag_pct,
        "Slag (MT)": result.slag_mt,
        "Cost/MT (₹)": result.cost_per_mt,
        "Total Cost (₹)": result.total_cost,
        "Total Qty (MT)": result.total_qty,
    }
    for ore, qty in result.quantities.items():
        row[f"qty_{ore}"] = qty
    return row