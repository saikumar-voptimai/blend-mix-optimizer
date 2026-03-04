"""
Overflow Resolver — Handles cases where recommended qty exceeds availability.

When optimizer recommends more of an ore than is available:
  1. Cap the overflowing ore at its maximum
  2. Calculate the deficit
  3. Redistribute deficit to next vendor(s) in priority list
  4. Recalculate blend chemistry on adjusted quantities
"""

import pandas as pd
from engine.blend_calculator import calculate_blend, BlendResult


def resolve_overflow(
    recommended_quantities: dict,   # {ore_name: qty_MT} from optimizer
    max_quantities: dict,            # {ore_name: max_available_MT}
    priority_list: list[str],        # ores in priority order (operator-set)
    prices: dict,                    # {ore_name: ₹/MT}
    target_qty: float,
    chemistry_df: pd.DataFrame,
) -> tuple[BlendResult | None, list[str]]:
    """
    Resolve any overflow in recommended quantities.

    Returns:
        (BlendResult with resolved quantities, list of warning messages)
    """
    warnings = []
    quantities = dict(recommended_quantities)  # copy

    # ── Step 1: Identify overflows ────────────────────────────────────────────
    overflow_ores = {
        ore: qty - max_quantities.get(ore, qty)
        for ore, qty in quantities.items()
        if qty > max_quantities.get(ore, qty) + 0.01
    }

    if not overflow_ores:
        # No overflow — just calculate and return
        return calculate_blend(quantities, prices, chemistry_df), warnings

    # ── Step 2: Cap overflowing ores and collect total deficit ────────────────
    total_deficit = 0.0
    for ore, excess in overflow_ores.items():
        quantities[ore] = max_quantities[ore]
        total_deficit += excess
        warnings.append(
            f"⚠️ {ore}: Recommended {recommended_quantities[ore]:.0f} MT "
            f"but only {max_quantities[ore]:.0f} MT available. "
            f"Capped. Deficit: {excess:.0f} MT."
        )

    # ── Step 3: Redistribute deficit down the priority list ───────────────────
    for ore in priority_list:
        if total_deficit <= 0.01:
            break

        if ore not in quantities:
            continue

        current_qty = quantities[ore]
        max_qty     = max_quantities.get(ore, current_qty)
        headroom    = max_qty - current_qty

        if headroom <= 0.01:
            continue

        # How much can this ore absorb?
        absorb = min(headroom, total_deficit)
        quantities[ore] += absorb
        total_deficit   -= absorb

        warnings.append(
            f"↳ Redirected {absorb:.0f} MT deficit → {ore} "
            f"(now {quantities[ore]:.0f} MT / {max_qty:.0f} MT available)"
        )

    # ── Step 4: Check if deficit is fully resolved ────────────────────────────
    if total_deficit > 0.5:
        warnings.append(
            f"❌ Could not fully resolve deficit. "
            f"Remaining unallocated: {total_deficit:.0f} MT. "
            f"Blend total will be {sum(quantities.values()):.0f} MT "
            f"instead of {target_qty:.0f} MT."
        )
        # Adjust target for calculation purposes
        actual_total = sum(quantities.values())
        if actual_total <= 0:
            return None, warnings
    
    return calculate_blend(quantities, prices, chemistry_df), warnings