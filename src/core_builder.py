from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from config.settings import FETCH_INSTRUMENT_INFO, TICKERS
from src.db import read_sql, write_df
from src.logger import log
from src.yfinance_loader import fetch_instruments


def load_staging_prices(engine: Engine) -> pd.DataFrame:
    sql = """
    SELECT
        ticker,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        adj_close_price,
        volume,
        dividends,
        stock_splits,
        batch_id,
        load_dttm
    FROM staging.stg_yf_prices
    ORDER BY ticker, trade_date;
    """
    prices = read_sql(engine, sql)
    if prices.empty:
        raise RuntimeError("staging.stg_yf_prices пустая. Сначала запустите scripts/02_load_staging_prices.py")
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.normalize()
    return prices


def build_core_frames(prices: pd.DataFrame, instruments_raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    prices = prices.copy()
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.normalize()

    min_date = prices["trade_date"].min()
    max_date = prices["trade_date"].max()
    all_dates = pd.date_range(min_date, max_date, freq="D")
    trading_dates = set(prices["trade_date"].dt.date)

    dim_date = pd.DataFrame({"full_date": all_dates})
    dim_date["date_key"] = dim_date["full_date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["full_date"].dt.year
    dim_date["quarter"] = dim_date["full_date"].dt.quarter
    dim_date["month"] = dim_date["full_date"].dt.month
    dim_date["month_name"] = dim_date["full_date"].dt.month_name()
    dim_date["week_number"] = dim_date["full_date"].dt.isocalendar().week.astype(int)
    dim_date["day_of_week"] = dim_date["full_date"].dt.dayofweek + 1
    dim_date["is_month_end"] = dim_date["full_date"].dt.is_month_end
    dim_date["is_quarter_end"] = dim_date["full_date"].dt.is_quarter_end
    dim_date["is_year_end"] = dim_date["full_date"].dt.is_year_end
    dim_date["is_trading_day"] = dim_date["full_date"].dt.date.isin(trading_dates)

    dim_date = dim_date[
        [
            "date_key", "full_date", "year", "quarter", "month", "month_name",
            "week_number", "day_of_week", "is_month_end", "is_quarter_end",
            "is_year_end", "is_trading_day",
        ]
    ]

    sectors = sorted(instruments_raw["sector_name"].fillna("Unknown").unique().tolist())
    dim_sector = pd.DataFrame({"sector_name": sectors})
    dim_sector.insert(0, "sector_key", range(1, len(dim_sector) + 1))

    dim_instrument = instruments_raw.copy()
    dim_instrument["sector_name"] = dim_instrument["sector_name"].fillna("Unknown")
    dim_instrument = dim_instrument.merge(dim_sector, on="sector_name", how="left")
    dim_instrument = dim_instrument.sort_values("ticker").reset_index(drop=True)
    dim_instrument.insert(0, "instrument_key", range(1, len(dim_instrument) + 1))
    dim_instrument = dim_instrument[
        [
            "instrument_key", "ticker", "instrument_name", "instrument_type",
            "exchange_code", "currency_code", "sector_key", "is_active",
            "valid_from", "valid_to",
        ]
    ]

    date_map = dim_date[["date_key", "full_date"]].rename(columns={"full_date": "trade_date"})
    instr_map = dim_instrument[["instrument_key", "ticker"]]

    fact_market = prices.merge(date_map, on="trade_date", how="left")
    fact_market = fact_market.merge(instr_map, on="ticker", how="left")
    fact_market = fact_market.sort_values(["instrument_key", "trade_date"])

    for col in ["open_price", "high_price", "low_price", "close_price", "adj_close_price", "dividends", "stock_splits"]:
        fact_market[col] = pd.to_numeric(fact_market[col], errors="coerce")
    fact_market["volume"] = pd.to_numeric(fact_market["volume"], errors="coerce").fillna(0).astype("int64")

    fact_market["daily_return"] = fact_market.groupby("instrument_key")["adj_close_price"].pct_change()
    shifted_price = fact_market.groupby("instrument_key")["adj_close_price"].shift(1)
    ratio = fact_market["adj_close_price"] / shifted_price
    fact_market["log_return"] = np.where(ratio > 0, np.log(ratio), np.nan)
    fact_market["price_range"] = fact_market["high_price"] - fact_market["low_price"]

    fact_market = fact_market.rename(columns={
        "dividends": "dividend_amount",
        "stock_splits": "split_ratio",
    })

    fact_market = fact_market[
        [
            "date_key", "instrument_key", "open_price", "high_price", "low_price",
            "close_price", "adj_close_price", "volume", "dividend_amount",
            "split_ratio", "daily_return", "log_return", "price_range",
            "batch_id", "load_dttm",
        ]
    ]

    return {
        "dim_date": dim_date,
        "dim_sector": dim_sector,
        "dim_instrument": dim_instrument,
        "fact_market_daily": fact_market,
    }


def build_and_load_core_market(engine: Engine) -> None:
    log("Чтение staging.stg_yf_prices")
    prices = load_staging_prices(engine)

    tickers = sorted(prices["ticker"].dropna().unique().tolist()) or TICKERS
    instruments_raw = fetch_instruments(tickers, FETCH_INSTRUMENT_INFO)

    log("Построение core-слоя рынка")
    frames = build_core_frames(prices, instruments_raw)

    log(f"Загрузка core.dim_date: {len(frames['dim_date']):,} строк")
    write_df(engine, frames["dim_date"], "core", "dim_date")

    log(f"Загрузка core.dim_sector: {len(frames['dim_sector']):,} строк")
    write_df(engine, frames["dim_sector"], "core", "dim_sector")

    log(f"Загрузка core.dim_instrument: {len(frames['dim_instrument']):,} строк")
    write_df(engine, frames["dim_instrument"], "core", "dim_instrument")

    log(f"Загрузка core.fact_market_daily: {len(frames['fact_market_daily']):,} строк")
    write_df(engine, frames["fact_market_daily"], "core", "fact_market_daily")
