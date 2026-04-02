"""
Self-contained optimizer correctness test.

Uses a 3-ore dummy dataset with known chemistry so we can verify by hand
and by exhaustive grid search that the LP finds the true minimum-cost blend.

Run from the repo root:
    python test_optimizer.py

No Streamlit, no InfluxDB required.
"""

import sys
import itertools
import numpy as np
from scipy.optimize import linprog

# ── Constants (from blend_calculator.py) ─────────────────────────────────────
FE_FROM_FEO_FACTOR  = 55.845 / 71.844   # = 0.7773
SIO2_FROM_SI_FACTOR = 60 / 28           # = 2.1429

# ── Dummy problem definition ─────────────────────────────────────────────────
#
# Three ores with clear trade-offs:
#   A — cheapest, low Fe, high slag  → LP should max-use up to slag cap
#   B — medium,   good Fe, med slag  → supplement to meet Fe target
#   C — expensive, high Fe, low slag → only used if A+B can't meet Fe
#
# Notation matches optimizer.py:
#   effective_fe  = Fe(T) + (FeO - feo_in_slag) * 0.7773
#   effective_slag = SiO2 - si_in_slag*(60/28) + Al2O3 + CaO + MgO + MnO

ORES = ["ORE_A", "ORE_B", "ORE_C"]

CHEMISTRY = {
    # name       Fe(T)  FeO   SiO2  Al2O3  CaO   MgO   MnO
    "ORE_A": dict(fe_t=58.0, feo=0.0, sio2=9.5, al2o3=3.0, cao=0.5, mgo=0.3, mno=0.2),
    "ORE_B": dict(fe_t=62.0, feo=0.0, sio2=6.0, al2o3=2.5, cao=0.4, mgo=0.2, mno=0.1),
    "ORE_C": dict(fe_t=66.0, feo=0.0, sio2=3.0, al2o3=1.5, cao=0.3, mgo=0.1, mno=0.1),
}

PRICES = {"ORE_A": 3_000.0, "ORE_B": 5_500.0, "ORE_C": 9_000.0}

MAX_QTY  = {"ORE_A": 5_000.0, "ORE_B": 5_000.0, "ORE_C": 5_000.0}

# Per-ore share limits (as fractions, not %)
ORE_MIN_SHARE = {"ORE_A": 0.0,  "ORE_B": 0.0,  "ORE_C": 0.0}
ORE_MAX_SHARE = {"ORE_A": 1.0,  "ORE_B": 1.0,  "ORE_C": 1.0}

# Config constants (matches config.yaml defaults)
FOE_IN_SLAG    = 0.4   # % FeO that stays in slag
SI_IN_SLAG     = 0.5   # % Si in slag
TARGET_SLAG_MT = 700.0
FUEL_SLAG_MT   = 0.0   # no fuel inputs for this test
MIN_FE_MT      = 2_350.0
MAX_FE_MT      = 2_500.0

SLAG_BUDGET    = TARGET_SLAG_MT - FUEL_SLAG_MT   # = 700 MT

# ── Derived per-ore coefficients ─────────────────────────────────────────────

def effective_fe_pct(ore: str) -> float:
    c = CHEMISTRY[ore]
    return c["fe_t"] + (c["feo"] - FOE_IN_SLAG) * FE_FROM_FEO_FACTOR

def effective_slag_pct(ore: str) -> float:
    c = CHEMISTRY[ore]
    return (c["sio2"] - SI_IN_SLAG * SIO2_FROM_SI_FACTOR) + c["al2o3"] + c["cao"] + c["mgo"] + c["mno"]

print("=" * 60)
print("DUMMY ORE COEFFICIENTS")
print("=" * 60)
for o in ORES:
    fe   = effective_fe_pct(o)
    slag = effective_slag_pct(o)
    print(f"  {o}  eff_Fe={fe:.3f}%  eff_Slag={slag:.3f}%  price=₹{PRICES[o]:,.0f}/MT")

# ── Build and solve the LP ────────────────────────────────────────────────────
# Same structure as optimizer.py::run_optimizer()

n = len(ORES)

c_obj  = np.array([PRICES[o] for o in ORES], dtype=float)

slag_coeff  = [effective_slag_pct(o) / 100.0 for o in ORES]
fe_min_coef = [-effective_fe_pct(o)  / 100.0 for o in ORES]
fe_max_coef = [ effective_fe_pct(o)  / 100.0 for o in ORES]

A_ub: list = []
b_ub: list = []

# Slag
A_ub.append(slag_coeff)
b_ub.append(SLAG_BUDGET)

# Fe min
A_ub.append(fe_min_coef)
b_ub.append(-MIN_FE_MT)

# Fe max
A_ub.append(fe_max_coef)
b_ub.append(MAX_FE_MT)

# Share constraints (linearised same as optimizer.py)
sl = [ORE_MIN_SHARE[o] for o in ORES]
sh = [ORE_MAX_SHARE[o] for o in ORES]

for i in range(n):
    row = [sl[i]] * n
    row[i] = sl[i] - 1.0
    A_ub.append(row)
    b_ub.append(0.0)

for i in range(n):
    row = [-sh[i]] * n
    row[i] = 1.0 - sh[i]
    A_ub.append(row)
    b_ub.append(0.0)

bounds = [(0.0, MAX_QTY[o]) for o in ORES]

lp_result = linprog(
    c=c_obj,
    A_ub=np.array(A_ub, dtype=float),
    b_ub=np.array(b_ub, dtype=float),
    bounds=bounds,
    method="highs",
)

print()
print("=" * 60)
print("LP RESULT")
print("=" * 60)
if not lp_result.success:
    print("  INFEASIBLE — LP returned no solution")
    sys.exit(1)

lp_x = lp_result.x
lp_total_qty  = float(np.sum(lp_x))
lp_total_cost = float(lp_result.fun)
lp_cost_per_mt = lp_total_cost / lp_total_qty if lp_total_qty > 0 else 0.0
lp_fe_mt   = sum(lp_x[i] * effective_fe_pct(ORES[i]) / 100.0 for i in range(n))
lp_slag_mt = sum(lp_x[i] * effective_slag_pct(ORES[i]) / 100.0 for i in range(n))

for i, ore in enumerate(ORES):
    pct = 100.0 * lp_x[i] / lp_total_qty if lp_total_qty > 0 else 0.0
    print(f"  {ore}: {lp_x[i]:,.1f} MT  ({pct:.1f}%)")

print(f"\n  Total qty   : {lp_total_qty:,.1f} MT")
print(f"  Fe production: {lp_fe_mt:,.1f} MT  (target {MIN_FE_MT:.0f}–{MAX_FE_MT:.0f})")
print(f"  Ore slag     : {lp_slag_mt:,.1f} MT  (budget {SLAG_BUDGET:.0f})")
print(f"  Total cost   : ₹{lp_total_cost:,.0f}")
print(f"  Cost / MT    : ₹{lp_cost_per_mt:,.1f}")

# ── Constraint verification ───────────────────────────────────────────────────
print()
print("=" * 60)
print("CONSTRAINT CHECKS")
print("=" * 60)
eps = 1e-4

checks = {
    "Fe ≥ min"    : lp_fe_mt   >= MIN_FE_MT   - eps,
    "Fe ≤ max"    : lp_fe_mt   <= MAX_FE_MT   + eps,
    "Slag ≤ budget": lp_slag_mt <= SLAG_BUDGET + eps,
    "All qty ≥ 0" : all(v >= -eps for v in lp_x),
}
for name, ok in checks.items():
    status = "PASS" if ok else "FAIL ← constraint violated!"
    print(f"  {name:25s}: {status}")

# Share constraints
for i, ore in enumerate(ORES):
    share = lp_x[i] / lp_total_qty if lp_total_qty > 0 else 0.0
    ok_min = share >= ORE_MIN_SHARE[ore] - eps
    ok_max = share <= ORE_MAX_SHARE[ore] + eps
    if not (ok_min and ok_max):
        print(f"  Share {ore}: FAIL  ({share:.3f} not in [{ORE_MIN_SHARE[ore]:.2f}, {ORE_MAX_SHARE[ore]:.2f}])")

# ── Brute-force grid verification ─────────────────────────────────────────────
# Enumerate all combinations on a 50 MT grid and check whether any feasible
# point has strictly lower total cost than the LP optimum.

STEP = 50.0
print()
print("=" * 60)
print(f"BRUTE-FORCE GRID SEARCH (step={STEP:.0f} MT)")
print("=" * 60)

best_cost  = lp_total_cost
best_combo = None
checked    = 0
feasible   = 0
cheaper    = 0

grid = np.arange(0, 5001, STEP)

for combo in itertools.product(grid, repeat=n):
    checked += 1
    xs = list(combo)
    total = float(sum(xs))
    if total <= 0:
        continue

    fe_mt   = sum(xs[i] * effective_fe_pct(ORES[i])   / 100.0 for i in range(n))
    slag_mt = sum(xs[i] * effective_slag_pct(ORES[i]) / 100.0 for i in range(n))

    if fe_mt   < MIN_FE_MT   - eps: continue
    if fe_mt   > MAX_FE_MT   + eps: continue
    if slag_mt > SLAG_BUDGET + eps: continue

    # Share constraints
    ok = True
    for i in range(n):
        share = xs[i] / total
        if share < ORE_MIN_SHARE[ORES[i]] - eps or share > ORE_MAX_SHARE[ORES[i]] + eps:
            ok = False
            break
        if xs[i] > MAX_QTY[ORES[i]] + eps:
            ok = False
            break
    if not ok:
        continue

    feasible += 1
    cost = sum(xs[i] * PRICES[ORES[i]] for i in range(n))
    if cost < best_cost - 1.0:   # ₹1 tolerance for floating point
        cheaper += 1
        if best_combo is None or cost < sum(best_combo[1]):
            best_cost  = cost
            best_combo = (xs, [xs[i] * PRICES[ORES[i]] for i in range(n)])

print(f"  Combinations checked : {checked:,}")
print(f"  Feasible found       : {feasible:,}")
print(f"  Cheaper than LP      : {cheaper}")

print()
print("=" * 60)
print("VERDICT — SCENARIO 1")
print("=" * 60)
if cheaper == 0:
    print("  PASS — No grid point beats the LP. Optimizer is correct.")
else:
    print(f"  FAIL — {cheaper} grid point(s) found cheaper than LP!")
    if best_combo:
        xs = best_combo[0]
        cost  = sum(xs[i] * PRICES[ORES[i]] for i in range(n))
        print(f"    Best alternative: {dict(zip(ORES, xs))}")
        print(f"    Cost: Rs{cost:,.0f}  vs LP Rs{lp_total_cost:,.0f}")


# ═════════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — Slag constraint is BINDING
# ORE_A has high slag (20%), so the LP must blend with a cleaner ore to stay
# inside the 700 MT budget while meeting the Fe target.
# This tests the "maximise cheap ore up to the slag cap" principle.
# ═════════════════════════════════════════════════════════════════════════════

print()
print("=" * 60)
print("SCENARIO 2 — SLAG-BINDING TEST")
print("  ORE_A: cheap, very high slag  → LP must limit its share")
print("  ORE_B: medium, moderate slag  → fills up what A can't")
print("  ORE_C: expensive, clean       → fallback if B also not enough")
print("=" * 60)

CHEMISTRY2 = {
    #           Fe(T)  FeO   SiO2   Al2O3  CaO   MgO   MnO
    "ORE_A": dict(fe_t=57.0, feo=0.0, sio2=16.0, al2o3=5.0, cao=0.8, mgo=0.5, mno=0.3),
    "ORE_B": dict(fe_t=62.0, feo=0.0, sio2=8.0,  al2o3=3.0, cao=0.5, mgo=0.3, mno=0.2),
    "ORE_C": dict(fe_t=66.0, feo=0.0, sio2=3.0,  al2o3=1.5, cao=0.3, mgo=0.1, mno=0.1),
}
PRICES2    = {"ORE_A": 3_000.0, "ORE_B": 5_500.0, "ORE_C": 9_000.0}
MAX_QTY2   = {"ORE_A": 5_000.0, "ORE_B": 5_000.0, "ORE_C": 5_000.0}
MIN_SHARE2 = {"ORE_A": 0.0,  "ORE_B": 0.0,  "ORE_C": 0.0}
MAX_SHARE2 = {"ORE_A": 1.0,  "ORE_B": 1.0,  "ORE_C": 1.0}

def eff_fe2(ore):
    c = CHEMISTRY2[ore]
    return c["fe_t"] + (c["feo"] - FOE_IN_SLAG) * FE_FROM_FEO_FACTOR

def eff_slag2(ore):
    c = CHEMISTRY2[ore]
    return (c["sio2"] - SI_IN_SLAG * SIO2_FROM_SI_FACTOR) + c["al2o3"] + c["cao"] + c["mgo"] + c["mno"]

print()
for o in ORES:
    fe   = eff_fe2(o)
    slag = eff_slag2(o)
    max_ore_at_slag_cap = SLAG_BUDGET / (slag / 100.0) if slag > 0 else float("inf")
    fe_at_cap = max_ore_at_slag_cap * fe / 100.0
    print(f"  {o}  eff_Fe={fe:.2f}%  eff_Slag={slag:.2f}%"
          f"  → max qty at slag cap = {max_ore_at_slag_cap:,.0f} MT"
          f"  → Fe produced = {fe_at_cap:,.0f} MT")

# Build LP
slag_c2  = [eff_slag2(o) / 100.0 for o in ORES]
fe_min2  = [-eff_fe2(o)  / 100.0 for o in ORES]
fe_max2  = [ eff_fe2(o)  / 100.0 for o in ORES]

A2: list = []
b2: list = []
A2.append(slag_c2);  b2.append(SLAG_BUDGET)
A2.append(fe_min2);  b2.append(-MIN_FE_MT)
A2.append(fe_max2);  b2.append(MAX_FE_MT)

sl2 = [MIN_SHARE2[o] for o in ORES]
sh2 = [MAX_SHARE2[o] for o in ORES]
for i in range(n):
    row = [sl2[i]] * n; row[i] = sl2[i] - 1.0
    A2.append(row); b2.append(0.0)
for i in range(n):
    row = [-sh2[i]] * n; row[i] = 1.0 - sh2[i]
    A2.append(row); b2.append(0.0)

bounds2 = [(0.0, MAX_QTY2[o]) for o in ORES]
c_obj2  = np.array([PRICES2[o] for o in ORES], dtype=float)

lp2 = linprog(c=c_obj2, A_ub=np.array(A2, dtype=float),
              b_ub=np.array(b2, dtype=float), bounds=bounds2, method="highs")

print()
print("  LP RESULT:")
if not lp2.success:
    print("  INFEASIBLE")
else:
    x2 = lp2.x
    total2 = float(np.sum(x2))
    cost2  = float(lp2.fun)
    fe2_mt   = sum(x2[i] * eff_fe2(ORES[i])   / 100.0 for i in range(n))
    slag2_mt = sum(x2[i] * eff_slag2(ORES[i]) / 100.0 for i in range(n))
    for i, ore in enumerate(ORES):
        pct = 100.0 * x2[i] / total2 if total2 > 0 else 0.0
        print(f"    {ore}: {x2[i]:,.1f} MT ({pct:.1f}%)")
    print(f"    Total qty   : {total2:,.1f} MT")
    print(f"    Fe production: {fe2_mt:,.1f} MT  (target {MIN_FE_MT:.0f}–{MAX_FE_MT:.0f})")
    print(f"    Ore slag     : {slag2_mt:,.1f} MT  (budget {SLAG_BUDGET:.0f})")
    print(f"    Total cost   : Rs{cost2:,.0f}")
    print(f"    Cost / MT    : Rs{cost2/total2:,.1f}")

    # Brute-force check scenario 2
    best2 = cost2
    cheaper2 = 0
    for combo in itertools.product(np.arange(0, 5001, STEP), repeat=n):
        xs = list(combo)
        total = float(sum(xs))
        if total <= 0: continue
        fe_mt   = sum(xs[i] * eff_fe2(ORES[i])   / 100.0 for i in range(n))
        slag_mt = sum(xs[i] * eff_slag2(ORES[i]) / 100.0 for i in range(n))
        if fe_mt   < MIN_FE_MT   - eps: continue
        if fe_mt   > MAX_FE_MT   + eps: continue
        if slag_mt > SLAG_BUDGET + eps: continue
        ok = all(MIN_SHARE2[ORES[i]] - eps <= xs[i]/total <= MAX_SHARE2[ORES[i]] + eps
                 and xs[i] <= MAX_QTY2[ORES[i]] + eps for i in range(n))
        if not ok: continue
        cost = sum(xs[i] * PRICES2[ORES[i]] for i in range(n))
        if cost < best2 - 1.0:
            cheaper2 += 1

    print()
    print("=" * 60)
    print("VERDICT — SCENARIO 2")
    print("=" * 60)
    slag_pct_used = 100.0 * slag2_mt / SLAG_BUDGET
    print(f"  Slag budget used: {slag2_mt:.1f} / {SLAG_BUDGET:.0f} MT  ({slag_pct_used:.1f}%)")
    if slag_pct_used > 95:
        print("  Slag cap is the binding constraint — LP correctly maxed cheap ore.")
    else:
        print("  Fe constraint is the binding constraint (slag not tight).")
    if cheaper2 == 0:
        print("  PASS — No grid point beats the LP. Optimizer is correct.")
    else:
        print(f"  FAIL — {cheaper2} grid point(s) found cheaper than LP!")
