"""
UI Results — Best blend card, balanced results display, and top blends table.
"""

import streamlit as st
import pandas as pd
from engine.blend_calculator import BlendResult


# ── Optimal blend card ───────────────────────────────────────────────────────

def render_best_blend_card(result: BlendResult):
    """Render the minimum cost optimal blend card."""
    st.subheader("💰 Minimum Cost Blend")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Fe%",        f"{result.effective_fe_pct:.2f}%")
    col2.metric("Slag%",      f"{result.slag_pct:.2f}%")
    col3.metric("Slag MT",    f"{result.slag_mt:.1f}")
    col4.metric("Cost/MT",    f"₹{result.cost_per_mt:,.0f}")
    col5.metric("Total Cost", f"₹{result.total_cost/100000:.2f}L")

    with st.expander("Full chemistry + composition"):
        qty_cols = st.columns(len(result.quantities))
        for i, (ore, qty) in enumerate(result.quantities.items()):
            pct = qty / result.total_qty * 100
            qty_cols[i].metric(ore, f"{qty:.0f} MT", f"{pct:.1f}%")

        st.divider()
        # When Sinter is in blend, show Fe% = Fe(T)% + FeO×0.7773 (FeO is separate in chemistry sheet)
        # When no Sinter, Fe% = Fe(T)% as usual
        fe_display = f"{result.effective_fe_pct:.3f}%" if result.feo_pct > 0 else f"{result.fe_pct:.3f}%"
        chem_rows = [
            ("Fe%",     fe_display),
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

def render_top_blends_table(grid_df: pd.DataFrame):
    """Render the top blends comparison table sorted by cost."""
    if grid_df.empty:
        st.info("No comparison blends generated. Try reducing step size or expanding availability.")
        return

    st.subheader("Top Blends — Sorted by Cost")
    st.caption(f"{len(grid_df)} valid blends found via grid search")

    display_cols = [
        "Fe%", "SiO2%", "Al2O3%", "CaO%", "MgO%", "TiO2%",
        "Slag%", "Slag (MT)", "Cost/MT (₹)", "Total Cost (₹)", "Total Qty (MT)"
    ]
    display_cols = [c for c in display_cols if c in grid_df.columns]
    show_df = grid_df[display_cols].head(20).copy()

    for col in show_df.columns:
        if "₹" in col or "Cost" in col:
            show_df[col] = show_df[col].apply(lambda x: f"₹{x:,.0f}")
        elif "%" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.3f}%")
        elif "MT" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.1f}")

    st.dataframe(show_df, use_container_width=True)