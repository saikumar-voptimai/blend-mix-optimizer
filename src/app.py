import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import linprog
from utils.config import cfg
from data.influx_loader import InfluxRMClient
st.set_page_config(
    page_title="Ore Blend Optimizer — BF-02",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from data.ore_chemistry import load_ore_chemistry
from engine.optimizer import run_optimizer
from engine.grid_search import run_grid_search, estimate_combination_count
from engine.blend_calculator import FE_FROM_FEO_FACTOR
from ui.sidebar import render_sidebar
from ui.results import render_best_blend_card, render_top_blends_table
from ui.manual_blend import render_manual_blend_tab
from ui.charts import (
    render_pareto_scatter,
    render_composition_bar,
    render_radar_chart,
    render_fe_contribution_waterfall,
)
from utils.config import cfg


# ── Load chemistry data ───────────────────────────────────────────────────────
mode = st.sidebar.selectbox(
    "Chemistry Source Mode",
    ["latest", "avg"]
)

days = st.sidebar.slider(
    "History window (days)",
    1,
    90,
    cfg.influxdb.query.default_range_days
)

@st.cache_data(ttl=300)
def load_data(days, mode):
    return load_ore_chemistry(days=days, mode=mode)

chemistry_df = load_data(days, mode)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("⚙️ Ore Blend Optimizer — BF-02")
st.caption("BF-02 Bunker · Blast Furnace Blend Optimization System · FY 2025–26 Average Chemistry")
st.divider()


# ── Sidebar ───────────────────────────────────────────────────────────────────
operator_inputs = render_sidebar(chemistry_df)



# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Ore Catalogue",
    "🌟 Optimal Blend",
    "📊 Comparison Charts",
    "🎯 Blend Comparison",
    "🔧 Manual Blend",
])


# ── Tab 1: Ore Catalogue (always visible) ────────────────────────────────────
with tab1:
    st.subheader("Ore Chemistry Reference — BF-02 Bunker (2025-26 Averages)")
    display_cols = ["%Fe(T)", "%FeO", "%SiO2", "%Al2O3", "%CaO", "%MgO", "%TiO2", "%P", "%MnO", "%LOI", "Slag%"]
    display_cols = [c for c in display_cols if c in chemistry_df.columns]
    st.dataframe(
        chemistry_df[display_cols].style.format("{:.3f}"),
        width="stretch",
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


# ── No inputs yet — show placeholders ────────────────────────────────────────
if operator_inputs is None:
    with tab2:
        st.info("← Configure blend in sidebar: select ores, enter quantities & prices, then click Run Optimizer.")
    with tab3:
        st.info("Run the optimizer first to see charts.")
    with tab4:
        st.info("Run the optimizer first to compare blends.")
    with tab5:
        st.info("Run the optimizer first to enable manual blend comparison.")
    st.stop()


# ── Unpack operator inputs ────────────────────────────────────────────────────
selected_ores  = operator_inputs["selected_ores"]
max_quantities = operator_inputs["max_quantities"]
prices         = operator_inputs["prices"]
target_qty     = operator_inputs["target_qty"]
step_size      = operator_inputs["step_size"]
fuel_input     = operator_inputs.get("fuel_input", None)


# ── Run optimizer — cached in session state, only reruns when inputs change ───
_opt_cache_key = f"opt_{selected_ores}_{target_qty}_{list(max_quantities.values())}_{list(prices.values())}"

if st.session_state.get("_opt_cache_id") != _opt_cache_key:
    with st.spinner("Running cost optimizer..."):
        # st.subheader("Chemistry Data Used for Optimization")
        # st.dataframe(chemistry_df)
        optimal_result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            chemistry_df=chemistry_df,
        )
    st.session_state["_opt_cache_id"] = _opt_cache_key
    st.session_state["_opt_result"]   = optimal_result
else:
    optimal_result = st.session_state["_opt_result"]


# ── Optimizer failed — diagnose and stop ─────────────────────────────────────
if optimal_result is None:
    sinter_ores = [o for o in selected_ores if "sinter" in o.lower()]

    n = len(selected_ores)
    slag_c, fe_c, bounds, bound_info = [], [], [], []
    for ore in selected_ores:
        slag = sum(float(chemistry_df.loc[ore, col])
                   for col in ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]
                   if col in chemistry_df.columns)
        slag_c.append(slag * 0.01)
        fe_t = float(chemistry_df.loc[ore, "%Fe(T)"])
        feo  = float(chemistry_df.loc[ore, "%FeO"])
        fe_c.append(-(fe_t + feo * FE_FROM_FEO_FACTOR) * 0.01)
        if "sinter" in ore.lower():
            lo = cfg.sinter_min_pct * target_qty
            hi = min(cfg.sinter_max_pct * target_qty, max_quantities.get(ore, target_qty))
        else:
            mp = cfg.ore_max_pct.get(ore, cfg.fallback_max_pct)
            hi = min(mp / 100.0 * target_qty, max_quantities.get(ore, target_qty))
            lo = 0.0
        bounds.append((lo, hi))
        bound_info.append(f"{ore}: lo={lo:.0f} hi={hi:.0f}")

    c    = np.ones(n)
    A_eq = np.ones((1, n)); b_eq = np.array([target_qty])
    A_ub = np.array([slag_c, fe_c])
    b_ub = np.array([cfg.target_slag_qty, -cfg.min_fe_production_mt])

    r_none = linprog(c, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    r_slag = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub[:1], b_ub=b_ub[:1], bounds=bounds, method="highs")
    r_fe   = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub[1:], b_ub=b_ub[1:], bounds=bounds, method="highs")

    lines = ["**Optimizer could not find a feasible solution.**", ""]

    if not r_none.success:
        lo_sum = sum(b[0] for b in bounds)
        hi_sum = sum(b[1] for b in bounds)
        lines.append(f"- **Bounds infeasible:** sum lo={lo_sum:.0f} MT, sum hi={hi_sum:.0f} MT, target={target_qty:.0f} MT.")
        lines.append(f"  The selected ore caps (`ore_max_pct`) don't allow reaching the target quantity.")
        if sinter_ores:
            gap = target_qty - min(cfg.sinter_max_pct * target_qty, max_quantities.get(sinter_ores[0], target_qty))
            lines.append(f"  Non-sinter ores must cover **{gap:.0f} MT** but are capped at less.")
    elif not r_slag.success:
        nat_slag = sum(r_none.x[i] * slag_c[i] for i in range(n))
        lines.append(f"- **Slag constraint too tight:** minimum achievable slag = **{nat_slag:.0f} MT** but `target_slag_qty = {cfg.target_slag_qty:.0f} MT`.")
        lines.append(f"  Increase `target_slag_qty` in config.yaml to at least **{int(nat_slag) + 50} MT**.")
    elif not r_fe.success:
        nat_fe = -sum(r_none.x[i] * fe_c[i] for i in range(n))
        lines.append(f"- **Fe constraint too high:** max possible Fe production = **{nat_fe:.0f} MT** but `min_fe_production_mt = {cfg.min_fe_production_mt:.0f} MT`.")
        lines.append(f"  Reduce `min_fe_production_mt` in config.yaml to at most **{int(nat_fe) - 50} MT**, or add higher-Fe ores.")
    else:
        nat_slag = sum(r_none.x[i] * slag_c[i] for i in range(n))
        nat_fe   = -sum(r_none.x[i] * fe_c[i] for i in range(n))
        lines.append(f"- **Slag + Fe constraints conflict** when applied together.")
        lines.append(f"  Natural slag={nat_slag:.0f} MT (limit={cfg.target_slag_qty:.0f}), Natural Fe={nat_fe:.0f} MT (min={cfg.min_fe_production_mt:.0f} MT).")

    lines += ["", "**Ore bounds used:**"] + [f"- {b}" for b in bound_info]

    with tab2:
        st.error("\n".join(lines))
    st.stop()


# ── Grid search — cached in session state, only reruns when inputs change ────
_grid_cache_key = f"grid_df_{selected_ores}_{target_qty}_{step_size}_{list(max_quantities.values())}"

if st.session_state.get("_grid_cache_id") != _grid_cache_key:
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
    st.session_state["_grid_cache_id"] = _grid_cache_key
    st.session_state["_grid_df"]       = grid_df
else:
    grid_df = st.session_state["_grid_df"]


# ── Tab 2: Optimal Blend ──────────────────────────────────────────────────────
with tab2:
    render_best_blend_card(optimal_result, fuel_input)
    st.divider()
    render_top_blends_table(grid_df, fuel_input)


# ── Tab 3: Comparison Charts ──────────────────────────────────────────────────
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


# ── Tab 4: Blend Comparison ───────────────────────────────────────────────────
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
            st.subheader("Side-by-Side Chemistry Comparison")
            rows = [{"Blend": "★ Optimal", "Fe%": optimal_result.fe_pct,
                     "SiO2%": optimal_result.sio2_pct, "Al2O3%": optimal_result.al2o3_pct,
                     "CaO%": optimal_result.cao_pct, "MgO%": optimal_result.mgo_pct,
                     "TiO2%": optimal_result.tio2_pct, "Slag%": optimal_result.slag_pct,
                     "Slag MT": optimal_result.slag_mt, "Cost/MT (₹)": optimal_result.cost_per_mt}]
            for rank in selected_ranks:
                if 1 <= rank <= len(grid_df):
                    row = grid_df.iloc[rank - 1]
                    rows.append({"Blend": f"Rank {rank}", "Fe%": row["Fe%"],
                                 "SiO2%": row["SiO2%"], "Al2O3%": row["Al2O3%"],
                                 "CaO%": row["CaO%"], "MgO%": row["MgO%"],
                                 "TiO2%": row["TiO2%"], "Slag%": row["Slag%"],
                                 "Slag MT": row["Slag (MT)"], "Cost/MT (₹)": row["Cost/MT (₹)"]})
            compare_df = pd.DataFrame(rows).set_index("Blend")
            st.dataframe(compare_df.style.format("{:.3f}"), use_container_width=True)
    else:
        st.info("No results to compare.")


# ── Tab 5: Manual Blend ───────────────────────────────────────────────────────
with tab5:
    render_manual_blend_tab(
        selected_ores=selected_ores,
        prices=prices,
        chemistry_df=chemistry_df,
        optimal_result=optimal_result,
        fuel_input=fuel_input,
    )