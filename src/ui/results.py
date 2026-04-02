"""
UI Results — Best blend card and top blends comparison table.
"""

import streamlit as st
import pandas as pd

from engine.blend_calculator import BlendResult
from utils.config import cfg
from engine.fuel_calculator import FuelInput, calculate_fuel_slag


# ── Helpers ───────────────────────────────────────────────────────────────────

def _derive_fe_totals(result: BlendResult, fuel_input: FuelInput | None):
    """Return (fuel_result, fuel_fe_mt, total_fe_mt, final_fe_pct, net_fe_pct, total_slag)."""
    fuel_result  = calculate_fuel_slag(fuel_input) if fuel_input else None
    fuel_fe_mt   = fuel_result.total_fuel_fe_mt if fuel_result else 0.0
    ore_fe_mt    = result.effective_fe_pct / 100.0 * result.total_qty
    total_fe_mt  = ore_fe_mt + fuel_fe_mt
    final_fe_pct = (total_fe_mt / result.total_qty * 100.0) if result.total_qty > 0 else result.effective_fe_pct
    net_fe_pct   = final_fe_pct - cfg.fe_loss_constant
    total_slag   = result.slag_mt + (fuel_result.total_fuel_slag_mt if fuel_result else 0.0)
    return fuel_result, fuel_fe_mt, total_fe_mt, final_fe_pct, net_fe_pct, total_slag


# ── Best Blend Card ───────────────────────────────────────────────────────────

def render_best_blend_card(
    result: BlendResult,
    fuel_input: FuelInput = None,
    min_fe_production_mt: float | None = None,
):
    """Render the minimum-cost optimal blend card."""
    if min_fe_production_mt is None:
        min_fe_production_mt = float(cfg.min_fe_production_mt)

    fuel_result, fuel_fe_mt, total_fe_mt, final_fe_pct, net_fe_pct, total_slag = (
        _derive_fe_totals(result, fuel_input)
    )

    # ── Banner ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="result-banner">
      <div style="color:#9ec4e8; font-size:11px; font-weight:700;
                  text-transform:uppercase; letter-spacing:1.2px;">
        Optimizer Result · Minimum Cost
      </div>
      <div style="color:#ffffff; font-size:22px; font-weight:700; margin-top:4px;">
        🏆 &nbsp;Optimal Blend
      </div>
      <div style="color:#c8ddf0; font-size:13px; margin-top:6px;">
        ₹{result.cost_per_thm:,.0f} / THM &nbsp;·&nbsp;
        {total_fe_mt:.1f} MT Fe &nbsp;·&nbsp;
        {total_slag:.1f} MT Total Slag &nbsp;·&nbsp;
        {result.total_qty:.0f} MT Ore Blend
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Constraint relaxation warning ─────────────────────────────────────────
    if getattr(result, "fe_constraint_relaxed", False):
        st.markdown(f"""
        <div class="constraint-warn">
          ⚠️ <strong>Fe production constraint relaxed</strong> — selected ores cannot reach
          {min_fe_production_mt:.0f} MT Fe. Blend achieves {result.effective_fe_pct:.2f}% Fe.
        </div>
        """, unsafe_allow_html=True)

    # ── KPI row 1: Fe metrics ──────────────────────────────────────────────────
    st.markdown('<div class="result-section-label">Fe &amp; Production</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Gross Fe%",
        f"{final_fe_pct:.3f}%",
        delta=f"ore only {result.effective_fe_pct:.3f}%" if fuel_fe_mt > 0 else None,
        delta_color="off",
    )
    k2.metric(
        "Net Fe% (HM)",
        f"{net_fe_pct:.3f}%",
        delta=f"−{cfg.fe_loss_constant:.2f}% BF loss",
        delta_color="off",
    )
    k3.metric(
        "Fe Production",
        f"{total_fe_mt:.1f} MT",
        delta=f"+{fuel_fe_mt:.1f} MT from fuel" if fuel_fe_mt > 0 else f"min {min_fe_production_mt:.0f} MT",
        delta_color="normal" if fuel_fe_mt > 0 else "off",
    )
    k4.metric("Ore Slag", f"{result.slag_mt:.1f} MT")

    # ── KPI row 2: Cost & slag ────────────────────────────────────────────────
    st.markdown('<div class="result-section-label">Cost &amp; Burden</div>', unsafe_allow_html=True)
    k5, k6, k7, k8 = st.columns(4)
    k5.metric(
        "Total BF Slag",
        f"{total_slag:.1f} MT",
        delta=f"+{fuel_result.total_fuel_slag_mt:.1f} MT from fuel" if fuel_result else None,
        delta_color="inverse",
    )
    k6.metric("Ore Blend Qty",  f"{result.total_qty:.0f} MT")
    k7.metric("Cost / THM",     f"₹{result.cost_per_thm:,.0f}")
    k8.metric("Total Cost",     f"₹{result.total_cost / 100_000:.2f} L")

    st.divider()

    # ── Ore Recipe ────────────────────────────────────────────────────────────
    st.markdown('<div class="step-header">📦 &nbsp;Ore Recipe</div>', unsafe_allow_html=True)

    recipe_rows = [
        {
            "Ore / Vendor":   ore,
            "Quantity (MT)":  qty,
            "Share (%)":      round(qty / result.total_qty * 100.0, 2) if result.total_qty > 0 else 0.0,
            "Price (₹/MT)":   cfg.ore_prices.get(ore, cfg.fallback_price),
        }
        for ore, qty in result.quantities.items()
        if qty > 0
    ]
    recipe_df = pd.DataFrame(recipe_rows)

    st.dataframe(
        recipe_df,
        column_config={
            "Ore / Vendor":  st.column_config.TextColumn("Ore / Vendor"),
            "Quantity (MT)": st.column_config.NumberColumn("Qty (MT)", format="%.0f"),
            "Share (%)":     st.column_config.ProgressColumn(
                                 "Share (%)", format="%.1f%%",
                                 min_value=0, max_value=100,
                             ),
            "Price (₹/MT)":  st.column_config.NumberColumn("Price (₹/MT)", format="₹%.0f"),
        },
        hide_index=True,
        use_container_width=True,
    )

    # ── Blend Chemistry ───────────────────────────────────────────────────────
    st.markdown('<div class="step-header">⚗️ &nbsp;Blend Chemistry</div>', unsafe_allow_html=True)

    fe_display = (
        f"{final_fe_pct:.3f}%" if fuel_fe_mt > 0
        else (f"{result.effective_fe_pct:.3f}%" if getattr(result, "feo_pct", 0) > 0 else f"{result.fe_pct:.3f}%")
    )

    chem_data = {
        "Component":   ["Gross Fe%", "Net Fe% (HM)", "SiO2%", "Al2O3%", "CaO%", "MgO%", "TiO2%", "P%", "MnO%", "Slag%"],
        "Value":       [
            fe_display,
            f"{net_fe_pct:.3f}%",
            f"{result.sio2_pct:.3f}%",
            f"{result.al2o3_pct:.3f}%",
            f"{result.cao_pct:.3f}%",
            f"{result.mgo_pct:.3f}%",
            f"{result.tio2_pct:.3f}%",
            f"{result.p_pct:.4f}%",
            f"{result.mno_pct:.3f}%",
            f"{result.slag_pct:.3f}%",
        ],
    }

    ch1, ch2 = st.columns([1, 2])
    with ch1:
        st.dataframe(
            pd.DataFrame(chem_data),
            hide_index=True,
            use_container_width=True,
        )

    # ── Fuel Slag Breakdown ───────────────────────────────────────────────────
    if fuel_result:
        with st.expander("🔥 Fuel Slag & Fe Breakdown", expanded=False):
            fc1, fc2, fc3, fc4 = st.columns(4)
            fc1.metric("Coke Slag",     f"{fuel_result.coke_slag_mt:.1f} MT",
                       f"Ash {fuel_input.coke_ash_pct}% × {fuel_input.coke_qty_mt:.0f} MT")
            fc2.metric("Nut Coke Slag", f"{fuel_result.nut_coke_slag_mt:.1f} MT",
                       f"Ash {fuel_input.nut_coke_ash_pct}% × {fuel_input.nut_coke_qty_mt:.0f} MT")
            fc3.metric("PCI Slag",      f"{fuel_result.pci_slag_mt:.1f} MT",
                       f"Ash {fuel_input.pci_ash_pct}% × {fuel_input.pci_qty_mt:.0f} MT")
            fc4.metric("Total Fuel Slag", f"{fuel_result.total_fuel_slag_mt:.1f} MT")

            st.divider()

            fe1, fe2, fe3, fe4 = st.columns(4)
            fe1.metric("Coke Fe",     f"{fuel_result.coke_fe_mt:.2f} MT", "Fe₂O₃ in ash → Fe")
            fe2.metric("Nut Coke Fe", f"{fuel_result.nut_coke_fe_mt:.2f} MT", "Fe₂O₃ in ash → Fe")
            fe3.metric("PCI Fe",      f"{fuel_result.pci_fe_mt:.2f} MT", "Fe₂O₃ in ash → Fe")
            fe4.metric("Total Fuel Fe", f"{fuel_result.total_fuel_fe_mt:.2f} MT")


# ── Top Blends Table ──────────────────────────────────────────────────────────

def render_top_blends_table(grid_df: pd.DataFrame, fuel_input: FuelInput = None):
    """Render the top-N blends comparison table with cost progress bars and CSV export."""
    if grid_df.empty:
        st.info("No comparison blends generated. Try reducing step size or expanding ore availability.")
        return

    # ── Header + controls ─────────────────────────────────────────────────────
    hdr_col, n_col, dl_col = st.columns([4, 1, 1])
    hdr_col.markdown(
        f'<div class="result-banner" style="padding:12px 18px;">'
        f'<span style="color:#9ec4e8; font-size:11px; font-weight:700; '
        f'text-transform:uppercase; letter-spacing:1px;">Grid Search Results</span><br/>'
        f'<span style="color:#fff; font-size:16px; font-weight:600;">'
        f'📊 &nbsp;{len(grid_df):,} valid blends found — sorted by cost</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    max_show = min(200, len(grid_df))
    default_show = min(50, len(grid_df))
    top_n = int(n_col.number_input(
        "Show top",
        min_value=1,
        max_value=max_show,
        value=default_show,
        step=5,
        help="Number of top-ranked blends to display (ranked by ₹/THM ascending)",
    ))

    # ── Build display dataframe ───────────────────────────────────────────────
    show_df = grid_df.copy()

    if fuel_input and "Fe%" in show_df.columns and "Fe Production (MT)" in show_df.columns:
        fuel_result  = calculate_fuel_slag(fuel_input)
        fuel_fe_mt   = fuel_result.total_fuel_fe_mt
        show_df["Fe Production (MT)"] = show_df["Fe Production (MT)"] + fuel_fe_mt
        show_df["Fe%"] = show_df["Fe Production (MT)"] / show_df["Total Qty (MT)"] * 100.0

    if "Fe%" in show_df.columns:
        show_df["Net Fe% (HM)"] = (show_df["Fe%"] - cfg.fe_loss_constant).round(3)

    qty_cols   = [c for c in show_df.columns if c.startswith("qty_")]
    rename_map = {c: c.replace("qty_", "") for c in qty_cols}

    ordered_cols = (
        qty_cols
        + ["Total Qty (MT)", "Fe%", "Net Fe% (HM)", "Fe Production (MT)",
           "Total Slag (MT)", "Slag (MT)", "Cost/THM (₹)", "Total Cost (₹)"]
    )
    ordered_cols = [c for c in ordered_cols if c in show_df.columns]
    show_df = show_df[ordered_cols].rename(columns=rename_map).head(top_n).copy()

    ore_names = list(rename_map.values())

    # ── Column config ─────────────────────────────────────────────────────────
    cost_col   = "Cost/THM (₹)"
    cost_vals  = pd.to_numeric(show_df[cost_col], errors="coerce") if cost_col in show_df.columns else None
    cost_min   = float(cost_vals.min()) if cost_vals is not None else 0.0
    cost_max   = float(cost_vals.max()) if cost_vals is not None else 1.0

    col_config: dict = {}

    if cost_col in show_df.columns:
        col_config[cost_col] = st.column_config.ProgressColumn(
            "Cost/THM (₹)",
            format="₹%.0f",
            min_value=cost_min,
            max_value=cost_max,
        )

    for ore in ore_names:
        if ore in show_df.columns:
            col_config[ore] = st.column_config.NumberColumn(ore, format="%.0f MT")

    for num_col, fmt in [
        ("Total Qty (MT)",       "%.0f MT"),
        ("Fe%",                  "%.3f%%"),
        ("Net Fe% (HM)",         "%.3f%%"),
        ("Fe Production (MT)",   "%.1f MT"),
        ("Total Slag (MT)",      "%.1f MT"),
        ("Slag (MT)",            "%.1f MT"),
        ("Total Cost (₹)",       "₹%.0f"),
    ]:
        if num_col in show_df.columns:
            col_config[num_col] = st.column_config.NumberColumn(num_col, format=fmt)

    # ── Download button ───────────────────────────────────────────────────────
    csv_bytes = show_df.to_csv(index=True).encode("utf-8")
    dl_col.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)
    dl_col.download_button(
        "📥 Export CSV",
        data=csv_bytes,
        file_name=f"top_{top_n}_blends.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # ── Table ─────────────────────────────────────────────────────────────────
    st.dataframe(
        show_df,
        column_config=col_config,
        use_container_width=True,
        height=min(600, 36 + top_n * 35),
    )

    st.caption(
        f"Showing {min(top_n, len(show_df))} of {len(grid_df):,} feasible blends. "
        f"Ranked #1 = lowest ₹/THM. Increase 'Show top' to see more."
    )
