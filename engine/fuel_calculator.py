"""
Fuel Slag & Fe Calculator — Computes slag and Fe contribution from coke, nut coke, and PCI.

Slag per fuel:
    ash_qty_MT = fuel_qty_MT × (ash_pct / 100)
    slag_MT    = ash_qty_MT  × (SiO2 + Al2O3 + CaO + MgO)_ash / 100

Fe per fuel (from Fe2O3 in ash):
    fe_mt = ash_qty_MT × (Fe2O3_ash / 100) × FE_FROM_FE2O3_FACTOR
    FE_FROM_FE2O3_FACTOR = 2 × 55.845 / 159.69 = 0.6994
"""

from dataclasses import dataclass
from config.config import cfg

# Fe2O3 → Fe conversion: 2 × mol_wt(Fe) / mol_wt(Fe2O3)
FE_FROM_FE2O3_FACTOR = (2 * 55.845) / 159.69   # = 0.6994


@dataclass
class FuelInput:
    coke_qty_mt:      float
    coke_ash_pct:     float
    nut_coke_qty_mt:  float
    nut_coke_ash_pct: float
    pci_qty_mt:       float
    pci_ash_pct:      float


@dataclass
class FuelSlagResult:
    # Coke
    coke_ash_qty_mt:  float
    coke_slag_mt:     float
    coke_fe_mt:       float
    # Nut Coke
    nut_coke_ash_qty_mt: float
    nut_coke_slag_mt: float
    nut_coke_fe_mt:   float
    # PCI
    pci_ash_qty_mt:   float
    pci_slag_mt:      float
    pci_fe_mt:        float
    # Totals
    total_fuel_slag_mt: float
    total_fuel_fe_mt:   float


def _slag_factor(ash_analysis: dict) -> float:
    """Sum of slag-forming oxides (SiO2+Al2O3+CaO+MgO) as fraction."""
    return (
        ash_analysis.get("SiO2",  0.0) +
        ash_analysis.get("Al2O3", 0.0) +
        ash_analysis.get("CaO",   0.0) +
        ash_analysis.get("MgO",   0.0) +
        ash_analysis.get("MnO",   0.0)    # Include MnO if present, else ignore
    ) / 100.0


def _fe_factor(ash_analysis: dict) -> float:
    """Fe contribution from Fe2O3 in ash as fraction."""
    return ash_analysis.get("Fe2O3", 0.0) / 100.0 * FE_FROM_FE2O3_FACTOR


def calculate_fuel_slag(fuel: FuelInput) -> FuelSlagResult:
    """Calculate slag and Fe contribution from all three fuels."""

    # Coke
    coke_ash_qty  = fuel.coke_qty_mt * (fuel.coke_ash_pct / 100.0)
    coke_slag     = coke_ash_qty * _slag_factor(cfg.coke_ash_analysis)
    coke_fe       = coke_ash_qty * _fe_factor(cfg.coke_ash_analysis)

    # Nut Coke
    nut_ash_qty   = fuel.nut_coke_qty_mt * (fuel.nut_coke_ash_pct / 100.0)
    nut_coke_slag = nut_ash_qty * _slag_factor(cfg.nut_coke_ash_analysis)
    nut_coke_fe   = nut_ash_qty * _fe_factor(cfg.nut_coke_ash_analysis)

    # PCI
    pci_ash_qty   = fuel.pci_qty_mt * (fuel.pci_ash_pct / 100.0)
    pci_slag      = pci_ash_qty * _slag_factor(cfg.pci_ash_analysis)
    pci_fe        = pci_ash_qty * _fe_factor(cfg.pci_ash_analysis)

    total_slag = coke_slag + nut_coke_slag + pci_slag
    total_fe   = coke_fe   + nut_coke_fe   + pci_fe

    return FuelSlagResult(
        coke_ash_qty_mt     = round(coke_ash_qty,  2),
        coke_slag_mt        = round(coke_slag,     2),
        coke_fe_mt          = round(coke_fe,       2),
        nut_coke_ash_qty_mt = round(nut_ash_qty,   2),
        nut_coke_slag_mt    = round(nut_coke_slag, 2),
        nut_coke_fe_mt      = round(nut_coke_fe,   2),
        pci_ash_qty_mt      = round(pci_ash_qty,   2),
        pci_slag_mt         = round(pci_slag,      2),
        pci_fe_mt           = round(pci_fe,        2),
        total_fuel_slag_mt  = round(total_slag,    2),
        total_fuel_fe_mt    = round(total_fe,      2),
    )