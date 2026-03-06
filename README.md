# Blend-Mix-Optimizer-2

Ore blend mix optimization system for the BF‑02 blast furnace bunker. This Streamlit application helps process engineers design ore blends that meet chemistry constraints while controlling slag, iron content and cost. It also estimates fuel slag contribution based on coke, nut coke and PCI inputs.

---

## Key features ✅

- **Interactive ore catalogue** – Browse FY 2025‑26 average chemistry for all bunker ores and materials. Click an ore to view a detailed profile.
- **LP‑based optimal blend** – Linear programming optimizer finds a feasible, cost‑minimised blend subject to:
  * Target blend quantity and user‑specified availability limits
  * Maximum slag burden and minimum effective Fe content
  * Sinter fraction bounds (must be within configured min/max percent of the blend)
  * Per‑ore minimum percentage constraints driven by historical usage (configurable)
- **Overflow resolver** – If the LP solution exceeds an ore’s available quantity, the algorithm caps the offending ore and redistributes the deficit down a user‑defined priority list, issuing warnings along the way.
- **Grid search around optimum** – Automatically sample neighbouring blends within a search radius to build a Pareto front of cost vs. chemistry/slag. Results are ranked and can be compared side‑by‑side.
- **Fuel slag calculator** – Estimate slag contribution from coke, nut coke and PCI using ash percentages and lab‑reported oxide analyses from `config.yaml`.
- **Rich visualization dashboard** –
  * Pareto scatter plot of all valid blends
  * Fe contribution waterfall by ore
  * Composition bar charts for top blends
  * Radar chart comparison of selected candidate blends
  * Tables showing quantities, costs and chemistry for best and neighbouring blends

---

## Project structure 📁

```text
app.py                 # Main Streamlit entry point

config/
  config.py            # YAML loader; exposes `cfg` object used throughout
  config.yaml          # Default parameters, prices, chemistry and limits

data/
  ore_chemistry.py     # Load/pre‑process ore chemistry from Excel

engine/
  blend_calculator.py  # Calculate blend chemistry, KPIs and format results
  optimizer.py         # LP cost minimiser with slag/Fe/sinter constraints
  overflow_resolver.py # Capping & redistribution logic for availability overflows
  grid_search.py       # Brute‑force search around optimum and combination estimator
  fuel_calculator.py   # Compute fuel ash & slag from coke/PCI inputs

ui/
  sidebar.py           # Streamlit widgets for user inputs
  results.py           # Render best‑blend card, tables and warnings
  charts.py            # Plotly figures used in dashboard

assets/
  BF02_Ores_Chemical_Composition.xlsx  # Source ore chemistry data

```

---

## Configuration 🔧

All operational parameters and defaults live in `config/config.yaml`. Highlights:

- **Blend targets** – `default_target_qty`, `target_slag_qty`, `fe_min_pct`.
- **Ore prices** – Per‑MT costs with a `fallback_price` for unlisted ores.
- **Sinter limits** – `sinter_min_pct` / `sinter_max_pct` applied when any ore name contains “sinter”.
- **Ore minimums** – `ore_min_pct` map or global `fallback_min_pct`.
- **Fuel ash analyses** – Used by the fuel slag calculator.
- **Sidebar defaults** – Initial quantities and ash% for coke, nut coke and PCI inputs.

Modify values and restart the app to apply changes. The YAML structure is self‑documenting with comments.

---

## Requirements & setup 🛠️

- **Python** ≥ 3.11
- Dependencies listed in `pyproject.toml` / `requirements.txt`:
  `streamlit`, `pandas`, `numpy`, `scipy`, `plotly`, `openpyxl`.

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Or install via your preferred tool as long as the same packages are available.

---

## Running the application 🚀

```bash
streamlit run app.py
```

Use the sidebar to:

1. Load the ore catalogue and select materials for the blend.
2. Specify available quantities, prices, target blend size, step size and fuel inputs.
3. Choose optimisation goals and run the LP solver.
4. Inspect the optimal blend, warnings (overflow or infeasibility), and explore nearby alternatives.

Additional tabs allow catalogue browsing and comparing ranked blends.

---

## Extending and customizing 💡

- Swap out the Excel file or adapt `data/ore_chemistry.py` to support other furnaces or time periods.
- Add or modify business rules (e.g. new constraints, KPIs) in the `engine/` modules and update `ui/` components accordingly.
- Adjust default sidebar values or add new input fields by editing `ui/sidebar.py` and updating `config.yaml`.

---

Feel free to fork, experiment, and adapt for your blast‑furnace planning needs!