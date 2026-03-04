"""
UI Sidebar — Ore selection, quantity inputs, price inputs, goal selection.
Returns all operator inputs as structured dicts.
"""

import streamlit as st
import pandas as pd
from data.ore_chemistry import get_ore_flag, SLAG_COMPONENTS


def render_sidebar(chemistry_df: pd.DataFrame) -> dict | None:
    """
    Render the full sidebar UI.
    Returns dict of operator inputs, or None if not ready to run.
    """
    st.sidebar.markdown("""
    <div style='padding: 0.5rem 0 1rem 0;'>
        <h2 style='font-family: monospace; font-size: 1.1rem; 
                   color: #E8A020; margin: 0; letter-spacing: 2px;'>
            ⚙️ BLEND CONFIGURATION
        </h2>
    </div>
    """, unsafe_allow_html=True)

    all_ores = chemistry_df.index.tolist()

    # ── Step 1: Select Ores ───────────────────────────────────────────────────
    st.sidebar.markdown("### Step 1 — Select Ores")
    st.sidebar.caption("Choose ores available in the yard today")

    selected_ores = []
    for ore in all_ores:
        flag = get_ore_flag(ore)
        label = f"{ore}  {flag}" if flag else ore
        if st.sidebar.checkbox(label, value=False, key=f"ore_check_{ore}"):
            selected_ores.append(ore)

    if len(selected_ores) < 2:
        st.sidebar.warning("Select at least 2 ores to begin.")
        return None

    st.sidebar.divider()

    # ── Step 2: Target Blend Quantity ─────────────────────────────────────────
    st.sidebar.markdown("### Step 2 — Target Blend")
    target_qty = st.sidebar.number_input(
        "Total Target Blend (MT)",
        min_value=10.0,
        max_value=50000.0,
        value=1000.0,
        step=50.0,
        help="Total tonnes of ore blend required"
    )

    st.sidebar.divider()

    # ── Step 3: Available Quantities ──────────────────────────────────────────
    st.sidebar.markdown("### Step 3 — Available Quantities (MT)")
    st.sidebar.caption("Enter max available tonnes per ore")

    max_quantities = {}
    total_available = 0
    for ore in selected_ores:
        qty = st.sidebar.number_input(
            f"{ore}",
            min_value=1.0,
            max_value=99999.0,
            value=float(max(100, int(target_qty / len(selected_ores)))),
            step=10.0,
            key=f"qty_{ore}",
        )
        max_quantities[ore] = qty
        total_available += qty

    # Availability check
    if total_available < target_qty:
        st.sidebar.error(
            f"⚠️ Total available ({total_available:.0f} MT) < "
            f"Target ({target_qty:.0f} MT). Add more ore or reduce target."
        )
        return None

    st.sidebar.divider()

    # ── Step 4: Prices ────────────────────────────────────────────────────────
    st.sidebar.markdown("### Step 4 — Price per MT (₹)")
    st.sidebar.caption("Enter current purchase price per tonne")

    prices = {}
    for ore in selected_ores:
        price = st.sidebar.number_input(
            f"{ore}",
            min_value=0.0,
            max_value=99999.0,
            value=5000.0,
            step=100.0,
            key=f"price_{ore}",
        )
        prices[ore] = price

    st.sidebar.divider()

    # ── Step 5: Optimization Goal ─────────────────────────────────────────────
    st.sidebar.markdown("### Step 5 — Optimization Goal")
    goal = st.sidebar.radio(
        "What matters most today?",
        options=["Minimize Cost", "Maximize Fe%", "Minimize Slag%"],
        index=0,
        help="The optimizer will find the blend that best achieves this goal"
    )

    st.sidebar.divider()

    # ── Step 6: Vendor Priority (for overflow resolver) ───────────────────────
    st.sidebar.markdown("### Step 6 — Vendor Priority")
    st.sidebar.caption("Priority order for overflow redistribution (1 = highest)")

    priority_list = []
    for i, ore in enumerate(selected_ores):
        priority = st.sidebar.number_input(
            f"{ore}",
            min_value=1,
            max_value=len(selected_ores),
            value=i + 1,
            step=1,
            key=f"priority_{ore}",
        )
        priority_list.append((priority, ore))

    priority_list.sort(key=lambda x: x[0])
    ordered_priority = [ore for _, ore in priority_list]

    st.sidebar.divider()

    # ── Step 7: Grid Search Settings ─────────────────────────────────────────
    st.sidebar.markdown("### Step 7 — Grid Search Settings")
    step_size = st.sidebar.select_slider(
        "Step Size (MT)",
        options=[25, 50, 100, 200, 500],
        value=100,
        help="Smaller steps = more combinations = slower"
    )

    st.sidebar.divider()

    # ── Run Button ────────────────────────────────────────────────────────────
    run = st.sidebar.button(
        "🚀 RUN OPTIMIZER",
        type="primary",
        use_container_width=True,
    )

    if not run:
        return None

    return {
        "selected_ores":   selected_ores,
        "max_quantities":  max_quantities,
        "prices":          prices,
        "target_qty":      target_qty,
        "goal":            goal,
        "priority_list":   ordered_priority,
        "step_size":       float(step_size),
    }