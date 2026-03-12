"""
UI Results — Best blend card, balanced results display, and top blends table.
"""

import streamlit as st
import pandas as pd
from engine.blend_calculator import BlendResult
from config.config import cfg
from engine.fuel_calculator import FuelInput, FuelSlagResult, calculate_fuel_slag


# ── Optimal blend card ───────────────────────────────────────────────────────

def render_best_blend_card(result: BlendResult, fuel_input: FuelInput = None):
    """Render the minimum cost optimal blend card."""
    st.subheader("💰 Minimum Cost Blend")
    if getattr(result, 'fe_constraint_relaxed', False):
        st.warning(
            f"⚠️ Fe production constraint relaxed — selected ores cannot reach "
            f"{cfg.min_fe_production_mt:.0f} MT Fe production. "
            f"Blend achieves {result.effective_fe_pct:.2f}% Fe. "
            f"Consider lowering min_fe_production_mt in config."
        )

    # Fuel slag
    fuel_result = calculate_fuel_slag(fuel_input) if fuel_input else None
    total_slag  = result.slag_mt + (fuel_result.total_fuel_slag_mt if fuel_result else 0)

    ore_fe_mt    = result.effective_fe_pct / 100.0 * result.total_qty
    fuel_fe_mt   = fuel_result.total_fuel_fe_mt if fuel_result else 0.0
    fuel_qty_mt  = (fuel_input.coke_qty_mt + fuel_input.nut_coke_qty_mt + fuel_input.pci_qty_mt) if fuel_input else 0.0
    total_fe_mt  = ore_fe_mt + fuel_fe_mt
    final_fe_pct = (total_fe_mt / result.total_qty * 100) if result.total_qty > 0 else result.effective_fe_pct
    net_fe_pct   = final_fe_pct - cfg.fe_loss_constant   # after BF losses (slag FeO, flue dust, GCP dust)

    # Row 1: Fe metrics (4 columns)
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.metric("Gross Fe%",     f"{final_fe_pct:.3f}%",
                delta=f"ore only {result.effective_fe_pct:.3f}%" if fuel_fe_mt > 0 else None,
                delta_color="off")
    r1c2.metric("Net Fe% (HM)",  f"{net_fe_pct:.3f}%",
                delta=f"-{cfg.fe_loss_constant:.2f}% BF loss",
                delta_color="off")
    r1c3.metric("Fe Production", f"{total_fe_mt:.1f} MT",
                delta=f"+{fuel_fe_mt:.1f} MT from fuel" if fuel_fe_mt > 0 else f"min {cfg.min_fe_production_mt:.0f} MT",
                delta_color="normal" if fuel_fe_mt > 0 else "off")
    r1c4.metric("Ore Slag",      f"{result.slag_mt:.1f} MT")

    # Row 2: Slag + Cost (4 columns)
    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.metric("Total BF Slag", f"{total_slag:.1f} MT",
                delta=f"+{fuel_result.total_fuel_slag_mt:.1f} MT from fuel" if fuel_result else None,
                delta_color="inverse")
    r2c2.metric("Ore Blend Qty", f"{result.total_qty:.0f} MT")
    r2c3.metric("Cost / MT",     f"₹{result.cost_per_mt:,.0f}")
    r2c4.metric("Total Cost",    f"₹{result.total_cost/100000:.2f} L")

    # Fuel slag breakdown
    if fuel_result:
        with st.expander("🔥 Fuel Slag Breakdown", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("Coke Slag",     f"{fuel_result.coke_slag_mt:.1f} MT",
                       f"Ash: {fuel_input.coke_ash_pct}% × {fuel_input.coke_qty_mt:.0f} MT")
            fc2.metric("Nut Coke Slag", f"{fuel_result.nut_coke_slag_mt:.1f} MT",
                       f"Ash: {fuel_input.nut_coke_ash_pct}% × {fuel_input.nut_coke_qty_mt:.0f} MT")
            fc3.metric("PCI Slag",      f"{fuel_result.pci_slag_mt:.1f} MT",
                       f"Ash: {fuel_input.pci_ash_pct}% × {fuel_input.pci_qty_mt:.0f} MT")
            fc4.metric("Total Fuel Slag", f"{fuel_result.total_fuel_slag_mt:.1f} MT")

            st.divider()
            fe1, fe2, fe3, fe4 = st.columns(4)
            fe1.metric("Coke Fe",       f"{fuel_result.coke_fe_mt:.2f} MT",
                       f"Fe2O3 in ash → Fe")
            fe2.metric("Nut Coke Fe",   f"{fuel_result.nut_coke_fe_mt:.2f} MT",
                       f"Fe2O3 in ash → Fe")
            fe3.metric("PCI Fe",        f"{fuel_result.pci_fe_mt:.2f} MT",
                       f"Fe2O3 in ash → Fe")
            fe4.metric("Total Fuel Fe", f"{fuel_result.total_fuel_fe_mt:.2f} MT")

    with st.expander("Full chemistry + composition"):
        qty_cols = st.columns(len(result.quantities))
        for i, (ore, qty) in enumerate(result.quantities.items()):
            pct = qty / result.total_qty * 100
            qty_cols[i].metric(ore, f"{qty:.0f} MT", f"{pct:.1f}%")

        st.divider()
        # Fe% — fuel-adjusted if fuel present, else ore-only
        fe_display = f"{final_fe_pct:.3f}%" if fuel_fe_mt > 0 else (
                     f"{result.effective_fe_pct:.3f}%" if result.feo_pct > 0 else f"{result.fe_pct:.3f}%")
        net_fe_display = f"{final_fe_pct - cfg.fe_loss_constant:.3f}%"
        chem_rows = [
            ("Gross Fe%",    fe_display),
            ("Net Fe% (HM)", net_fe_display),
            ("SiO2%",   f"{result.sio2_pct:.3f}%"),
            ("Al2O3%",  f"{result.al2o3_pct:.3f}%"),
            ("CaO%",    f"{result.cao_pct:.3f}%"),
            ("MgO%",    f"{result.mgo_pct:.3f}%"),
            ("TiO2%",   f"{result.tio2_pct:.3f}%"),
            ("P%",      f"{result.p_pct:.4f}%"),
            ("MnO%",    f"{result.mno_pct:.3f}%"),
            ("Slag%",   f"{result.slag_pct:.3f}%"),
        ]
        st.dataframe(
            pd.DataFrame(chem_rows, columns=["Component", "Value"]),
            hide_index=True,
            use_container_width=True,
        )


# ── Single-goal top blends table ─────────────────────────────────────────────

def render_top_blends_table(grid_df: pd.DataFrame, fuel_input: FuelInput = None):
    """Render the top blends comparison table sorted by cost."""
    if grid_df.empty:
        st.info("No comparison blends generated. Try reducing step size or expanding availability.")
        return

    st.subheader("Top Blends — Sorted by Cost")
    st.caption(f"{len(grid_df)} valid blends found via grid search")

    show_df = grid_df.copy()

    # Adjust Fe% and Fe Production to include fuel Fe contribution
    if fuel_input and "Fe%" in show_df.columns and "Fe Production (MT)" in show_df.columns:
        fuel_result = calculate_fuel_slag(fuel_input)
        fuel_fe_mt  = fuel_result.total_fuel_fe_mt
        show_df["Fe Production (MT)"] = show_df["Fe Production (MT)"] + fuel_fe_mt
        show_df["Fe%"] = show_df["Fe Production (MT)"] / show_df["Total Qty (MT)"] * 100

    # Recompute Net Fe% (HM) = Gross Fe% x efficiency (after fuel adjustment)
    if "Fe%" in show_df.columns:
        show_df["Net Fe% (HM)"] = show_df["Fe%"] - cfg.fe_loss_constant

    display_cols = [
        "Fe%", "Net Fe% (HM)", "Fe Production (MT)", "SiO2%", "Al2O3%", "CaO%", "MgO%", "TiO2%",
        "Slag%", "Slag (MT)", "Cost/MT (₹)", "Total Cost (₹)", "Total Qty (MT)"
    ]
    display_cols = [c for c in display_cols if c in show_df.columns]
    show_df = show_df[display_cols].head(20).copy()

    for col in show_df.columns:
        if "₹" in col or "Cost" in col:
            show_df[col] = show_df[col].apply(lambda x: f"₹{x:,.0f}")
        elif "%" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.3f}%")
        elif "MT" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.1f}")

    st.dataframe(show_df, use_container_width=True)
    