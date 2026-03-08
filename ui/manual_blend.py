"""
Manual Blend Tab — Operator enters their own blend quantities,
compares against the optimizer's result: cost, Fe%, slag, chemistry.

Uses session_state to store comparison results so clicking Compare
does not re-trigger the optimizer or grid search in app.py.
"""

import streamlit as st
import pandas as pd
from engine.blend_calculator import calculate_blend, BlendResult
from engine.fuel_calculator import calculate_fuel_slag, FuelInput
from config.config import cfg

MANUAL_RESULT_KEY = "manual_blend_result"


def render_manual_blend_tab(
    selected_ores: list,
    prices: dict,
    chemistry_df: pd.DataFrame,
    optimal_result: BlendResult,
    fuel_input: FuelInput = None,
):
    st.subheader("🔧 Manual Blend vs Optimal Blend")
    st.caption("Enter your own quantities for the selected ores, then hit Compare.")

    if not selected_ores:
        st.info("Run the optimizer first to load selected ores.")
        return

    # ── Operator quantity inputs ──────────────────────────────────────────────
    st.markdown("**Enter your blend quantities (MT):**")

    cols = st.columns(min(len(selected_ores), 4))
    manual_quantities = {}
    for i, ore in enumerate(selected_ores):
        col = cols[i % 4]
        default = float(optimal_result.quantities.get(ore, 0.0))
        qty = col.number_input(
            ore,
            min_value=0.0,
            max_value=99999.0,
            value=default,
            step=10.0,
            key=f"manual_qty_{ore}",
        )
        manual_quantities[ore] = qty

    manual_total = sum(manual_quantities.values())
    optimal_total = optimal_result.total_qty
    st.caption(f"Manual total: **{manual_total:.0f} MT**  |  Optimal total: **{optimal_total:.0f} MT**")

    if manual_total <= 0:
        st.warning("Enter at least some quantity to compare.")
        return

    # ── Compare button — stores result in session_state, no full rerun ────────
    if st.button("⚖️ Compare Blends", type="primary"):
        active_manual = {ore: qty for ore, qty in manual_quantities.items() if qty > 0}
        try:
            result = calculate_blend(active_manual, prices, chemistry_df)
            st.session_state[MANUAL_RESULT_KEY] = {
                "result":     result,
                "quantities": manual_quantities,
            }
        except Exception as e:
            st.error(f"Could not calculate manual blend: {e}")
            st.session_state.pop(MANUAL_RESULT_KEY, None)

    # ── Show results if available ─────────────────────────────────────────────
    if MANUAL_RESULT_KEY not in st.session_state:
        return

    manual_result    = st.session_state[MANUAL_RESULT_KEY]["result"]
    manual_quantities = st.session_state[MANUAL_RESULT_KEY]["quantities"]

    # ── Fuel results ──────────────────────────────────────────────────────────
    fuel_result = calculate_fuel_slag(fuel_input) if fuel_input else None

    def gross_and_net_fe(result: BlendResult):
        ore_fe_mt  = result.effective_fe_pct / 100.0 * result.total_qty
        fuel_fe_mt = fuel_result.total_fuel_fe_mt if fuel_result else 0.0
        gross_fe   = (ore_fe_mt + fuel_fe_mt) / result.total_qty * 100
        net_fe     = gross_fe - cfg.fe_loss_constant
        return round(gross_fe, 3), round(net_fe, 3)

    def total_slag_mt(result: BlendResult):
        return result.slag_mt + (fuel_result.total_fuel_slag_mt if fuel_result else 0.0)

    opt_gross_fe, opt_net_fe = gross_and_net_fe(optimal_result)
    man_gross_fe, man_net_fe = gross_and_net_fe(manual_result)
    opt_total_slag           = total_slag_mt(optimal_result)
    man_total_slag           = total_slag_mt(manual_result)

    cost_delta  = manual_result.cost_per_mt - optimal_result.cost_per_mt
    fe_delta    = man_gross_fe              - opt_gross_fe
    slag_delta  = man_total_slag            - opt_total_slag
    total_delta = manual_result.total_cost  - optimal_result.total_cost

    st.divider()

    # ── Summary verdict (top, most important) ────────────────────────────────
    if cost_delta > 0:
        st.error(
            f"🔴 Manual blend costs **₹{cost_delta:,.0f}/MT more** than optimizer. "
            f"Extra spend: **₹{total_delta/1e5:.2f} Lakhs** for this batch."
        )
    elif cost_delta < 0:
        st.success(
            f"🟢 Manual blend costs **₹{abs(cost_delta):,.0f}/MT less** than optimizer. "
            f"Saving: **₹{abs(total_delta)/1e5:.2f} Lakhs** for this batch."
        )
    else:
        st.info("Manual and optimal blends have the same cost/MT.")

    st.divider()

    # ── Side-by-side metrics ──────────────────────────────────────────────────
    st.markdown("### 📊 Side-by-Side Comparison")

    def arrow(val, lower_is_better=True):
        if abs(val) < 0.005:
            return "—"
        better = (val < 0) if lower_is_better else (val > 0)
        color  = "#21c55d" if better else "#ff4b4b"
        symbol = "▼" if val < 0 else "▲"
        return f'<span style="color:{color}">{symbol} {abs(val):.3g}</span>'

    rows = [
        ("Cost/MT (₹)",        f"₹{optimal_result.cost_per_mt:,.0f}",    f"₹{manual_result.cost_per_mt:,.0f}",    arrow(cost_delta, True)),
        ("Total Cost",         f"₹{optimal_result.total_cost/1e5:.2f}L",  f"₹{manual_result.total_cost/1e5:.2f}L", arrow(total_delta/1e5, True)),
        ("Total Qty (MT)",     f"{optimal_result.total_qty:.0f}",          f"{manual_result.total_qty:.0f}",         arrow(manual_result.total_qty - optimal_result.total_qty, False)),
        ("Gross Fe%",          f"{opt_gross_fe:.3f}%",                     f"{man_gross_fe:.3f}%",                   arrow(fe_delta, False)),
        ("Net Fe% (HM)",       f"{opt_net_fe:.3f}%",                       f"{man_net_fe:.3f}%",                     arrow(fe_delta, False)),
        ("Ore Slag (MT)",      f"{optimal_result.slag_mt:.1f}",            f"{manual_result.slag_mt:.1f}",           arrow(manual_result.slag_mt - optimal_result.slag_mt, True)),
        ("Total BF Slag (MT)", f"{opt_total_slag:.1f}",                    f"{man_total_slag:.1f}",                  arrow(slag_delta, True)),
        ("SiO2%",              f"{optimal_result.sio2_pct:.3f}%",          f"{manual_result.sio2_pct:.3f}%",         arrow(manual_result.sio2_pct - optimal_result.sio2_pct, True)),
        ("Al2O3%",             f"{optimal_result.al2o3_pct:.3f}%",         f"{manual_result.al2o3_pct:.3f}%",        arrow(manual_result.al2o3_pct - optimal_result.al2o3_pct, True)),
        ("CaO%",               f"{optimal_result.cao_pct:.3f}%",           f"{manual_result.cao_pct:.3f}%",          arrow(manual_result.cao_pct - optimal_result.cao_pct, True)),
        ("MgO%",               f"{optimal_result.mgo_pct:.3f}%",           f"{manual_result.mgo_pct:.3f}%",          arrow(manual_result.mgo_pct - optimal_result.mgo_pct, True)),
        ("TiO2%",              f"{optimal_result.tio2_pct:.3f}%",          f"{manual_result.tio2_pct:.3f}%",         arrow(manual_result.tio2_pct - optimal_result.tio2_pct, True)),
        ("Slag%",              f"{optimal_result.slag_pct:.3f}%",          f"{manual_result.slag_pct:.3f}%",         arrow(manual_result.slag_pct - optimal_result.slag_pct, True)),
    ]

    h1, h2, h3, h4 = st.columns([2, 1.5, 1.5, 1])
    h1.markdown("**Metric**"); h2.markdown("**✅ Optimizer**")
    h3.markdown("**🔧 Manual**"); h4.markdown("**Δ**")

    for label, opt_val, man_val, diff_html in rows:
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 1])
        c1.markdown(f"**{label}**")
        c2.markdown(opt_val)
        c3.markdown(man_val)
        c4.markdown(diff_html, unsafe_allow_html=True)

    st.divider()

    # ── Ore-by-ore cost breakdown ─────────────────────────────────────────────
    st.markdown("### 🪨 Ore-by-Ore Breakdown")

    ore_rows = []
    for ore in selected_ores:
        opt_qty  = optimal_result.quantities.get(ore, 0.0)
        man_qty  = manual_quantities.get(ore, 0.0)
        price    = prices.get(ore, 0)
        ore_rows.append({
            "Ore":              ore,
            "Optimal (MT)":     opt_qty,
            "Manual (MT)":      man_qty,
            "Δ MT":             man_qty - opt_qty,
            "Price (₹/MT)":     price,
            "Optimal Cost (₹)": opt_qty * price,
            "Manual Cost (₹)":  man_qty * price,
            "Cost Δ (₹)":       (man_qty - opt_qty) * price,
        })

    ore_df = pd.DataFrame(ore_rows)

    # Totals row
    totals = pd.DataFrame([{
        "Ore":              "TOTAL",
        "Optimal (MT)":     ore_df["Optimal (MT)"].sum(),
        "Manual (MT)":      ore_df["Manual (MT)"].sum(),
        "Δ MT":             ore_df["Δ MT"].sum(),
        "Price (₹/MT)":     None,
        "Optimal Cost (₹)": ore_df["Optimal Cost (₹)"].sum(),
        "Manual Cost (₹)":  ore_df["Manual Cost (₹)"].sum(),
        "Cost Δ (₹)":       ore_df["Cost Δ (₹)"].sum(),
    }])
    ore_df["Price (₹/MT)"] = ore_df["Price (₹/MT)"].astype(float)
    ore_df = pd.concat([ore_df, totals], ignore_index=True)

    def highlight_cost_delta(col):
        styles = []
        for v in col:
            if isinstance(v, (int, float)):
                if v > 0:   styles.append("color: #ff4b4b")
                elif v < 0: styles.append("color: #21c55d")
                else:       styles.append("")
            else:
                styles.append("font-weight: bold")
        return styles

    st.dataframe(
        ore_df.style
            .format({
                "Optimal (MT)":     "{:.0f}",
                "Manual (MT)":      "{:.0f}",
                "Δ MT":             "{:+.0f}",
                "Optimal Cost (₹)": "₹{:,.0f}",
                "Manual Cost (₹)":  "₹{:,.0f}",
                "Cost Δ (₹)":       "₹{:+,.0f}",
            }, na_rep="")
            .apply(highlight_cost_delta, subset=["Cost Δ (₹)"])
            .apply(highlight_cost_delta, subset=["Δ MT"]),
        use_container_width=True,
        hide_index=True,
    )