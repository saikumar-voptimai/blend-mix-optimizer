import streamlit as st

from config.config import cfg
from data.ore_chemistry import load_ore_chemistry

from engine.optimizer import run_optimizer
from engine.grid_search import run_grid_search, estimate_combination_count
from engine.fuel_calculator import FuelInput

from ui.results import render_best_blend_card, render_top_blends_table
from ui.charts import (
    render_pareto_scatter,
    render_composition_bar,
    render_radar_chart,
    render_fe_contribution_waterfall,
)
from ui.manual_blend import render_manual_blend_tab


# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------

st.set_page_config(
    page_title="BF-02 Ore Blend Optimizer",
    layout="wide",
)

st.title("⚙️ Ore Blend Optimizer — BF-02")
st.caption("Blast Furnace Burden Optimization System")


# -------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------

@st.cache_data
def load_data():
    return load_ore_chemistry()

chemistry_df = load_data()


# -------------------------------------------------------
# INPUT UI
# -------------------------------------------------------

with st.expander("⚙️ Blend Configuration", expanded=True):
    st.subheader("Step 1 — Select Ores")

    selected_ores = []
    cols = st.columns(4)
    for i, ore in enumerate(chemistry_df.index):
        if cols[i % 4].checkbox(ore, key=f"ore_{ore}"):
            selected_ores.append(ore)

    if len(selected_ores) < 2:
        st.warning("Select at least 2 ores to continue.")
        st.stop()

    st.divider()

    st.subheader("Step 2 — Available Quantities (MT)")
    max_quantities = {}
    cols = st.columns(4)
    for i, ore in enumerate(selected_ores):
        max_quantities[ore] = cols[i % 4].number_input(
            f"{ore}",
            min_value=0.0,
            value=float(cfg.default_target_qty),
            step=10.0,
            key=f"qty_{ore}",
        )

    st.divider()

    st.subheader("Step 3 — Ore Prices (₹/MT)")
    prices = {}
    cols = st.columns(4)
    for i, ore in enumerate(selected_ores):
        prices[ore] = cols[i % 4].number_input(
            f"{ore} price",
            min_value=0.0,
            value=float(cfg.ore_prices.get(ore, cfg.fallback_price)),
            step=100.0,
            key=f"price_{ore}",
        )

    st.divider()

    st.subheader("Step 4 — Fuel Inputs")
    c1, c2, c3 = st.columns(3)

    coke_qty = c1.number_input(
        "Coke Qty (MT)",
        min_value=0.0,
        value=float(cfg.coke_defaults["qty_mt"]),
        step=10.0,
        key="coke_qty",
    )
    coke_ash = c1.number_input(
        "Coke Ash %",
        min_value=0.0,
        max_value=100.0,
        value=float(cfg.coke_defaults["ash_pct"]),
        step=0.1,
        key="coke_ash",
    )

    nut_coke_qty = c2.number_input(
        "Nut Coke Qty (MT)",
        min_value=0.0,
        value=float(cfg.nut_coke_defaults["qty_mt"]),
        step=10.0,
        key="nut_coke_qty",
    )
    nut_coke_ash = c2.number_input(
        "Nut Coke Ash %",
        min_value=0.0,
        max_value=100.0,
        value=float(cfg.nut_coke_defaults["ash_pct"]),
        step=0.1,
        key="nut_coke_ash",
    )

    pci_qty = c3.number_input(
        "PCI Qty (MT)",
        min_value=0.0,
        value=float(cfg.pci_defaults["qty_mt"]),
        step=10.0,
        key="pci_qty",
    )
    pci_ash = c3.number_input(
        "PCI Ash %",
        min_value=0.0,
        max_value=100.0,
        value=float(cfg.pci_defaults["ash_pct"]),
        step=0.1,
        key="pci_ash",
    )

    fuel_input = FuelInput(
        coke_qty_mt=coke_qty,
        coke_ash_pct=coke_ash,
        nut_coke_qty_mt=nut_coke_qty,
        nut_coke_ash_pct=nut_coke_ash,
        pci_qty_mt=pci_qty,
        pci_ash_pct=pci_ash,
    )

    st.divider()

    st.subheader("Step 5 — Grid Search Step")
    step_size = st.select_slider(
        "Grid search step size (MT)",
        options=[5, 10, 25, 50, 100],
        value=10,
        key="step_size",
    )

    st.divider()

    st.subheader("Step 6 — Fe Production Range")
    col1, col2 = st.columns(2)

    min_fe_production_mt = col1.number_input(
        "Minimum Fe Production (MT)",
        min_value=0.0,
        value=float(cfg.min_fe_production_mt),
        step=10.0,
        key="min_fe",
    )
    max_fe_production_mt = col2.number_input(
        "Maximum Fe Production (MT)",
        min_value=0.0,
        value=float(cfg.max_fe_production_mt),
        step=10.0,
        key="max_fe",
    )

    run_btn = st.button("Run Optimizer", type="primary")


# -------------------------------------------------------
# RUN OPTIMIZER
# -------------------------------------------------------

if run_btn:
    with st.spinner("Running optimizer..."):
        optimal_result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            chemistry_df=chemistry_df,
            min_fe_production_mt=min_fe_production_mt,
            max_fe_production_mt=max_fe_production_mt,
        )

    if optimal_result is None:
        st.session_state.pop("optimal_result", None)
        st.session_state.pop("grid_df", None)
        st.error(
            "Optimizer could not find a feasible blend.\n\n"
            "Possible reasons:\n"
            "- Fe production limits are too strict\n"
            "- Slag limit is too strict\n"
            "- Ore min/max percentage constraints are too restrictive\n"
            "- Selected ore availability is too low"
        )
        st.stop()

    est_count = estimate_combination_count(
        selected_ores=selected_ores,
        optimal_quantities=optimal_result.quantities,
        max_quantities=max_quantities,
        step_size=step_size,
    )

    with st.spinner(f"Running grid search (~{est_count:,} combinations)..."):
        grid_df = run_grid_search(
            selected_ores=selected_ores,
            optimal_quantities=optimal_result.quantities,
            max_quantities=max_quantities,
            prices=prices,
            step_size=step_size,
            chemistry_df=chemistry_df,
            min_fe_production_mt=min_fe_production_mt,
            max_fe_production_mt=max_fe_production_mt,
        )

    st.session_state["optimal_result"] = optimal_result
    st.session_state["grid_df"] = grid_df
    st.session_state["selected_ores"] = selected_ores
    st.session_state["prices"] = prices
    st.session_state["fuel_input"] = fuel_input
    st.session_state["min_fe_production_mt"] = min_fe_production_mt
    st.session_state["max_fe_production_mt"] = max_fe_production_mt


# -------------------------------------------------------
# REQUIRE OPTIMIZER RUN
# -------------------------------------------------------

if "optimal_result" not in st.session_state:
    st.info("Configure inputs above and click **Run Optimizer**.")
    st.stop()

optimal_result = st.session_state["optimal_result"]
grid_df = st.session_state["grid_df"]
selected_ores = st.session_state["selected_ores"]
prices = st.session_state["prices"]
fuel_input = st.session_state["fuel_input"]
min_fe_production_mt = st.session_state["min_fe_production_mt"]


# -------------------------------------------------------
# TABS
# -------------------------------------------------------

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Ore Catalogue",
    "🏆 Optimal Blend",
    "📊 Comparison Charts",
    "📑 Blend Comparison",
    "🔧 Manual Blend",
])


with tab1:
    st.subheader("Ore Chemistry Catalogue")
    st.dataframe(chemistry_df, width="stretch")


with tab2:
    render_best_blend_card(optimal_result, fuel_input, min_fe_production_mt=min_fe_production_mt)


with tab3:
    if not grid_df.empty:
        render_pareto_scatter(grid_df, optimal_result)
        st.divider()
        render_composition_bar(grid_df, selected_ores)
        st.divider()
        render_radar_chart(grid_df, [2, 3, 4], optimal_result)
        st.divider()
        render_fe_contribution_waterfall(optimal_result, chemistry_df)
    else:
        st.info("No grid search results to plot.")


with tab4:
    render_top_blends_table(grid_df, fuel_input)


with tab5:
    render_manual_blend_tab(
        selected_ores=selected_ores,
        prices=prices,
        chemistry_df=chemistry_df,
        optimal_result=optimal_result,
        fuel_input=fuel_input,
    )