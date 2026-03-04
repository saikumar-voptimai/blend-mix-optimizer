"""
Ore Blend Mix Optimization System
BF-02 Blast Furnace — Bunker Ore Blend Optimizer

Main Streamlit application entry point.
"""

import streamlit as st
import pandas as pd

# ── Page config (must be first Streamlit call) ─────────────────────────────────
st.set_page_config(
    page_title="Ore Blend Optimizer — BF-02",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Barlow', sans-serif;
    }
    .main { background-color: #0D1117; color: #C9D1D9; }
    .stApp { background-color: #0D1117; }
    
    [data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #21262D;
    }
    [data-testid="stSidebar"] * { color: #C9D1D9 !important; }
    
    .stMetric {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 8px;
        padding: 1rem;
    }
    .stMetric label { color: #8B949E !important; font-family: 'Share Tech Mono', monospace !important; font-size: 0.75rem !important; }
    .stMetric [data-testid="stMetricValue"] { 
        color: #E8A020 !important; 
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 1.4rem !important;
    }
    .stMetric [data-testid="stMetricDelta"] { color: #8B949E !important; font-size: 0.75rem !important; }

    .stButton > button {
        background: linear-gradient(135deg, #E8A020, #c17d10) !important;
        color: #0D1117 !important;
        font-family: 'Share Tech Mono', monospace !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 6px !important;
        letter-spacing: 1px;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #f5b53a, #E8A020) !important;
        transform: translateY(-1px);
    }

    .stDataFrame { border: 1px solid #21262D; border-radius: 8px; }
    
    h1, h2, h3, h4 { 
        font-family: 'Share Tech Mono', monospace !important;
        color: #C9D1D9 !important;
    }
    h1 { color: #E8A020 !important; letter-spacing: 2px; }

    .stTabs [data-baseweb="tab"] {
        font-family: 'Share Tech Mono', monospace;
        color: #8B949E;
    }
    .stTabs [aria-selected="true"] {
        color: #E8A020 !important;
        border-bottom: 2px solid #E8A020 !important;
    }

    .stAlert { border-radius: 8px; }
    
    div[data-testid="stExpander"] {
        background: #161B22;
        border: 1px solid #21262D;
        border-radius: 8px;
    }

    hr { border-color: #21262D !important; }
</style>
""", unsafe_allow_html=True)

# ── Imports (after page config) ────────────────────────────────────────────────
from data.ore_chemistry import load_ore_chemistry
from engine.optimizer import run_optimizer
from engine.overflow_resolver import resolve_overflow
from engine.grid_search import run_grid_search, estimate_combination_count
from ui.sidebar import render_sidebar
from ui.results import render_best_blend_card, render_top_blends_table
from ui.charts import (
    render_pareto_scatter,
    render_composition_bar,
    render_radar_chart,
    render_fe_contribution_waterfall,
)


# ── Load chemistry data (cached) ───────────────────────────────────────────────
@st.cache_data
def load_data():
    return load_ore_chemistry()


# ── Header ─────────────────────────────────────────────────────────────────────
def render_header():
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        <h1 style='margin-bottom: 0;'>⚙ ORE BLEND OPTIMIZER</h1>
        <p style='color: #8B949E; font-family: monospace; margin-top: 0.2rem; font-size: 0.85rem;'>
            BF-02 BUNKER — BLAST FURNACE BLEND OPTIMIZATION SYSTEM
        </p>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div style='text-align: right; padding-top: 0.5rem;'>
            <span style='font-family: monospace; font-size: 0.75rem; color: #8B949E;'>
                FY 2025–26 | AVERAGE CHEMISTRY
            </span>
        </div>
        """, unsafe_allow_html=True)
    st.divider()


# ── Ore Catalogue Tab ──────────────────────────────────────────────────────────
def render_catalogue_tab(chemistry_df: pd.DataFrame):
    st.markdown("#### 📋 Ore Chemistry Reference — BF-02 Bunker (2025-26 Averages)")

    display_cols = ["%Fe(T)", "%SiO2", "%Al2O3", "%CaO", "%MgO", "%TiO2", "%P", "%MnO", "%LOI", "Slag%"]
    display_cols = [c for c in display_cols if c in chemistry_df.columns]

    styled_df = chemistry_df[display_cols].copy()
    styled_df.index.name = "Ore / Material"

    def highlight_fe(val):
        if isinstance(val, float):
            if val >= 60:
                return "color: #81C784"
            elif val >= 50:
                return "color: #E8A020"
            else:
                return "color: #F06292"
        return ""

    st.dataframe(
        styled_df.style.format("{:.3f}"),
        use_container_width=True,
        height=480,
    )

    st.caption("Slag% = SiO2% + Al2O3% + CaO% + MgO%")

    # Special ore notes
    with st.expander("ℹ️ Special Ore Notes"):
        st.markdown("""
        - **Acore Industries** — Manganese ore (MnO ~22%). Very low Fe (~27%). Use only if Mn addition is intentional.
        - **Titani Ferrous CLO** — Titaniferous ore (TiO2 ~12%). High titanium loads the slag and can damage furnace lining at elevated concentrations.
        - **NMDC Donimalai** — Unusually high SiO2 (~14.4%). Will significantly increase slag burden if used in large quantities.
        - **Sinter (SP-02)** — Self-fluxing material with high CaO (~10.6%). This reduces the need for external limestone additions.
        """)


# ── Main App ───────────────────────────────────────────────────────────────────
def main():
    chemistry_df = load_data()

    render_header()

    # Sidebar inputs
    operator_inputs = render_sidebar(chemistry_df)

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Ore Catalogue",
        "★ Optimal Blend",
        "📊 Comparison Charts",
        "🎯 Blend Comparison",
    ])

    with tab1:
        render_catalogue_tab(chemistry_df)

    # If operator hasn't run yet, show instructions
    if operator_inputs is None:
        with tab2:
            st.markdown("""
            <div style='text-align: center; padding: 4rem 2rem; color: #8B949E;'>
                <h2 style='color: #8B949E; font-family: monospace;'>← Configure blend in sidebar</h2>
                <p>Select ores, enter quantities and prices, pick your goal, then click RUN OPTIMIZER</p>
            </div>
            """, unsafe_allow_html=True)
        with tab3:
            st.info("Run the optimizer first to see charts.")
        with tab4:
            st.info("Run the optimizer first to compare blends.")
        return

    # ── Extract inputs ─────────────────────────────────────────────────────────
    selected_ores  = operator_inputs["selected_ores"]
    max_quantities = operator_inputs["max_quantities"]
    prices         = operator_inputs["prices"]
    target_qty     = operator_inputs["target_qty"]
    goal           = operator_inputs["goal"]
    priority_list  = operator_inputs["priority_list"]
    step_size      = operator_inputs["step_size"]

    # ── Run LP Optimizer ───────────────────────────────────────────────────────
    with st.spinner("Running LP optimizer..."):
        optimal_result = run_optimizer(
            selected_ores=selected_ores,
            max_quantities=max_quantities,
            prices=prices,
            target_qty=target_qty,
            goal=goal,
            chemistry_df=chemistry_df,
        )

    if optimal_result is None:
        st.error(
            "❌ Optimizer could not find a feasible solution. "
            "Check that total available quantity ≥ target blend quantity."
        )
        return

    # ── Run Overflow Resolver ──────────────────────────────────────────────────
    resolved_result, overflow_warnings = resolve_overflow(
        recommended_quantities=optimal_result.quantities,
        max_quantities=max_quantities,
        priority_list=priority_list,
        prices=prices,
        target_qty=target_qty,
        chemistry_df=chemistry_df,
    )

    final_result = resolved_result if resolved_result else optimal_result

    # ── Run Grid Search ────────────────────────────────────────────────────────
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
            goal=goal,
            chemistry_df=chemistry_df,
        )

    # ── Tab 2: Optimal Blend ───────────────────────────────────────────────────
    with tab2:
        render_best_blend_card(final_result, goal, overflow_warnings)
        st.divider()
        render_top_blends_table(grid_df, goal)

    # ── Tab 3: Comparison Charts ───────────────────────────────────────────────
    with tab3:
        if not grid_df.empty:
            st.markdown("#### Pareto Front — All Valid Blends")
            render_pareto_scatter(grid_df, final_result)

            st.divider()
            st.markdown("#### Fe% Contribution per Ore")
            render_fe_contribution_waterfall(final_result, chemistry_df)

            st.divider()
            st.markdown("#### Blend Composition — Top 10 Blends")
            render_composition_bar(grid_df, selected_ores, top_n=10)
        else:
            st.info("No grid search results. Try a smaller step size.")

    # ── Tab 4: Blend Comparison (Radar) ───────────────────────────────────────
    with tab4:
        if not grid_df.empty:
            st.markdown("#### Select Blends to Compare")
            max_rank = min(20, len(grid_df))
            selected_ranks = st.multiselect(
                "Select ranks from Top 20 to compare (2–5 blends)",
                options=list(range(1, max_rank + 1)),
                default=[1, 2, 3] if max_rank >= 3 else list(range(1, max_rank + 1)),
                max_selections=5,
            )

            if len(selected_ranks) >= 1:
                render_radar_chart(grid_df, selected_ranks, final_result)

                # Side-by-side chemistry table
                st.divider()
                st.markdown("#### Side-by-Side Chemistry Comparison")

                compare_rows = []
                # Add optimal
                compare_rows.append({
                    "Blend": "★ Optimal",
                    "Fe%": final_result.fe_pct,
                    "SiO2%": final_result.sio2_pct,
                    "Al2O3%": final_result.al2o3_pct,
                    "CaO%": final_result.cao_pct,
                    "MgO%": final_result.mgo_pct,
                    "TiO2%": final_result.tio2_pct,
                    "Slag%": final_result.slag_pct,
                    "Slag MT": final_result.slag_mt,
                    "Cost/MT (₹)": final_result.cost_per_mt,
                })
                for rank in selected_ranks:
                    if 1 <= rank <= len(grid_df):
                        row = grid_df.iloc[rank - 1]
                        compare_rows.append({
                            "Blend": f"Rank {rank}",
                            "Fe%": row["Fe%"],
                            "SiO2%": row["SiO2%"],
                            "Al2O3%": row["Al2O3%"],
                            "CaO%": row["CaO%"],
                            "MgO%": row["MgO%"],
                            "TiO2%": row["TiO2%"],
                            "Slag%": row["Slag%"],
                            "Slag MT": row["Slag (MT)"],
                            "Cost/MT (₹)": row["Cost/MT (₹)"],
                        })

                compare_df = pd.DataFrame(compare_rows).set_index("Blend")
                st.dataframe(
                    compare_df.style.format("{:.3f}"),
                    use_container_width=True,
                )
            else:
                st.info("Select at least 1 rank to view comparison.")
        else:
            st.info("No grid search results available for comparison.")


if __name__ == "__main__":
    main()