import streamlit as st
import pandas as pd

from utils.config import cfg, persist_overrides
from data.ore_chemistry import load_ore_chemistry
from data.influx_loader import InfluxClient
from engine.optimizer import run_optimizer
from engine.grid_search import run_grid_search, estimate_combination_count
from engine.fuel_calculator import FuelInput

from ui.results import render_best_blend_card, render_top_blends_table
from ui.charts import (
    render_pareto_scatter,
    render_composition_bar,
    render_fe_contribution_waterfall,
)
from ui.manual_blend import render_manual_blend_tab
from ui.styles import apply_styles, info_banner


# PAGE CONFIG


st.set_page_config(
    page_title="Ore Blend Optimizer",
    layout="wide",
)

apply_styles()


# LOAD DATA

with st.sidebar.form("chemistry_form"):
    mode = st.selectbox(
        "Chemistry Source Mode",
        ["latest", "avg"],
        index=0 if st.session_state.get("mode", "latest") == "latest" else 1
    )

    days = st.slider(
        "History window (days)",
        1,
        90,
        st.session_state.get("days", cfg.influxdb.query.default_range_days)
    )
    submit_sidebar = st.form_submit_button("Load Chemistry")
    
# CONTROL EXECUTION USING SUBMIT BUTTON
if "sidebar_submitted" not in st.session_state:
    st.session_state.sidebar_submitted = False

if submit_sidebar:
    st.session_state.sidebar_submitted = True
    st.session_state.mode = mode
    st.session_state.days = days

# Stop app until user clicks submit
if not st.session_state.sidebar_submitted:
    st.stop()

# Use stored values
mode = st.session_state.mode
days = st.session_state.days


@st.cache_data(ttl=300)
def load_data(days, mode):
    return load_ore_chemistry(days=days, mode=mode)


chemistry_df = load_data(days, mode)


@st.cache_data(ttl=300)
def load_stock():
    client = InfluxClient()
    return client.get_stock_map(cfg.influxdb.stock_materials)


stock_map = load_stock()

# INPUT PANEL


with st.expander("⚙️  Blend Configuration", expanded=True):

    # ── Step 1 — Select Ores ─────────────────────────

    st.markdown('<div class="step-header">① &nbsp; Select Ores</div>',
                unsafe_allow_html=True)

    selected_ores = []
    ore_list = list(chemistry_df.index)
    cols = st.columns(5)
    for i, ore in enumerate(ore_list):
        if cols[i % 5].checkbox(ore, key=f"ore_{ore}"):
            selected_ores.append(ore)

    if selected_ores:
        chips = "".join(
            f'<span class="summary-chip">{o}</span>' for o in selected_ores)
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
    hc_ore.markdown('<div class="col-header">Ore / Vendor</div>',
                    unsafe_allow_html=True)
    hc_qty.markdown(
        '<div class="col-header">Available in Yard (MT)</div>', unsafe_allow_html=True)
    hc_price.markdown(
        '<div class="col-header">Price (₹ / MT)</div>', unsafe_allow_html=True)

    for ore in selected_ores:
        c_ore, c_qty, c_price = st.columns([3, 2, 2])
        c_ore.markdown(
            f'<div class="ore-label">🪨 &nbsp;{ore}</div>', unsafe_allow_html=True)
        raw_qty = float(stock_map.get(ore, cfg.default_target_qty))
        default_qty = max(0.0, raw_qty)

        max_quantities[ore] = c_qty.number_input(
            f"qty_{ore}",
            min_value=0.0,
            value=default_qty,
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

    st.markdown('<div class="step-header">③ &nbsp; Fuel Inputs</div>',
                unsafe_allow_html=True)

    # Headers
    _, fh1, fh2, fh3 = st.columns([2, 2, 2, 2])
    fh1.markdown('<div class="fuel-col-header">🔥 Coke</div>',
                 unsafe_allow_html=True)
    fh2.markdown('<div class="fuel-col-header">🔥 Nut Coke</div>',
                 unsafe_allow_html=True)
    fh3.markdown('<div class="fuel-col-header">💨 PCI</div>',
                 unsafe_allow_html=True)

    # Quantity row
    fl0, fl1, fl2, fl3 = st.columns([2, 2, 2, 2])
    fl0.markdown(
        '<div style="padding-top:7px; font-size:13px; font-weight:500; color:#444;">Quantity (MT)</div>', unsafe_allow_html=True)
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
    fl0b.markdown(
        '<div style="padding-top:7px; font-size:13px; font-weight:500; color:#444;">Ash %</div>', unsafe_allow_html=True)
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

    # ── Constraint Overrides (persist to config.yaml) ───────────────────────

    with st.expander("🧰  Constraint Overrides (persist)", expanded=False):
        st.caption(
            "Edits here are saved to config/config.yaml and apply to the optimizer and grid search. "
            "Slag limit is treated as TOTAL BF slag (ore + fuel)."
        )

        new_target_slag = st.number_input(
            "Target Total Slag (MT)",
            min_value=0.0,
            value=float(cfg.target_slag_qty),
            step=10.0,
            key="override_target_slag_qty",
        )

        limits_rows = []
        for ore in selected_ores:
            limits_rows.append(
                {
                    "Ore / Vendor": ore,
                    "Min %": float(cfg.ore_min_pct.get(ore, cfg.fallback_min_pct)),
                    "Max %": float(cfg.ore_max_pct.get(ore, cfg.fallback_max_pct)),
                }
            )

        limits_df = pd.DataFrame(limits_rows)
        edited_limits_df = st.data_editor(
            limits_df,
            hide_index=True,
            use_container_width=True,
            disabled=["Ore / Vendor"],
            column_config={
                "Min %": st.column_config.NumberColumn("Min %", min_value=0.0, max_value=100.0, step=0.5),
                "Max %": st.column_config.NumberColumn("Max %", min_value=0.0, max_value=100.0, step=0.5),
            },
        )

        save_col, reset_col = st.columns([1, 1])
        save_clicked = save_col.button("💾 Save overrides", type="primary")
        reset_clicked = reset_col.button("↩️ Reset to YAML values")

        if reset_clicked:
            # Force a rerun so the editor re-initializes from cfg
            st.rerun()

        if save_clicked:
            ore_min_updates: dict[str, float] = {}
            ore_max_updates: dict[str, float] = {}

            for _, row in edited_limits_df.iterrows():
                ore = str(row["Ore / Vendor"])
                mn = float(row["Min %"])
                mx = float(row["Max %"])
                if mn > mx:
                    st.error(f"Min% cannot exceed Max% for {ore}.")
                    st.stop()
                ore_min_updates[ore] = mn
                ore_max_updates[ore] = mx

            persist_overrides(
                ore_min_pct=ore_min_updates,
                ore_max_pct=ore_max_updates,
                target_slag_qty=float(new_target_slag),
            )

            st.success("Saved. Overrides will apply on this run.")
            st.rerun()

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
            width="stretch",
        )
    st.markdown('</div>', unsafe_allow_html=True)

# RUN OPTIMIZER

if run_btn:
    with st.spinner("⚙️ Running optimizer..."):
        optimal_result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            chemistry_df=chemistry_df,
            min_fe_production_mt=min_fe_production_mt,
            max_fe_production_mt=max_fe_production_mt,
            fuel_input=fuel_input,
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
            fuel_input=fuel_input,
        )

    st.session_state["optimal_result"] = optimal_result
    st.session_state["grid_df"] = grid_df
    st.session_state["selected_ores"] = selected_ores
    st.session_state["prices"] = prices
    st.session_state["fuel_input"] = fuel_input
    st.session_state["min_fe_production_mt"] = min_fe_production_mt
    st.session_state["max_fe_production_mt"] = max_fe_production_mt


# REQUIRE OPTIMIZER RUN

if "optimal_result" not in st.session_state:
    info_banner()
    st.stop()

optimal_result = st.session_state["optimal_result"]
grid_df = st.session_state["grid_df"]
selected_ores = st.session_state["selected_ores"]
prices = st.session_state["prices"]
fuel_input = st.session_state["fuel_input"]
min_fe_production_mt = st.session_state["min_fe_production_mt"]


# TABS


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
    render_best_blend_card(optimal_result, fuel_input,
                           min_fe_production_mt=min_fe_production_mt)


with tab3:
    if not grid_df.empty:
        render_pareto_scatter(grid_df, optimal_result)
        st.divider()
        render_composition_bar(grid_df, selected_ores)
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
