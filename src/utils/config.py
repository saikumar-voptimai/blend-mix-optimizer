"""
Config Loader — Reads config.yaml and exposes all settings as typed variables.
"""

from pathlib import Path
import yaml
from dataclasses import dataclass
import streamlit as st


CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "config.yaml"


# Influx configuration


@dataclass
class InfluxQueryConfig:
    default_range_days: int
    default_mode: str


@dataclass
class InfluxConfig:
    url: str
    org: str
    bucket: str
    token: str
    measurement: str
    query: InfluxQueryConfig
    materials: dict

# Main application configuration


@dataclass
class Config:

    # blend settings
    default_target_qty: float
    fallback_price: float
    fallback_max_pct: float

    min_fe_production_mt: float
    fe_loss_constant: float

    sinter_min_pct: float
    sinter_max_pct: float

    feo_in_slag: float
    si_in_slag: float

    target_slag_qty: float

    # ore configs
    ore_prices: dict
    ore_max_pct: dict

    # fuel chemistry
    coke_ash_analysis: dict
    nut_coke_ash_analysis: dict
    pci_ash_analysis: dict

    # sidebar defaults
    coke_defaults: dict
    nut_coke_defaults: dict
    pci_defaults: dict

    # influx
    influxdb: InfluxConfig
    chemistry_map: dict


# Loader
@st.cache_resource
def load_config() -> Config:

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    influx_raw = raw["influxdb"]

    influx = InfluxConfig(
        url=influx_raw["url"],
        org=influx_raw["org"],
        bucket=influx_raw["bucket"],
        token=influx_raw["token"],
        measurement=influx_raw["measurement"],
        materials=influx_raw.get("materials", {}),
        query=InfluxQueryConfig(**influx_raw["query"]),
    )

    return Config(
        default_target_qty=float(raw["default_target_qty"]),
        fallback_price=float(raw["fallback_price"]),
        fallback_max_pct=float(raw["fallback_max_pct"]),

        min_fe_production_mt=float(raw["min_fe_production_mt"]),
        fe_loss_constant=float(raw["fe_loss_constant"]),

        sinter_min_pct=float(raw["sinter_min_pct"]),
        sinter_max_pct=float(raw["sinter_max_pct"]),

        feo_in_slag=float(raw["feo_in_slag"]),
        si_in_slag=float(raw["si_in_slag"]),

        target_slag_qty=float(raw["target_slag_qty"]),

        ore_prices={k: float(v) for k, v in raw["ore_prices"].items()},
        ore_max_pct={k: float(v) for k, v in raw["ore_max_pct"].items()},

        coke_ash_analysis={k: float(v) for k, v in raw["coke_ash_analysis"].items()},
        nut_coke_ash_analysis={k: float(v) for k, v in raw["nut_coke_ash_analysis"].items()},
        pci_ash_analysis={k: float(v) for k, v in raw["pci_ash_analysis"].items()},

        coke_defaults={k: float(v) for k, v in raw["coke_defaults"].items()},
        nut_coke_defaults={k: float(v) for k, v in raw["nut_coke_defaults"].items()},
        pci_defaults={k: float(v) for k, v in raw["pci_defaults"].items()},

        influxdb=influx,
        chemistry_map=raw["chemistry_map"],
    )


# shared config object
cfg = load_config()