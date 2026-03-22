from influxdb_client_3 import InfluxDBClient3
import pandas as pd
from utils.config import cfg
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("INFLUX_TOKEN")


class InfluxClient:
    """
    Production InfluxDB client (v3)

    Supports:
    - RM chemistry (historical + latest non-null)
    - RM stock (latest snapshot)

    Handles multiple buckets (rm + stock)
    """

    def __init__(self):
        self.client = InfluxDBClient3(
            host=cfg.influxdb.url,
            token=token,
            org=cfg.influxdb.org,
        )

        # 🔹 Separate buckets (current requirement)
        self.rm_bucket = cfg.influxdb.bucket
        self.stock_bucket = cfg.influxdb.stock_bucket

        self.rm_measurement = cfg.influxdb.measurement
        self.stock_measurement = "rm_stock"

    # RM CHEMISTRY

    def query_rm_data(self, days: int = 30, mode: str = "latest"):
        sql = f"""
        SELECT *
        FROM "{self.rm_measurement}"
        WHERE time >= now() - interval '{days} day'
        ORDER BY time DESC
        """

        table = self.client.query(sql, database=self.rm_bucket)
        df = table.to_pandas()

        if df is None or df.empty:
            raise RuntimeError("No RM chemistry returned from InfluxDB")

        df = df.sort_values("time", ascending=False)

        if mode == "avg":
            return df.mean(numeric_only=True).to_frame().T

        #  latest non-null per column
        latest_row = {}
        for col in df.columns:
            if col == "time":
                continue

            series = df[col].dropna()
            latest_row[col] = series.iloc[0] if not series.empty else None

        return pd.DataFrame([latest_row])

    # RM STOCK

    def query_rm_stock(self):
        """
        Fetch latest stock snapshot (wide format)
        """
        sql = f"""
        SELECT *
        FROM "{self.stock_measurement}"
        ORDER BY time DESC
        LIMIT 1
        """

        table = self.client.query(sql, database=self.stock_bucket)
        df = table.to_pandas()

        if df is None or df.empty:
            raise RuntimeError("No RM stock data found in InfluxDB")

        return df

    # STOCK → UI MAPPING (VERY IMPORTANT)
    def get_stock_map(self, material_map: dict):
        """
        material_map example:
        {
            "Lloyds Metals & Energy": "lloyds_mt",
            "NMDC Donimalai": "nmdc_donimalai_mt"
        }
        """
        df = self.query_rm_stock()
        row = df.iloc[0]

        result = {}

        for ui_name, influx_field in material_map.items():
            val = row.get(influx_field)

            if pd.isna(val):
                val = 0

            result[ui_name] = float(val)

        return result
