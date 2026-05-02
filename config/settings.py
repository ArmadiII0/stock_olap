from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

POSTGRES_USER = os.getenv("POSTGRES_USER", "ratibot")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "ratibor")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "stock_olap")
POSTGRES_ADMIN_DB = os.getenv("POSTGRES_ADMIN_DB", "postgres")

PROJECT_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
)

ADMIN_DB_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_ADMIN_DB}"
)

START_DATE = "2020-01-01"
END_DATE = "2026-01-01"

TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
    "META", "TSLA", "JPM", "V", "MA",
    "UNH", "XOM", "PG", "KO", "PEP",
    "AVGO", "COST", "HD", "BAC", "WMT",
]

YFINANCE_CHUNK_SIZE = 8
FETCH_INSTRUMENT_INFO = False

PORTFOLIO_CONFIG = {
    "portfolio_name": "Model Risk Adjusted Portfolio",
    "strategy_name": "Top-N risk-adjusted return with inverse volatility weights",
    "initial_capital": 1_000_000.0,
    "portfolio_start": "2023-01-03",
    "top_n": 10,
    "lookback_days": 252,
    "rebalance_threshold": 0.02,
    "commission_rate": 0.001,
}

REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = REPORTS_DIR / "charts"
SQL_DIR = BASE_DIR / "sql"
