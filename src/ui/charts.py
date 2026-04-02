"""
UI Charts — All Plotly visualizations for the blend optimizer.

Charts:
  1. Pareto scatter: Cost/MT vs Fe% (colour = Slag%)
  2. Stacked bar: Ore composition of top N blends
  3. Radar chart: Multi-dimension comparison of selected blends
  4. Chemistry waterfall: Per-ore contribution to blend Fe%
"""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from engine.blend_calculator import BlendResult

# ── Colour palette ─────────────────────────────────────────────────────────────
PALETTE = [
    "#E8A020", "#4FC3F7", "#81C784", "#F06292", "#CE93D8",
    "#80DEEA", "#FFCC02", "#FF8A65", "#A5D6A7", "#90CAF9",
    "#FFAB91", "#B39DDB"
]

BG_COLOR   = "#0D1117"
GRID_COLOR = "#21262D"
TEXT_COLOR = "#C9D1D9"
ACCENT     = "#E8A020"


def _base_layout(title: str) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=ACCENT, family="monospace", size=14)),
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        font=dict(color=TEXT_COLOR, family="monospace"),
        xaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        margin=dict(l=40, r=20, t=50, b=40),
    )


def render_pareto_scatter(grid_df: pd.DataFrame, optimal: BlendResult):
    """
    Scatter plot: Cost/MT (x) vs Fe% (y), coloured by Slag%.
    Optimal blend highlighted with a star marker.
    """
    if grid_df.empty:
        st.info("No grid search results to plot.")
        return

    fig = go.Figure()

    # All comparison blends
    fig.add_trace(go.Scatter(
        x=grid_df["Cost/THM (₹)"],
        y=grid_df["Fe%"],
        mode="markers",
        marker=dict(
            color=grid_df["Slag%"],
            colorscale="RdYlGn_r",
            size=8,
            opacity=0.7,
            colorbar=dict(
                title=dict(text="Slag%", font=dict(color=TEXT_COLOR)),
                tickfont=dict(color=TEXT_COLOR),
            ),
            line=dict(width=0.5, color=GRID_COLOR),
        ),
        text=[
            f"Rank {i+1}<br>Fe: {row['Fe%']:.2f}%<br>"
            f"Slag: {row['Slag%']:.2f}%<br>Cost: ₹{row['Cost/THM (₹)']:,.0f}/THM"
            for i, row in grid_df.iterrows()
        ],
        hovertemplate="%{text}<extra></extra>",
        name="Blend Combinations",
    ))

    # Optimal blend star
    fig.add_trace(go.Scatter(
        x=[optimal.cost_per_thm],
        y=[optimal.effective_fe_pct],
        mode="markers+text",
        marker=dict(
            symbol="star",
            size=20,
            color=ACCENT,
            line=dict(width=1, color="white"),
        ),
        text=["★ OPTIMAL"],
        textposition="top center",
        textfont=dict(color=ACCENT, size=11),
        hovertemplate=(
            f"<b>OPTIMAL BLEND</b><br>"
            f"Fe: {optimal.effective_fe_pct:.2f}%<br>"
            f"Slag: {optimal.slag_pct:.2f}%<br>"
            f"Cost: ₹{optimal.cost_per_thm:,.0f}/THM<extra></extra>"
        ),
        name="Optimal Blend",
    ))

    layout = _base_layout("PARETO FRONT — Cost vs Fe% (colour = Slag%)")
    layout.update(
        xaxis_title="Cost per THM (₹)",
        yaxis_title="Fe% of Blend",
        legend=dict(bgcolor=BG_COLOR, bordercolor=GRID_COLOR),
        height=450,
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch")


def render_composition_bar(grid_df: pd.DataFrame, selected_ores: list[str], top_n: int = 10):
    """
    Stacked horizontal bar chart showing ore composition of top N blends.
    """
    if grid_df.empty:
        return

    qty_cols = [f"qty_{ore}" for ore in selected_ores if f"qty_{ore}" in grid_df.columns]
    if not qty_cols:
        return

    top_df = grid_df.head(top_n).copy()
    top_df["label"] = [f"Rank {i+1}" for i in range(len(top_df))]

    fig = go.Figure()

    for i, ore in enumerate(selected_ores):
        col = f"qty_{ore}"
        if col not in top_df.columns:
            continue
        fig.add_trace(go.Bar(
            name=ore,
            y=top_df["label"],
            x=top_df[col],
            orientation="h",
            marker_color=PALETTE[i % len(PALETTE)],
            hovertemplate=f"<b>{ore}</b><br>%{{x:.0f}} MT<extra></extra>",
        ))

    layout = _base_layout(f"BLEND COMPOSITION — Top {top_n} Blends (MT per ore)")
    layout.update(
        barmode="stack",
        xaxis_title="Quantity (MT)",
        yaxis=dict(
            gridcolor=GRID_COLOR,
            autorange="reversed",
            tickfont=dict(size=10),
        ),
        legend=dict(bgcolor=BG_COLOR, bordercolor=GRID_COLOR, orientation="h",
                    yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=max(350, top_n * 35),
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch")

def render_fe_contribution_waterfall(optimal: BlendResult, chemistry_df):
    """
    Horizontal bar showing each ore's contribution to final Fe% of blend.
    Contribution_i = (qty_i / total_qty) × Fe_i
    """
    from engine.blend_calculator import FE_FROM_FEO_FACTOR
    from utils.config import cfg as _cfg
    ores     = list(optimal.quantities.keys())
    contribs = []
    for ore in ores:
        w     = optimal.quantities[ore] / optimal.total_qty
        fe_t  = float(chemistry_df.loc[ore, "%Fe(T)"])
        feo   = float(chemistry_df.loc[ore, "%FeO"]) if "%FeO" in chemistry_df.columns else 0.0
        fe_i  = fe_t + (feo - _cfg.feo_in_slag) * FE_FROM_FEO_FACTOR  # matches blend_calculator
        contribs.append(w * fe_i)

    fig = go.Figure(go.Bar(
        x=contribs,
        y=ores,
        orientation="h",
        marker=dict(
            color=contribs,
            colorscale=[[0, "#4a1942"], [0.5, "#E8A020"], [1, "#81C784"]],
        ),
        text=[f"{c:.2f}%" for c in contribs],
        textposition="outside",
        textfont=dict(color=TEXT_COLOR),
        hovertemplate="<b>%{y}</b><br>Fe contribution: %{x:.3f}%<extra></extra>",
    ))

    layout = _base_layout("Fe% CONTRIBUTION PER ORE TO FINAL BLEND")
    layout.update(
        xaxis_title="Fe% Contribution",
        yaxis=dict(gridcolor=GRID_COLOR, autorange="reversed"),
        height=max(300, len(ores) * 45),
        showlegend=False,
    )
    fig.update_layout(**layout)
    st.plotly_chart(fig, width="stretch")