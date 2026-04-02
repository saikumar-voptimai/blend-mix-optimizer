"""
Config Loader — Reads config.yaml and exposes all settings as typed variables.
Import this module anywhere in the app to access configuration.

Usage:
    from config import cfg
    price = cfg.ore_prices.get("NMDC ROM", cfg.fallback_price)
"""

from pathlib import Path
import yaml
from dataclasses import dataclass
import streamlit as st

CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "config.yaml"

@dataclass
class InfluxQueryConfig:
    default_range_days: int
    default_mode: str


@dataclass
class InfluxConfig:
    url: str
    org: str
    bucket: str
    stock_bucket: str
    measurement: str
    stock_measurement: str
    query: InfluxQueryConfig
    stock_materials: dict
    materials: dict


@dataclass
class Config:

    default_target_qty: float
    fallback_price: float
    fallback_max_pct: float
    fallback_min_pct: float
    min_fe_production_mt: float
    max_fe_production_mt: float

    fe_loss_constant: float

    feo_in_slag: float
    si_in_slag: float

    target_slag_qty: float

    ore_prices: dict
    ore_max_pct: dict
    ore_min_pct: dict

    coke_ash_analysis: dict
    nut_coke_ash_analysis: dict
    pci_ash_analysis: dict

    coke_defaults: dict
    nut_coke_defaults: dict
    pci_defaults: dict
    influxdb: InfluxConfig
    chemistry_map: dict


@st.cache_resource
def load_config() -> Config:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    
        influx_raw = raw["influxdb"]

    influx = InfluxConfig(
        url=influx_raw["url"],
        org=influx_raw["org"],
        bucket=influx_raw["bucket"],
        measurement=influx_raw["measurement"],
        materials=influx_raw.get("materials", {}),
        query=InfluxQueryConfig(**influx_raw["query"]),
        stock_bucket=influx_raw.get("stock_bucket"),
        stock_measurement=influx_raw.get("stock_measurement", "rm_stock"),
        stock_materials=influx_raw.get("stock_materials", {}),
    )

    return Config(

        default_target_qty=float(raw["default_target_qty"]),

        fallback_price=float(raw["fallback_price"]),
        fallback_max_pct=float(raw["fallback_max_pct"]),
        fallback_min_pct=float(raw["fallback_min_pct"]),

        min_fe_production_mt=float(raw["min_fe_production_mt"]),
        max_fe_production_mt=float(raw["max_fe_production_mt"]),

        fe_loss_constant=float(raw["fe_loss_constant"]),

        feo_in_slag=float(raw["feo_in_slag"]),
        si_in_slag=float(raw["si_in_slag"]),

        target_slag_qty=float(raw["target_slag_qty"]),

        ore_prices={k: float(v) for k, v in raw["ore_prices"].items()},
        ore_max_pct={k: float(v) for k, v in raw["ore_max_pct"].items()},
        ore_min_pct={k: float(v) for k, v in raw["ore_min_pct"].items()},

        coke_ash_analysis={k: float(v) for k, v in raw["coke_ash_analysis"].items()},
        nut_coke_ash_analysis={k: float(v) for k, v in raw["nut_coke_ash_analysis"].items()},
        pci_ash_analysis={k: float(v) for k, v in raw["pci_ash_analysis"].items()},

        coke_defaults={k: float(v) for k, v in raw["coke_defaults"].items()},
        nut_coke_defaults={k: float(v) for k, v in raw["nut_coke_defaults"].items()},
        pci_defaults={k: float(v) for k, v in raw["pci_defaults"].items()},
        influxdb=influx,
        chemistry_map=raw["chemistry_map"],
    )


cfg = load_config()


def persist_overrides(
    *,
    ore_min_pct: dict[str, float] | None = None,
    ore_max_pct: dict[str, float] | None = None,
    ore_prices: dict[str, float] | None = None,
    target_slag_qty: float | None = None,
) -> None:
    """Persist user overrides into config.yaml and update the live cfg in-place.

    Notes:
    - Updates are merged into the existing YAML (only provided keys change).
    - cfg is mutated in-place so modules that imported `cfg` see updates.
    """

    if ore_min_pct is None and ore_max_pct is None and ore_prices is None and target_slag_qty is None:
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    if ore_min_pct is not None:
        raw.setdefault("ore_min_pct", {})
        for k, v in ore_min_pct.items():
            raw["ore_min_pct"][k] = float(v)

    if ore_max_pct is not None:
        raw.setdefault("ore_max_pct", {})
        for k, v in ore_max_pct.items():
            raw["ore_max_pct"][k] = float(v)

    if ore_prices is not None:
        raw.setdefault("ore_prices", {})
        for k, v in ore_prices.items():
            raw["ore_prices"][k] = float(v)

    if target_slag_qty is not None:
        raw["target_slag_qty"] = float(target_slag_qty)

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            raw,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )

    # Update in-memory cfg (in-place) so all importers see the new values.
    if ore_min_pct is not None:
        cfg.ore_min_pct.update({k: float(v) for k, v in ore_min_pct.items()})
    if ore_max_pct is not None:
        cfg.ore_max_pct.update({k: float(v) for k, v in ore_max_pct.items()})
    if ore_prices is not None:
        cfg.ore_prices.update({k: float(v) for k, v in ore_prices.items()})
    if target_slag_qty is not None:
        cfg.target_slag_qty = float(target_slag_qty)

    # Clear cached loader so any future load_config() calls re-read the file.
    try:
        load_config.clear()
    except Exception:
        pass