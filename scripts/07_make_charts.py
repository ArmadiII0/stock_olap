"""Строит PNG-графики по готовым OLAP-витринам."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib.pyplot as plt
import pandas as pd

# Графики строятся уже не из raw/core-таблиц, а из готовых OLAP-витрин mart.
from config.settings import CHARTS_DIR
from src.db import get_project_engine, read_sql
from src.logger import log


def ensure_chart_dir() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)


def save_portfolio_value_chart(engine) -> None:
    """Строит график стоимости портфеля во времени."""
    sql = """
    SELECT
        trade_date,
        portfolio_name,
        portfolio_value
    FROM mart.mart_portfolio_daily
    ORDER BY trade_date;
    """
    df = read_sql(engine, sql)

    # Каждый график сначала проверяет наличие данных, чтобы скрипт не падал на пустой витрине.
    if df.empty:
        log("Нет данных для графика стоимости портфеля")
        return

    df["trade_date"] = pd.to_datetime(df["trade_date"])

    plt.figure(figsize=(12, 6))
    plt.plot(df["trade_date"], df["portfolio_value"])
    plt.title("Portfolio Value Over Time")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value")
    plt.grid(True)
    plt.tight_layout()
    path = CHARTS_DIR / "portfolio_value.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_portfolio_cumulative_return_chart(engine) -> None:
    """Строит график накопленной доходности портфеля."""
    sql = """
    SELECT
        trade_date,
        portfolio_name,
        cumulative_return
    FROM mart.mart_portfolio_daily
    ORDER BY trade_date;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для графика кумулятивной доходности")
        return

    df["trade_date"] = pd.to_datetime(df["trade_date"])

    plt.figure(figsize=(12, 6))
    plt.plot(df["trade_date"], df["cumulative_return"])
    plt.title("Portfolio Cumulative Return")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return")
    plt.grid(True)
    plt.tight_layout()
    path = CHARTS_DIR / "portfolio_cumulative_return.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_portfolio_drawdown_chart(engine) -> None:
    """Показывает просадку портфеля относительно исторического максимума."""
    sql = """
    SELECT
        trade_date,
        portfolio_name,
        max_drawdown
    FROM mart.mart_portfolio_daily
    ORDER BY trade_date;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для графика просадки")
        return

    df["trade_date"] = pd.to_datetime(df["trade_date"])

    plt.figure(figsize=(12, 6))
    plt.plot(df["trade_date"], df["max_drawdown"])
    plt.title("Portfolio Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.grid(True)
    plt.tight_layout()
    path = CHARTS_DIR / "portfolio_drawdown.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_top_instrument_returns_chart(engine) -> None:
    """Показывает самые доходные инструменты на последнюю доступную дату."""
    sql = """
    WITH last_date AS (
        SELECT MAX(trade_date) AS max_trade_date
        FROM mart.mart_instrument_returns
    )
    SELECT
        r.ticker,
        r.sector_name,
        r.cumulative_return
    FROM mart.mart_instrument_returns r
    JOIN last_date d
        ON r.trade_date = d.max_trade_date
    ORDER BY r.cumulative_return DESC
    LIMIT 15;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для графика доходности инструментов")
        return

    plt.figure(figsize=(12, 6))
    plt.bar(df["ticker"], df["cumulative_return"])
    plt.title("Top Instruments by Cumulative Return")
    plt.xlabel("Ticker")
    plt.ylabel("Cumulative Return")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y")
    plt.tight_layout()
    path = CHARTS_DIR / "top_instrument_returns.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_risk_return_scatter_chart(engine) -> None:
    """Строит карту риск-доходность по инструментам и портфелю."""
    sql = """
    WITH last_date AS (
        SELECT MAX(calc_date) AS max_calc_date
        FROM mart.mart_risk_metrics
    )
    SELECT
        object_type,
        object_name,
        sector_name,
        return_252d,
        volatility_252d
    FROM mart.mart_risk_metrics r
    JOIN last_date d
        ON r.calc_date = d.max_calc_date
    WHERE return_252d IS NOT NULL
      AND volatility_252d IS NOT NULL
    ORDER BY object_type, object_name;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для risk-return графика")
        return

    plt.figure(figsize=(11, 7))
    plt.scatter(df["volatility_252d"], df["return_252d"])

    for _, row in df.iterrows():
        plt.annotate(
            row["object_name"],
            (row["volatility_252d"], row["return_252d"]),
            fontsize=8,
        )

    plt.title("Risk-Return Map")
    plt.xlabel("Annualized Volatility 252d")
    plt.ylabel("Return 252d")
    plt.grid(True)
    plt.tight_layout()
    path = CHARTS_DIR / "risk_return_scatter.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_portfolio_structure_chart(engine) -> None:
    """Показывает текущие веса инструментов в портфеле."""
    sql = """
    WITH last_date AS (
        SELECT MAX(trade_date) AS max_trade_date
        FROM mart.mart_portfolio_structure
    )
    SELECT
        s.ticker,
        s.position_weight
    FROM mart.mart_portfolio_structure s
    JOIN last_date d
        ON s.trade_date = d.max_trade_date
    ORDER BY s.position_weight DESC;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для графика структуры портфеля")
        return

    plt.figure(figsize=(10, 6))
    plt.bar(df["ticker"], df["position_weight"])
    plt.title("Current Portfolio Structure")
    plt.xlabel("Ticker")
    plt.ylabel("Position Weight")
    plt.xticks(rotation=45)
    plt.grid(True, axis="y")
    plt.tight_layout()
    path = CHARTS_DIR / "portfolio_structure.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def save_monthly_sector_returns_chart(engine) -> None:
    """Строит динамику средней дневной доходности по секторам за каждый месяц."""
    sql = """
    SELECT
        period_start,
        sector_name,
        AVG(avg_daily_return) AS avg_daily_return
    FROM mart.mart_aggregates_monthly
    WHERE sector_name IS NOT NULL
    GROUP BY period_start, sector_name
    ORDER BY period_start, sector_name;
    """
    df = read_sql(engine, sql)

    if df.empty:
        log("Нет данных для графика месячной доходности по секторам")
        return

    df["period_start"] = pd.to_datetime(df["period_start"])

    pivot = df.pivot_table(
        index="period_start",
        columns="sector_name",
        values="avg_daily_return",
        aggfunc="mean",
    ).sort_index()

    plt.figure(figsize=(13, 7))
    for col in pivot.columns:
        plt.plot(pivot.index, pivot[col], label=col)

    plt.title("Monthly Average Daily Return by Sector")
    plt.xlabel("Month")
    plt.ylabel("Average Daily Return")
    plt.grid(True)
    plt.legend(fontsize=8)
    plt.tight_layout()
    path = CHARTS_DIR / "monthly_sector_returns.png"
    plt.savefig(path, dpi=150)
    plt.close()

    log(f"Сохранён график: {path}")


def main() -> None:
    """Запускает построение всех графиков."""
    log("Построение графиков")
    ensure_chart_dir()
    engine = get_project_engine()

    save_portfolio_value_chart(engine)
    save_portfolio_cumulative_return_chart(engine)
    save_portfolio_drawdown_chart(engine)
    save_top_instrument_returns_chart(engine)
    save_risk_return_scatter_chart(engine)
    save_portfolio_structure_chart(engine)
    save_monthly_sector_returns_chart(engine)

    log("Графики построены")


if __name__ == "__main__":
    main()
