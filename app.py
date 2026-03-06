"""
Ore Blend Mix Optimization System
BF-02 Blast Furnace — Bunker Ore Blend Optimizer
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Ore Blend Optimizer — BF-02",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from data.ore_chemistry import load_ore_chemistry
from engine.optimizer import run_optimizer
from engine.grid_search import run_grid_search, estimate_combination_count
from ui.sidebar import render_sidebar
from ui.results import render_best_blend_card, render_top_blends_table
from ui.charts import (
    render_pareto_scatter,
    render_composition_bar,
    render_radar_chart,
    render_fe_contribution_waterfall,
)


@st.cache_data
def load_data():
    return load_ore_chemistry()


def render_header():
    st.title("⚙️ Ore Blend Optimizer — BF-02")
    st.caption("BF-02 Bunker · Blast Furnace Blend Optimization System · FY 2025–26 Average Chemistry")
    st.divider()


def render_catalogue_tab(chemistry_df: pd.DataFrame):
    st.subheader("Ore Chemistry Reference — BF-02 Bunker (2025-26 Averages)")
    display_cols = ["%Fe(T)", "%FeO", "%SiO2", "%Al2O3", "%CaO", "%MgO", "%TiO2", "%P", "%MnO", "%LOI", "Slag%"]
    display_cols = [c for c in display_cols if c in chemistry_df.columns]
    st.dataframe(
        chemistry_df[display_cols].style.format("{:.3f}"),
        use_container_width=True,
        height=480,
    )
    st.caption(
        "Slag% = SiO2% + Al2O3% + CaO% + MgO% + MnO%  |  "
        "%FeO shown for Sinter only — informational, not added to Slag%"
    )
    with st.expander("ℹ️ Special Ore Notes"):
        st.markdown("""
        - **Acore Industries** — Mn ore (MnO ~22%). Very low Fe (~27%). Use only if Mn addition is intentional.
        - **Titani Ferrous CLO** — TiO2 ~12.2%. High titanium loads slag and can damage furnace lining.
        - **NMDC Donimalai** — SiO2 ~14.4%. Heavy slag burden if used in large quantities.
        - **Sinter (SP-02)** — Self-fluxing. High CaO (~10.6%) reduces external limestone need. FeO ~9.2% indicates partial oxidation state — Fe(T)% already includes all iron forms.
        """)


def main():
    chemistry_df = load_data()
    render_header()

    operator_inputs = render_sidebar(chemistry_df)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Ore Catalogue",
        "💰 Optimal Blend",
        "📊 Comparison Charts",
        "🎯 Blend Comparison",
    ])

    with tab1:
        render_catalogue_tab(chemistry_df)

    if operator_inputs is None:
        with tab2:
            st.info("← Configure blend in sidebar: select ores, enter quantities & prices, then click Run Optimizer.")
        with tab3:
            st.info("Run the optimizer first to see charts.")
        with tab4:
            st.info("Run the optimizer first to compare blends.")
        return

    selected_ores  = operator_inputs["selected_ores"]
    max_quantities = operator_inputs["max_quantities"]
    prices         = operator_inputs["prices"]
    target_qty     = operator_inputs["target_qty"]
    step_size      = operator_inputs["step_size"]

    with st.spinner("Running cost optimizer..."):
        optimal_result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            chemistry_df=chemistry_df,
        )

    if optimal_result is None:
        st.error("Optimizer could not find a feasible solution. Check that total available ≥ target.")
        return

    est_count = estimate_combination_count(
        selected_ores, optimal_result.quantities, max_quantities, target_qty, step_size
    )

    with st.spinner(f"Running grid search (~{est_count} combinations)..."):
        grid_df = run_grid_search(
            selected_ores=selected_ores,
            optimal_quantities=optimal_result.quantities,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            step_size=step_size,
            chemistry_df=chemistry_df,
        )

    with tab2:
        render_best_blend_card(optimal_result)
        st.divider()
        render_top_blends_table(grid_df)

    with tab3:
        if not grid_df.empty:
            st.subheader("Pareto Front — All Valid Blends")
            render_pareto_scatter(grid_df, optimal_result)
            st.divider()
            st.subheader("Fe% Contribution per Ore")
            render_fe_contribution_waterfall(optimal_result, chemistry_df)
            st.divider()
            st.subheader("Blend Composition — Top 10 Blends")
            render_composition_bar(grid_df, selected_ores, top_n=10)
        else:
            st.info("No grid search results. Try a smaller step size.")

    with tab4:
        if not grid_df.empty:
            max_rank = min(20, len(grid_df))
            selected_ranks = st.multiselect(
                "Select ranks to compare (2–5 blends)",
                options=list(range(1, max_rank + 1)),
                default=[1, 2, 3] if max_rank >= 3 else list(range(1, max_rank + 1)),
                max_selections=5,
            )
            if selected_ranks:
                render_radar_chart(grid_df, selected_ranks, optimal_result)
                st.divider()
                _render_comparison_table(grid_df, selected_ranks, optimal_result)
        else:
            st.info("No results to compare.")


def _render_comparison_table(grid_df: pd.DataFrame, selected_ranks: list,
                              optimal_result=None):
    """Side-by-side chemistry comparison table."""
    st.subheader("Side-by-Side Chemistry Comparison")
    rows = []

    if optimal_result:
        rows.append({
            "Blend":       "★ Optimal",
            "Fe%":         optimal_result.fe_pct,
            "SiO2%":       optimal_result.sio2_pct,
            "Al2O3%":      optimal_result.al2o3_pct,
            "CaO%":        optimal_result.cao_pct,
            "MgO%":        optimal_result.mgo_pct,
            "TiO2%":       optimal_result.tio2_pct,
            "Slag%":       optimal_result.slag_pct,
            "Slag MT":     optimal_result.slag_mt,
            "Cost/MT (₹)": optimal_result.cost_per_mt,
        })

    for rank in selected_ranks:
        if 1 <= rank <= len(grid_df):
            row = grid_df.iloc[rank - 1]
            rows.append({
                "Blend":       f"Rank {rank}",
                "Fe%":         row["Fe%"],
                "SiO2%":       row["SiO2%"],
                "Al2O3%":      row["Al2O3%"],
                "CaO%":        row["CaO%"],
                "MgO%":        row["MgO%"],
                "TiO2%":       row["TiO2%"],
                "Slag%":       row["Slag%"],
                "Slag MT":     row["Slag (MT)"],
                "Cost/MT (₹)": row["Cost/MT (₹)"],
            })

    if rows:
        compare_df = pd.DataFrame(rows).set_index("Blend")
        st.dataframe(compare_df.style.format("{:.3f}"), use_container_width=True)


if __name__ == "__main__":
    main()