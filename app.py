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
from ui.styles import apply_styles, info_banner


# -------------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------------

st.set_page_config(
    page_title="BF-02 Ore Blend Optimizer",
    layout="wide",
)

apply_styles()


# -------------------------------------------------------
# LOAD DATA
# -------------------------------------------------------

@st.cache_data
def load_data():
    return load_ore_chemistry()

chemistry_df = load_data()


# -------------------------------------------------------
# INPUT PANEL
# -------------------------------------------------------

with st.expander("⚙️  Blend Configuration", expanded=True):

    # ── Step 1 — Select Ores ─────────────────────────

    st.markdown('<div class="step-header">① &nbsp; Select Ores</div>', unsafe_allow_html=True)

    selected_ores = []
    ore_list = list(chemistry_df.index)
    cols = st.columns(5)
    for i, ore in enumerate(ore_list):
        if cols[i % 5].checkbox(ore, key=f"ore_{ore}"):
            selected_ores.append(ore)

    if selected_ores:
        chips = "".join(f'<span class="summary-chip">{o}</span>' for o in selected_ores)
        st.markdown(
            f'<div style="margin-top:6px;">{len(selected_ores)} selected: &nbsp;{chips}</div>',
            unsafe_allow_html=True,
        )

    if len(selected_ores) < 2:
        st.warning("Select at least 2 ores to continue.")
        st.stop()

    st.divider()

    # ── Step 2 — Vendor Quantities & Prices (combined) ──

    st.markdown(
        '<div class="step-header">② &nbsp; Vendor Quantities &amp; Prices</div>',
        unsafe_allow_html=True,
    )

    max_quantities: dict = {}
    prices: dict = {}

    # Column header row
    hc_ore, hc_qty, hc_price = st.columns([3, 2, 2])
    hc_ore.markdown('<div class="col-header">Ore / Vendor</div>', unsafe_allow_html=True)
    hc_qty.markdown('<div class="col-header">Available in Yard (MT)</div>', unsafe_allow_html=True)
    hc_price.markdown('<div class="col-header">Price (₹ / MT)</div>', unsafe_allow_html=True)

    for ore in selected_ores:
        c_ore, c_qty, c_price = st.columns([3, 2, 2])
        c_ore.markdown(f'<div class="ore-label">🪨 &nbsp;{ore}</div>', unsafe_allow_html=True)
        max_quantities[ore] = c_qty.number_input(
            f"qty_{ore}",
            min_value=0.0,
            value=float(cfg.default_target_qty),
            step=10.0,
            key=f"qty_{ore}",
            label_visibility="collapsed",
        )
        prices[ore] = c_price.number_input(
            f"price_{ore}",
            min_value=0.0,
            value=float(cfg.ore_prices.get(ore, cfg.fallback_price)),
            step=100.0,
            key=f"price_{ore}",
            label_visibility="collapsed",
        )

    st.divider()

    # ── Step 3 — Fuel Inputs ─────────────────────────

    st.markdown('<div class="step-header">③ &nbsp; Fuel Inputs</div>', unsafe_allow_html=True)

    # Headers
    _, fh1, fh2, fh3 = st.columns([2, 2, 2, 2])
    fh1.markdown('<div class="fuel-col-header">🔥 Coke</div>', unsafe_allow_html=True)
    fh2.markdown('<div class="fuel-col-header">🔥 Nut Coke</div>', unsafe_allow_html=True)
    fh3.markdown('<div class="fuel-col-header">💨 PCI</div>', unsafe_allow_html=True)

    # Quantity row
    fl0, fl1, fl2, fl3 = st.columns([2, 2, 2, 2])
    fl0.markdown('<div style="padding-top:7px; font-size:13px; font-weight:500; color:#444;">Quantity (MT)</div>', unsafe_allow_html=True)
    coke_qty = fl1.number_input(
        "Coke Qty (MT)", min_value=0.0, value=float(cfg.coke_defaults["qty_mt"]),
        step=10.0, key="coke_qty", label_visibility="collapsed",
    )
    nut_coke_qty = fl2.number_input(
        "Nut Coke Qty (MT)", min_value=0.0, value=float(cfg.nut_coke_defaults["qty_mt"]),
        step=10.0, key="nut_coke_qty", label_visibility="collapsed",
    )
    pci_qty = fl3.number_input(
        "PCI Qty (MT)", min_value=0.0, value=float(cfg.pci_defaults["qty_mt"]),
        step=10.0, key="pci_qty", label_visibility="collapsed",
    )

    # Ash row
    fl0b, fl1b, fl2b, fl3b = st.columns([2, 2, 2, 2])
    fl0b.markdown('<div style="padding-top:7px; font-size:13px; font-weight:500; color:#444;">Ash %</div>', unsafe_allow_html=True)
    coke_ash = fl1b.number_input(
        "Coke Ash %", min_value=0.0, max_value=100.0, value=float(cfg.coke_defaults["ash_pct"]),
        step=0.1, key="coke_ash", label_visibility="collapsed",
    )
    nut_coke_ash = fl2b.number_input(
        "Nut Coke Ash %", min_value=0.0, max_value=100.0, value=float(cfg.nut_coke_defaults["ash_pct"]),
        step=0.1, key="nut_coke_ash", label_visibility="collapsed",
    )
    pci_ash = fl3b.number_input(
        "PCI Ash %", min_value=0.0, max_value=100.0, value=float(cfg.pci_defaults["ash_pct"]),
        step=0.1, key="pci_ash", label_visibility="collapsed",
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

    # ── Step 4 — Search Settings & Fe Range (combined) ──

    st.markdown(
        '<div class="step-header">④ &nbsp; Search Settings &amp; Fe Production Range</div>',
        unsafe_allow_html=True,
    )

    sc1, sc2, sc3 = st.columns(3)

    step_size = sc1.select_slider(
        "Grid Search Step (MT)",
        options=[5, 10, 25, 50, 100],
        value=10,
        key="step_size",
        help="Smaller step = more combinations explored, slower run",
    )
    min_fe_production_mt = sc2.number_input(
        "Min Fe Production (MT)",
        min_value=0.0,
        value=float(cfg.min_fe_production_mt),
        step=10.0,
        key="min_fe",
    )
    max_fe_production_mt = sc3.number_input(
        "Max Fe Production (MT)",
        min_value=0.0,
        value=float(cfg.max_fe_production_mt),
        step=10.0,
        key="max_fe",
    )

    st.divider()

    # ── Run Button ────────────────────────────────────

    st.markdown('<div class="run-wrapper">', unsafe_allow_html=True)
    rb_l, rb_c, rb_r = st.columns([1, 2, 1])
    with rb_c:
        run_btn = st.button(
            "🚀  Run Optimizer",
            type="primary",
            use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


# -------------------------------------------------------
# RUN OPTIMIZER
# -------------------------------------------------------

if run_btn:
    with st.spinner("⚙️ Running optimizer..."):
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
            "**Optimizer could not find a feasible blend.**\n\n"
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

    with st.spinner(f"📊 Running grid search (~{est_count:,} combinations)..."):
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
    info_banner()
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
