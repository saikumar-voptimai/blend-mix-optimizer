"""
UI Results — Best blend card and chemistry summary display.
"""

import streamlit as st
import pandas as pd
from engine.blend_calculator import BlendResult


def render_best_blend_card(result: BlendResult, goal: str, overflow_warnings: list[str]):
    """Render the optimal blend result as a styled card."""

    st.markdown("""
    <div style='background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border: 1px solid #E8A020;
                border-radius: 12px;
                padding: 1.5rem 2rem;
                margin-bottom: 1.5rem;'>
        <h2 style='color: #E8A020; font-family: monospace; 
                   letter-spacing: 3px; margin: 0 0 0.5rem 0; font-size: 1rem;'>
            ★ OPTIMAL BLEND
        </h2>
    </div>
    """, unsafe_allow_html=True)

    # Show overflow warnings if any
    if overflow_warnings:
        with st.expander("⚠️ Overflow Adjustments Applied", expanded=False):
            for w in overflow_warnings:
                st.markdown(f"- {w}")

    # KPI metrics row
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            "Fe%",
            f"{result.fe_pct:.2f}%",
            help="Weighted average iron content of blend"
        )
    with col2:
        st.metric(
            "Slag%",
            f"{result.slag_pct:.2f}%",
            help="SiO2 + Al2O3 + CaO + MgO"
        )
    with col3:
        st.metric(
            "Slag Volume",
            f"{result.slag_mt:.1f} MT",
            help="Absolute slag-forming material in blend"
        )
    with col4:
        st.metric(
            "Cost/MT",
            f"₹{result.cost_per_mt:,.0f}",
            help="Weighted average cost per tonne"
        )
    with col5:
        st.metric(
            "Total Cost",
            f"₹{result.total_cost/100000:.2f}L",
            help="Total procurement cost (Lakhs)"
        )

    st.divider()

    # Ore quantities breakdown
    st.markdown("#### Blend Composition")
    qty_cols = st.columns(len(result.quantities))
    for i, (ore, qty) in enumerate(result.quantities.items()):
        pct = (qty / result.total_qty) * 100
        with qty_cols[i]:
            st.metric(
                ore,
                f"{qty:.0f} MT",
                f"{pct:.1f}% of blend"
            )

    st.divider()

    # Full chemistry breakdown
    st.markdown("#### Full Chemistry Profile")
    chem_data = {
        "Component": ["Fe%", "SiO2%", "Al2O3%", "CaO%", "MgO%", "TiO2%", "P%", "MnO%", "Slag%"],
        "Blend Value": [
            f"{result.fe_pct:.3f}%",
            f"{result.sio2_pct:.3f}%",
            f"{result.al2o3_pct:.3f}%",
            f"{result.cao_pct:.3f}%",
            f"{result.mgo_pct:.3f}%",
            f"{result.tio2_pct:.3f}%",
            f"{result.p_pct:.4f}%",
            f"{result.mno_pct:.3f}%",
            f"{result.slag_pct:.3f}%",
        ]
    }
    chem_df = pd.DataFrame(chem_data)
    st.dataframe(chem_df, use_container_width=True, hide_index=True)


def render_top_blends_table(grid_df: pd.DataFrame, goal: str):
    """Render the top blends comparison table."""
    if grid_df.empty:
        st.info("No comparison blends generated. Try reducing step size or expanding availability.")
        return

    st.markdown(f"#### Top Blends — Sorted by: **{goal}**")
    st.caption(f"{len(grid_df)} valid blends found via grid search")

    # Display columns — exclude raw qty_ columns from main table
    display_cols = [
        "Fe%", "SiO2%", "Al2O3%", "CaO%", "MgO%", "TiO2%",
        "Slag%", "Slag (MT)", "Cost/MT (₹)", "Total Cost (₹)", "Total Qty (MT)"
    ]
    display_cols = [c for c in display_cols if c in grid_df.columns]

    show_df = grid_df[display_cols].head(20).copy()

    # Format numeric columns
    for col in show_df.columns:
        if "₹" in col or "Cost" in col:
            show_df[col] = show_df[col].apply(lambda x: f"₹{x:,.0f}")
        elif "%" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.3f}%")
        elif "MT" in col:
            show_df[col] = show_df[col].apply(lambda x: f"{x:.1f}")

    st.dataframe(show_df, use_container_width=True)