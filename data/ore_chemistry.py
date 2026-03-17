"""
Data Layer — Loads ore chemistry from the Excel file.
Parses BF02 Bunker Ores Average Chemical Composition sheet.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Path to the chemistry file
CHEMISTRY_FILE = Path(__file__).parent.parent / "assets" / "BF02_Ores_Chemical_Composition.xlsx"

# Chemical columns used in calculations
CHEMISTRY_COLS = ["%Fe(T)", "%FeO", "%SiO2", "%Al2O3", "%CaO", "%MgO", "%TiO2", "%P", "%MnO", "%LOI"]

# Slag components
SLAG_COMPONENTS = ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]

# Special ore flags for UI warnings
ORE_FLAGS = {
    "Acore Industries": "⚠️ Mn Ore — Low Fe (~27%)",
    "Titani Ferrous CLO": "⚠️ High TiO2 (~12%) — Titaniferous",
    "NMDC Donimalai": "⚠️ Very High SiO2 (~14%)",
    "Sinter (SP-02)": "ℹ️ Self-Fluxing — High CaO (~10.6%)",
}


def load_ore_chemistry() -> pd.DataFrame:
    """
    Load and parse the ore chemistry Excel sheet.
    Returns a clean DataFrame indexed by ore name.
    """
    df = pd.read_excel(
        CHEMISTRY_FILE,
        sheet_name="Ore Chemical Compositions",
        header=2,       # Row 3 is the header
    )
    

    # Drop empty rows
    df = df.dropna(subset=["Ore / Material"])
    df = df[df["Ore / Material"].str.strip() != ""]

    # Keep only ore data rows (exclude notes and long text rows)
    # Valid ore rows: short names (< 40 chars) that don't look like sentences
    ore_mask = (
        ~df["Ore / Material"].str.startswith("Notes", na=True) &
        (df["Ore / Material"].str.len() < 40) &
        ~df["Ore / Material"].str.contains(r"\.", regex=True, na=False)
    )
    df = df[ore_mask].copy()

    # Replace '-' strings with NaN then 0
    df = df.replace("-", np.nan).infer_objects(copy=False)

    # Set ore name as index
    df = df.rename(columns={"Ore / Material": "ore_name"})
    df = df.set_index("ore_name")

    # Convert all chemistry columns to float
    for col in df.columns:
        if col != "ore_name":
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Add computed slag column
    df["Slag%"] = df[[c for c in SLAG_COMPONENTS if c in df.columns]].sum(axis=1)

    return df


def get_ore_list(df: pd.DataFrame) -> list[str]:
    """Return list of all ore names."""
    return df.index.tolist()


def get_ore_profile(df: pd.DataFrame, ore_name: str) -> dict:
    """Return chemistry profile for a single ore as dict."""
    return df.loc[ore_name].to_dict()


def get_ore_flag(ore_name: str) -> str | None:
    """Return warning flag string for special ores, or None."""
    return ORE_FLAGS.get(ore_name, None)