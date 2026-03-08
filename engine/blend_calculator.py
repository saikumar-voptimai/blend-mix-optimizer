"""
Blend Calculator — Computes chemistry, slag and cost for any blend combination.
"""

import pandas as pd
from dataclasses import dataclass
from config.config import cfg, field
from config.config import cfg

# Fe/FeO molecular weight ratio: 55.845 / 71.844
FE_FROM_FEO_FACTOR  = 55.845 / 71.844   # = 0.7773
SIO2_FROM_SI_FACTOR = 60 / 28           # = 2.1429


@dataclass
class BlendResult:
    """Holds all calculated properties of a blend."""
    quantities:       dict    # {ore_name: qty_MT}
    total_qty:        float   # total MT
    fe_pct:           float   # weighted avg Fe(T)%  — total iron, all forms
    sio2_pct:         float
    al2o3_pct:        float
    cao_pct:          float
    mgo_pct:          float
    tio2_pct:         float
    p_pct:            float
    mno_pct:          float
    feo_pct:          float   # weighted avg FeO%  (non-zero only when Sinter in blend)
    effective_fe_pct: float   # Fe(T)% + ((FeO% - feo_in_slag) × 0.7773)
    slag_pct:         float   # SiO2 - si_in_slag×(60/28) + Al2O3 + CaO + MgO + MnO
    slag_mt:          float   # slag in absolute tonnes
    cost_per_mt:      float   # ₹/MT
    total_cost:       float   # ₹ total
    fe_constraint_relaxed: bool = False  # True if Fe production constraint was relaxed


def calculate_blend(
    quantities: dict,
    prices: dict,
    chemistry_df: pd.DataFrame,
) -> BlendResult:
    total_qty = sum(quantities.values())
    if total_qty <= 0:
        raise ValueError("Total blend quantity must be > 0")

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
    feo   = weighted_avg("%FeO")   # non-zero only when Sinter is in blend

    # Effective Fe — FeO not fully reduced; feo_in_slag stays in slag, rest goes to metal
    # Fe(T)% and FeO% are separate columns in the chemistry sheet for Sinter
    effective_fe = fe + ((feo - cfg.feo_in_slag) * FE_FROM_FEO_FACTOR)

    # Slag% — subtract SiO2 equivalent of Si that stays unreduced in slag
    slag_pct = sio2 - (cfg.si_in_slag * SIO2_FROM_SI_FACTOR) + al2o3 + cao + mgo + mno
    slag_mt  = slag_pct / 100.0 * total_qty

    total_cost  = sum(quantities[ore] * prices.get(ore, 0) for ore in quantities)
    cost_per_mt = total_cost / total_qty if total_qty > 0 else 0

    return BlendResult(
        quantities       = quantities,
        total_qty        = total_qty,
        fe_pct           = round(fe, 3),
        sio2_pct         = round(sio2, 3),
        al2o3_pct        = round(al2o3, 3),
        cao_pct          = round(cao, 3),
        mgo_pct          = round(mgo, 3),
        tio2_pct         = round(tio2, 3),
        p_pct            = round(p, 4),
        mno_pct          = round(mno, 3),
        feo_pct          = round(feo, 3),
        effective_fe_pct = round(effective_fe, 3),
        slag_pct         = round(slag_pct, 3),
        slag_mt          = round(slag_mt, 2),
        cost_per_mt      = round(cost_per_mt, 2),
        total_cost       = round(total_cost, 2),
    )


def blend_results_to_dict(result: BlendResult) -> dict:
    """Convert BlendResult to flat dict for DataFrame rows."""
    row = {
        "Fe%":                result.effective_fe_pct,
        "Net Fe% (HM)":       round(result.effective_fe_pct - cfg.fe_loss_constant, 3),
        "Fe Production (MT)": round(result.effective_fe_pct / 100.0 * result.total_qty, 1),
        "SiO2%":              result.sio2_pct,
        "Al2O3%":             result.al2o3_pct,
        "CaO%":               result.cao_pct,
        "MgO%":               result.mgo_pct,
        "TiO2%":              result.tio2_pct,
        "Slag%":              result.slag_pct,
        "Slag (MT)":          result.slag_mt,
        "Cost/MT (₹)":        result.cost_per_mt,
        "Total Cost (₹)":     result.total_cost,
        "Total Qty (MT)":     result.total_qty,
    }
    for ore, qty in result.quantities.items():
        row[f"qty_{ore}"] = qty
    return row