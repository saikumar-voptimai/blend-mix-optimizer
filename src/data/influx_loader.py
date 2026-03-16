from influxdb_client_3 import InfluxDBClient3
import pandas as pd
from utils.config import cfg
import os
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("INFLUX_TOKEN")
class InfluxRMClient:
    """
    Production client for InfluxDB Serverless (v3)
    Fetches latest available value per chemistry field
    """
    def __init__(self):

        self.client = InfluxDBClient3(
            host=cfg.influxdb.url,
            token=token,
            org=cfg.influxdb.org,
        )

        self.database = cfg.influxdb.bucket
        self.measurement = cfg.influxdb.measurement

    def query_rm_data(self, days: int = 30, mode: str = "latest"):

        sql = f"""
        SELECT *
        FROM "{self.measurement}"
        WHERE time >= now() - interval '{days} day'
        ORDER BY time DESC
        """
        table = self.client.query(sql, database=self.database)
        df = table.to_pandas()
        if df is None or df.empty:
            raise RuntimeError("No RM chemistry returned from InfluxDB")
        # sort latest first
        df = df.sort_values("time", ascending=False)
        if mode == "avg":
            df = df.mean(numeric_only=True).to_frame().T
            return df

        # LATEST NON-NULL PER COLUMN
        latest_row = {}
        for col in df.columns:
            if col == "time":
                continue
            series = df[col].dropna()
            if not series.empty:
                latest_row[col] = series.iloc[0]
            else:
                latest_row[col] = None

        latest_df = pd.DataFrame([latest_row])
        return latest_df