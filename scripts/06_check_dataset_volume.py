from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from src.db import get_project_engine


TABLES = [
    "staging.stg_yf_prices",
    "core.dim_date",
    "core.dim_sector",
    "core.dim_instrument",
    "core.dim_portfolio",
    "core.fact_market_daily",
    "core.fact_trades",
    "core.fact_positions",
    "core.fact_portfolio_cash",
    "mart.mart_instrument_returns",
    "mart.mart_portfolio_daily",
    "mart.mart_portfolio_structure",
    "mart.mart_risk_metrics",
    "mart.mart_aggregates_monthly",
]


def main() -> None:
    engine = get_project_engine()

    print()
    print("DATASET VOLUME REPORT")
    print("-" * 62)
    print(f"{'table_name':<45} {'rows_count':>12}")
    print("-" * 62)

    with engine.connect() as conn:
        for table in TABLES:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            except Exception:
                count = "N/A"
            print(f"{table:<45} {str(count):>12}")

    print("-" * 62)
    print()


if __name__ == "__main__":
    main()
