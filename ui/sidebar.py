"""
UI Sidebar — Ore selection, quantity inputs, price inputs.
"""

import streamlit as st
import pandas as pd
from data.ore_chemistry import get_ore_flag
from config.config import cfg


def render_sidebar(chemistry_df: pd.DataFrame) -> dict | None:
    st.sidebar.title("Blend Configuration")

    all_ores = chemistry_df.index.tolist()

    # ── Step 1: Select Ores ───────────────────────────────────────────────────
    st.sidebar.subheader("Step 1 — Select Ores")
    st.sidebar.caption("Choose ores available in the yard today")

    selected_ores = []
    for ore in all_ores:
        flag  = get_ore_flag(ore)
        label = f"{ore}  {flag}" if flag else ore
        if st.sidebar.checkbox(label, value=False, key=f"ore_check_{ore}"):
            selected_ores.append(ore)

    if len(selected_ores) < 2:
        st.sidebar.warning("Select at least 2 ores to begin.")
        return None

    st.sidebar.divider()

    # ── Step 2: Target Blend Quantity ─────────────────────────────────────────
    st.sidebar.subheader("Step 2 — Target Blend")
    target_qty = st.sidebar.number_input(
        "Total Target Blend (MT)",
        min_value=10.0,
        max_value=50000.0,
        value=cfg.default_target_qty,
        step=50.0,
        help="Total tonnes of ore blend required",
    )

    st.sidebar.divider()

    # ── Step 3: Available Quantities ──────────────────────────────────────────
    st.sidebar.subheader("Step 3 — Available Quantities (MT)")
    st.sidebar.caption("Enter max available tonnes per ore")

    max_quantities  = {}
    total_available = 0.0
    for ore in selected_ores:
        qty = st.sidebar.number_input(
            ore,
            min_value=1.0,
            max_value=99999.0,
            value=float(target_qty),
            step=10.0,
            key=f"qty_{ore}",
        )
        max_quantities[ore] = qty
        total_available += qty

    if total_available < target_qty:
        st.sidebar.error(
            f"Total available ({total_available:.0f} MT) is less than "
            f"target ({target_qty:.0f} MT). Add more ore or reduce target."
        )
        return None

    st.sidebar.divider()

    # ── Step 4: Prices ────────────────────────────────────────────────────────
    st.sidebar.subheader("Step 4 — Price per MT (₹)")
    st.sidebar.caption("Enter current purchase price per tonne")

    prices = {}
    for ore in selected_ores:
        price = st.sidebar.number_input(
            ore,
            min_value=0.0,
            max_value=99999.0,
            value=cfg.ore_prices.get(ore, cfg.fallback_price),
            step=100.0,
            key=f"price_{ore}",
        )
        prices[ore] = price

    st.sidebar.divider()

    # ── Step 5: Grid Search Step Size ─────────────────────────────────────────
    st.sidebar.subheader("Step 5 — Grid Search Step Size")
    step_size = st.sidebar.select_slider(
        "Step Size (MT)",
        options=[5, 10, 25, 50, 100],
        value=10,
        help="Smaller steps = more candidate blends = slightly slower",
    )

    st.sidebar.divider()

    # ── Run Button ────────────────────────────────────────────────────────────
    run = st.sidebar.button(
        "Run Optimizer",
        type="primary",
        use_container_width=True,
    )

    if not run:
        return None

    return {
        "selected_ores":  selected_ores,
        "max_quantities": max_quantities,
        "prices":         prices,
        "target_qty":     target_qty,
        "step_size":      float(step_size),
    }