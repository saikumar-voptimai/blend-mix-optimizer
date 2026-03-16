from data.influx_loader import InfluxRMClient
import pandas as pd
from utils.config import cfg



# Special ore flags for UI
ORE_FLAGS = {
    "Acore Industries": "⚠️ Mn Ore — Low Fe (~27%)",
    "Titani Ferrous CLO": "⚠️ High TiO2 (~12%) — Titaniferous",
    "NMDC Donimalai": "⚠️ Very High SiO2 (~14%)",
    "Sinter (SP-02)": "ℹ️ Self-Fluxing — High CaO (~10.6%)",
}


SLAG_COMPONENTS = ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]
def load_ore_chemistry(days=30, mode="latest"):

    client = InfluxRMClient()

    df = client.query_rm_data(days=days, mode=mode)

    if df.shape[0] == 0:
        raise RuntimeError("No data returned from InfluxDB")

    row = df.iloc[0]

    chemistry = {}

    for field, value in row.items():

        # accept ores AND sinter AND any configured material
        parts = field.split("_pct_", 1)
        if len(parts) != 2:
            continue

        material_key, chem = parts

        if material_key not in cfg.influxdb.materials:
            continue

        if "_pct_" not in field:
            continue

        parts = field.split("_pct_", 1)
        if len(parts) != 2:
            continue

        ore_key, chem = parts

        if ore_key not in cfg.influxdb.materials:
            continue

        chem = chem.lower()

        if chem not in cfg.chemistry_map:
            continue

        if value is None:
            continue

        ore_name = cfg.influxdb.materials[ore_key]

        chemistry.setdefault(ore_name, {})
        chemistry[ore_name][cfg.chemistry_map[chem]] = float(value)

    chemistry_df = pd.DataFrame.from_dict(chemistry, orient="index")

    for col in cfg.chemistry_map.values():
        if col not in chemistry_df.columns:
            chemistry_df[col] = 0.0

    chemistry_df = chemistry_df.apply(pd.to_numeric, errors="coerce")
    chemistry_df = chemistry_df.fillna(0.0)

    chemistry_df["Slag%"] = chemistry_df[
        ["%SiO2", "%Al2O3", "%CaO", "%MgO", "%MnO"]
    ].sum(axis=1)

    return chemistry_df

# Helper functions used by UI
def get_ore_list(df: pd.DataFrame) -> list[str]:
    """Return list of ore names."""
    return df.index.tolist()
def get_ore_profile(df: pd.DataFrame, ore_name: str) -> dict:
    """Return chemistry profile for a single ore."""
    return df.loc[ore_name].to_dict()


def get_ore_flag(ore_name: str):
    """Return warning flag for special ores."""
    return ORE_FLAGS.get(ore_name)