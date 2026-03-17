# Blend-Mix-Optimizer-2

**Ore Blend Mix Optimization System for BF-02 Blast Furnace**

A comprehensive Streamlit-based application that helps metallurgical and process engineers design optimal ore blends meeting strict chemistry constraints while minimizing cost. The system leverages linear programming (via SciPy) to optimize blend composition, includes intelligent overflow resolution, and provides interactive visualization of alternative solutions.

---

## Key Features ✅

- **Interactive Ore Catalogue** – Browse FY 2025-26 average chemistry profiles for all available bunker ores and materials with detailed oxide compositions and slag estimates.

- **Advanced LP-Based Optimizer** – Minimizes blend cost subject to:
  * Fixed total blend quantity constraint
  * Maximum slag burden (MT) limit
  * Minimum effective Fe production (MT) with FeO-to-Fe conversion factor
  * Sinter fraction bounds (configurable min/max % when sinter ores detected)
  * Per-ore maximum percentage caps (configurable by ore or global fallback)
  * Operator-specified availability limits for each ore
  * **Graceful fallback**: If Fe constraint is infeasible, automatically retries with relaxed constraint only

- **Intelligent Overflow Resolver** – When LP solution recommends quantities exceeding availability:
  * Automatically caps the overflowing ore at max available
  * Redistributes deficit proportionally to remaining ores
  * Issues clear warnings about which ores were capped and by how much

- **Advanced Grid Search & Pareto Front** – Explore alternatives by sampling nearby blends within configurable step size:
  * Builds Pareto front of cost vs. chemistry/slag across all valid combinations
  * Pre-calculates combination count estimate to avoid excessive search spaces
  * Ranks solutions by user-selected objective (cost, slag, Fe content)
  * Compare top N candidates side-by-side with full chemistry details

- **Fuel Slag Calculator** – Estimates slag contribution from coke, nut coke, and PCI inputs:
  * Uses ash percentages and detailed oxide analyses (SiO2, Al2O3, CaO, MgO, Fe2O3, P2O5) from config
  * Integrates seamlessly with blend results
  * Configurable defaults for sidebar fuel input widgets

- **Rich Interactive Dashboard** –
  * Pareto scatter plot with cost vs. slag/Fe highlighting
  * Fe contribution waterfall chart by ore
  * Composition bar charts for top candidate blends
  * Radar chart comparison of selected solutions
  * Detailed tables: quantities, unit costs, total costs, and full chemistry profiles
  * Real-time KPI cards (kg/MT values) for selected blends

- **Manual Blend Comparison Tool** – Allows operators to input their own ore mix and instantly compare against the optimizer’s recommendation. Displays cost deltas, gross/net Fe%, slag, full chemistry and an ore-by-ore cost breakdown (fuel-adjusted). Guidelines and results are preserved in session state for easy re-use.

---

## Project Structure 📁

`	ext
app.py                 # Main Streamlit entry point; orchestrates tabs and data flow

config/
  __init__.py          # Package initialization
  config.py            # Typed Config dataclass; YAML loader; exposes 'cfg' singleton
  config.yaml          # All parameters: prices, chemistry, constraints, fuel ash data

data/
  ore_chemistry.py     # Load and preprocess ore chemistry from Excel source

engine/
  optimizer.py         # Core LP solver; uses scipy.optimize.linprog
  blend_calculator.py  # Computes blend stats (chemistry, slag, Fe, cost); BlendResult dataclass
  overflow_resolver.py # Caps overflowing ores; redistributes deficit
  grid_search.py       # Grid search around optimum; estimates combo count
  fuel_calculator.py   # Fuel ash/slag computation from coke/PCI inputs

ui/
  sidebar.py           # Streamlit sidebar widgets for user inputs & selections
  results.py           # Render best-blend card, tables, and operator warnings
  charts.py            # Plotly figures: Pareto, waterfall, composition, radar
  manual_blend.py      # UI tab for manual blend entry and comparison with optimal result

assets/
  BF02_Ores_Chemical_Composition.xlsx  # Source ore chemistry data (FY 2025-26 averages)
`

---

## Configuration 🔧

All operational parameters live in `config/config.yaml`. Key sections:

### Blend Parameters
- `default_target_qty` – Default blend size (MT)
- `target_slag_qty` – Maximum slag burden allowed (MT)
- `min_fe_production_mt` – Minimum usable Fe in blend (MT)

### Ore Constraints
- `ore_prices` – Dict of ore names to \$/MT cost; uses `fallback_price` for unknowns
- `ore_max_pct` – Dict of ore names to max % of blend; uses `fallback_max_pct` for unknowns
- `sinter_min_pct` / `sinter_max_pct` – Hard bounds on ores containing "sinter" in name

### Fuel Ash Data
- `coke_ash_analysis`, `nut_coke_ash_analysis`, `pci_ash_analysis` – Oxide compositions (SiO2, Al2O3, CaO, MgO, Fe2O3, P2O5)
- `feo_in_slag`, `si_in_slag` – Slag composition factors for fuel contribution

### Sidebar Defaults
- `coke_defaults`, `nut_coke_defaults`, `pci_defaults` – Initial quantities and ash % for fuel inputs

**To apply changes:** Modify values in `config.yaml` and restart the Streamlit app.

---

## How It Works ⚙

### 1. **Load & Select**
   - Load ore chemistry from Excel source via `data/ore_chemistry.py`
   - Select available ores from the catalogue in the sidebar
   - Specify quantities (MT) available for each ore

### 2. **Optimize**
   - Click "Run Optimizer" to solve the LP problem:
     * **Objective**: Minimize total cost = Σ(quantity × price)
     * **Constraints**:
       - Total blend = target quantity
       - Total slag ≤ slag limit (MT)
       - Total effective Fe ≥ Fe minimum (MT)
       - Sinter ores bounded by configured min/max %
       - Per-ore quantity ≤ availability & % cap
   - If **Fe constraint fails**: Solver retries with slack (slag-only constraint)
   - Result: Quantities for each ore that form the optimal blend

### 3. **Resolve Overflows** (if needed)
   - If any ore quantity exceeds availability, `overflow_resolver.py` caps it
   - Deficit redistributed proportionally to other ores
   - Warnings issued for capped ores

### 4. **Manual Blend Comparison** (Optional)
   - Switch to the "Manual Blend" tab after running the optimizer
   - Enter ore quantities of your choice and click **"Compare Blends"**
   - Review cost/MT delta, total cost impact, gross/net Fe%, slag, and full chemistry
   - Examine ore-level cost breakdowns (with fuel slag added) to understand where differences arise
   - Results are cached in `st.session_state` so the optimizer or grid search aren’t re‑run each time

### 5. **Grid Search** (Optional)
   - Sample blends within ± step size of each ore's optimum quantity
   - Keeps only chemically feasible blends (slag ≤ limit, Fe ≥ minimum)
   - Ranks by cost, slag, or Fe—user selectable
   - Builds Pareto front for comparison

### 6. **Visualize & Compare**
   - View best blend card with KPIs
   - Inspect Pareto scatter, composition bars, Fe waterfall, radar comparison
   - Download or compare ranked candidates

---

## Requirements & Setup 🛠

### Prerequisites
- **Python** ≥ 3.11
- **Dependencies** (in `pyproject.toml` / `requirements.txt`):
  - `streamlit` ≥ 1.55.0
  - `pandas` ≥ 2.3.3
  - `numpy` ≥ 2.4.2
  - `scipy` ≥ 1.17.1 (LP solver)
  - `plotly` ≥ 6.6.0 (interactive charts)
  - `openpyxl` ≥ 3.1.5 (Excel chemistry file)
  - `pyyaml` ≥ 6.0.3 (config parsing)

### Installation

**Option 1: Virtual environment + `uv`**
\\\ash
python -m venv .venv
.venv\Scripts\activate    # Windows PowerShell
# or: .venv\Scripts\Activate.ps1 (if running scripts is allowed)
# install packages using the `uv` package manager (preferred)
uv install
# or, if you still need to use pip:
# pip install -r requirements.txt
\\\

**Option 2: Poetry**
\\\ash
poetry install
poetry run streamlit run app.py
\\\

**Option 3: Conda**
\\\ash
conda env create -f environment.yml
conda activate blend-optimizer
streamlit run app.py
\\\

---

## Running the Application 🚀

\\\ash
streamlit run app.py
\\\

The app will open at `http://localhost:8501` in your default browser.

### Typical Workflow

1. **Catalogue Tab** – Review ore chemistry profiles and understand available materials.

2. **Optimization Tab** (default):
   - Load the ore catalogue (cached after first load)
   - Select ores for your blend from checkboxes
   - Set available quantities (MT), prices (\$/MT), target blend size
   - Specify fuel inputs (coke, nut coke, PCI) quantities and ash percentages
   - Adjust slag and Fe constraints if needed
   - Click **"Run Optimizer"** → view the best-cost blend
   - Inspect warnings, KPIs, and composition details

3. **Manual Blend Tab** –
   - Enter your own ore quantities and click **"Compare Blends"**
   - See cost and chemistry deltas versus the optimizer result
   - Useful for validating operator intuition or trial mixes

4. **Grid Search Tab**:
   - Choose step size (how far to search from optimum)
   - Click **"Run Grid Search"** → builds Pareto front
   - Select ranking objective (cost, slag, Fe)
   - View top N alternative blends; compare using radar/bar charts

5. **Extra Tools**:
   - **Fuel Slag Calculator** – Standalone tool to estimate slag from fuel inputs only
   - **Combination Estimator** – Preview how many blends will be sampled before grid search

---

## Module Reference

### `config/config.py`
Loads `config.yaml` into a `Config` dataclass. Exposes `cfg` object globally.

**Key Properties:**
- `cfg.default_target_qty` – Target blend quantity (MT)
- `cfg.ore_prices` – Dict of ore → price (\$/MT)
- `cfg.ore_max_pct` – Dict of ore → max % of blend
- `cfg.target_slag_qty`, `cfg.min_fe_production_mt` – Constraints
- `cfg.sinter_min_pct`, `cfg.sinter_max_pct` – Sinter bounds
- Fuel ash analyses & defaults

### `engine/optimizer.py`
**Function:** `run_optimizer(selected_ores, max_quantities, prices, target_qty, chemistry_df) -> BlendResult | None`

Solves LP to minimize cost with full constraint set. Auto-retries with relaxed Fe constraint if infeasible.

**Returns:** `BlendResult` object with:
- `quantities` – Dict[ore_name → MT]
- `total_cost` – Total blend cost (\$)
- `chemistry_details` – Full oxide composition
- `fe_constraint_relaxed` – True if Fe constraint was relaxed
- `is_feasible` – True if solution is valid

### `engine/blend_calculator.py`
**Function:** `calculate_blend(quantities, prices, chemistry_df) -> BlendResult`

Computes blend chemistry, KPIs (slag %, Fe %, cost), and formats for rendering.

### `engine/overflow_resolver.py`
**Function:** `resolve_overflow(quantities, max_quantities) -> tuple[Dict, List[str]]`

Caps overflowing ores; redistributes deficit. Returns updated quantities & warning messages.

### `engine/grid_search.py`
**Functions:**
- `run_grid_search(...)` – Samples blends around optimum within step size
- `estimate_combination_count(...)` – Pre-calculates expected search space size

### `engine/fuel_calculator.py`
**Function:** `calculate_fuel_slag(coke_mt, nut_coke_mt, pci_mt, coke_ash_pct, ...) -> dict`

Computes slag from fuel inputs using ash % and oxide analyses.

### `ui/sidebar.py`
Renders all user input widgets: ore selection, quantities, prices, fuel inputs, constraint sliders.

### `ui/results.py`
Renders best-blend KPI card, detailed tables, and operator warnings.

### `ui/charts.py`
Plotly figure generators: Pareto scatter, Fe waterfall, composition bars, radar comparison.

### `ui/manual_blend.py`
Handles the Manual Blend tab. Accepts user-specified ore quantities, computes a blend via `engine.blend_calculator.calculate_blend`, compares against the optimizer's `BlendResult`, and renders side-by-side metrics & cost breakdown with visual cues.
### `data/ore_chemistry.py`
**Function:** `load_ore_chemistry() -> pd.DataFrame`

Reads `assets/BF02_Ores_Chemical_Composition.xlsx`, normalizes column names, caches result.

---

## Customization & Extension 💡

### Add a New Ore
1. Add row to `BF02_Ores_Chemical_Composition.xlsx`
2. Add price to `ore_prices` in `config.yaml`
3. (Optional) Set max % cap in `ore_max_pct`
4. Restart app; new ore appears in sidebar checklist

### Change Constraints
1. Edit `config.yaml` (e.g., `target_slag_qty`, `min_fe_production_mt`, sinter bounds)
2. Restart app
3. New constraints take effect on next optimization

### Add a New KPI
1. Compute metric in `engine/blend_calculator.py` within `calculate_blend()`
2. Add field to `BlendResult` dataclass
3. Display in `ui/results.py` (best-blend card or table)

### Support Multi-Furnace
1. Extend `config.py` to load multiple `.yaml` files or add a selector widget
2. Pass selected config to optimizer & calculator functions
3. Load furnace-specific Excel file in `data/ore_chemistry.py`

---

## Troubleshooting 🔧

### "Optimizer returned None — infeasible problem"
- **Cause**: Selected ore mix cannot satisfy all constraints simultaneously
- **Fix**: 
  * Relax `target_slag_qty` or `min_fe_production_mt` in sidebar or config
  * Add more diverse ores to increase feasibility space
  * Lower per-ore % caps in `config.yaml`

### "Grid search takes too long"
- **Cause**: Step size is too small or too many ores selected
- **Fix**: 
  * Increase step size (e.g., 5 MT → 10 MT)
  * Pre-check combo estimate using "Combination Estimator" tool
  * Reduce number of selected ores

### "Ore chemistry appears stale"
- **Cause**: Streamlit caching from previous run
- **Fix**: Restart the app or use Streamlit's "Rerun" button

### "Config changes not taking effect"
- **Cause**: Changes made but app not restarted
- **Fix**: Save `config.yaml` and restart Streamlit (\Ctrl+C\ in terminal, then \streamlit run app.py\)

---

## Performance Notes 📊

- **Optimizer**: ~50 ms for 10 ores (LP is fast)
- **Grid search**: ~1 s per 1000 combination samples (depends on ore count and step size)
- **Visualization**: Plotly rendering ~100 ms
- **Caching**: Ore chemistry and config cached on first load; clear with app restart

---

## License & Attribution 📄

See [LICENSE](LICENSE) file for terms.

---

## Contributing & Feedback 🤝

Found a bug? Have a feature request? Please open an issue or reach out to the development team.

---

**Happy optimizing!** ⛏️
