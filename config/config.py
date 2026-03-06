from pathlib import Path
import yaml
from dataclasses import dataclass
import streamlit as st

CONFIG_FILE = Path(__file__).parent / "config.yaml"


@dataclass
class Config:
    default_target_qty: float
    fallback_price: float
    fallback_min_pct: float
    sinter_min_pct: float
    sinter_max_pct: float
    fe_min_pct: float
    target_slag_qty: float
    ore_prices: dict
    ore_min_pct: dict


@st.cache_resource
def load_config() -> Config:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return Config(
        default_target_qty=float(raw.get("default_target_qty", 0)),
        fallback_price=float(raw.get("fallback_price", 0)),
        fallback_min_pct=float(raw.get("fallback_min_pct", 0)),
        sinter_min_pct=float(raw.get("sinter_min_pct", 0)),
        sinter_max_pct=float(raw.get("sinter_max_pct", 0)),
        fe_min_pct=float(raw["fe_min_pct"]),
        target_slag_qty=float(raw.get("target_slag_qty", 0)),
        ore_prices={k: float(v) for k, v in raw.get("ore_prices", {}).items()},
        ore_min_pct={k: float(v) for k, v in raw.get("ore_min_pct", {}).items()},
    )


# Shared instance
cfg = load_config()