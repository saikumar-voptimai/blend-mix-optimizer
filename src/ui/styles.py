"""
Global CSS styles for the BF-02 Ore Blend Optimizer.

Call apply_styles() once at the top of app.py to inject all styling.
"""

import streamlit as st

_CSS = """
/* ── Page background ───────────────────────────────── */
[data-testid="stAppViewContainer"] {
    background: #f0f4f9;
}
[data-testid="stHeader"] {
    background: transparent;
}

/* ── Step section headers ──────────────────────────── */
.step-header {
    background: linear-gradient(90deg, #1b3d6e 0%, #2a5fa5 100%);
    color: #ffffff;
    padding: 9px 16px;
    border-radius: 8px;
    margin: 4px 0 10px 0;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.4px;
}

/* ── Column header row (ore table) ────────────────── */
.col-header {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #6b7a8d;
    padding-bottom: 4px;
    border-bottom: 2px solid #d0dbe9;
    margin-bottom: 4px;
}

/* ── Ore name label ────────────────────────────────── */
.ore-label {
    padding-top: 6px;
    font-size: 13px;
    font-weight: 500;
    color: #1e3355;
}

/* ── Fuel table header ─────────────────────────────── */
.fuel-col-header {
    font-size: 12px;
    font-weight: 700;
    color: #2a5fa5;
    padding-bottom: 2px;
    border-bottom: 2px solid #b8d0ee;
    margin-bottom: 6px;
}

/* ── Run button wrapper ────────────────────────────── */
.run-wrapper {
    background: linear-gradient(135deg, #e6f0ff 0%, #edf7ee 100%);
    border: 1.5px solid #9dc8f0;
    border-radius: 10px;
    padding: 14px 20px 10px 20px;
    margin-top: 6px;
}

/* ── Summary chips ─────────────────────────────────── */
.summary-chip {
    display: inline-block;
    background: #dbeafe;
    color: #1d4ed8;
    border-radius: 20px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: 600;
    margin-right: 6px;
}

/* ── Fuel row label ────────────────────────────────── */
.fuel-row-label {
    padding-top: 7px;
    font-size: 13px;
    font-weight: 500;
    color: #444;
}

/* ── Result card banner ────────────────────────────── */
.result-banner {
    background: linear-gradient(135deg, #0a1e40 0%, #1a3a6e 60%, #1e5080 100%);
    padding: 16px 22px 14px 22px;
    border-radius: 10px;
    margin-bottom: 16px;
    box-shadow: 0 3px 12px rgba(10,30,64,0.25);
}

/* ── Section label inside result card ─────────────── */
.result-section-label {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #6b7a8d;
    margin-bottom: 6px;
    margin-top: 14px;
}

/* ── KPI divider band ──────────────────────────────── */
.kpi-band {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 14px 4px 14px;
    margin-bottom: 10px;
}

/* ── Warning/relaxed banner ────────────────────────── */
.constraint-warn {
    background: #fff8e1;
    border-left: 4px solid #f59e0b;
    border-radius: 6px;
    padding: 10px 14px;
    font-size: 13px;
    color: #78350f;
    margin-bottom: 12px;
}
"""

_PAGE_HEADER_HTML = """
<div style="
    background: linear-gradient(135deg, #0d2045 0%, #1a3a6e 55%, #1d5190 100%);
    padding: 22px 28px 18px 28px;
    border-radius: 12px;
    margin-bottom: 18px;
    box-shadow: 0 4px 16px rgba(13,32,69,0.25);
">
  <h1 style="color:#ffffff; margin:0; font-size:24px; font-weight:700; letter-spacing:-0.3px;">
    ⚙️ &nbsp;Ore Blend Optimizer — BF-02
  </h1>
  <p style="color:#9ec4e8; margin:5px 0 0 0; font-size:13px;">
    Blast Furnace Burden Optimization System &nbsp;·&nbsp; Evonith Steel
  </p>
</div>
"""

_INFO_BANNER_HTML = """
<div style="
    background:#e8f4fd;
    border-left: 4px solid #2a5fa5;
    border-radius: 6px;
    padding: 14px 18px;
    font-size: 14px;
    color: #1a3a6e;
">
    ℹ️ &nbsp; Configure inputs above and click <strong>🚀 Run Optimizer</strong> to start.
</div>
"""


def apply_styles() -> None:
    """Inject global CSS and render the page header banner."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
    st.markdown(_PAGE_HEADER_HTML, unsafe_allow_html=True)


def info_banner() -> None:
    """Render the 'run the optimizer' prompt banner."""
    st.markdown(_INFO_BANNER_HTML, unsafe_allow_html=True)
