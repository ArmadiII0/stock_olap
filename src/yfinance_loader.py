from __future__ import annotations

import time
from datetime import datetime
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

from src.logger import log

FALLBACK_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "GOOGL": "Communication Services",
    "GOOG": "Communication Services",
    "AMZN": "Consumer Cyclical",
    "META": "Communication Services",
    "TSLA": "Consumer Cyclical",
    "JPM": "Financial Services",
    "V": "Financial Services",
    "MA": "Financial Services",
    "UNH": "Healthcare",
    "XOM": "Energy",
    "PG": "Consumer Defensive",
    "KO": "Consumer Defensive",
    "PEP": "Consumer Defensive",
    "AVGO": "Technology",
    "COST": "Consumer Defensive",
    "HD": "Consumer Cyclical",
    "BAC": "Financial Services",
    "WMT": "Consumer Defensive",
}


def chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def normalize_date_column(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Date" in df.columns:
        date_col = "Date"
    elif "Datetime" in df.columns:
        date_col = "Datetime"
    elif "index" in df.columns:
        date_col = "index"
    else:
        raise ValueError(f"Не найдена колонка даты в yfinance DataFrame: {list(df.columns)}")

    df = df.rename(columns={date_col: "trade_date"})
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.tz_localize(None).dt.normalize()
    return df


def standardize_price_columns(df: pd.DataFrame, ticker: str, batch_id: str) -> pd.DataFrame:
    if "Date" not in df.columns and "Datetime" not in df.columns:
        df = df.reset_index()
    df = normalize_date_column(df)

    rename_map = {
        "Open": "open_price",
        "High": "high_price",
        "Low": "low_price",
        "Close": "close_price",
        "Adj Close": "adj_close_price",
        "Volume": "volume",
        "Dividends": "dividends",
        "Stock Splits": "stock_splits",
    }
    df = df.rename(columns=rename_map)

    required_cols = [
        "open_price", "high_price", "low_price", "close_price",
        "adj_close_price", "volume", "dividends", "stock_splits",
    ]
    for col in required_cols:
        if col not in df.columns:
            if col in {"dividends", "stock_splits"}:
                df[col] = 0.0
            elif col == "adj_close_price" and "close_price" in df.columns:
                df[col] = df["close_price"]
            else:
                df[col] = np.nan

    df["ticker"] = ticker.upper().strip()
    df["source_system"] = "yfinance"
    df["batch_id"] = batch_id
    df["load_dttm"] = datetime.now()

    df = df[
        [
            "ticker", "trade_date", "open_price", "high_price", "low_price",
            "close_price", "adj_close_price", "volume", "dividends",
            "stock_splits", "source_system", "batch_id", "load_dttm",
        ]
    ]

    df = df.dropna(subset=["trade_date"])
    df = df.dropna(subset=["open_price", "high_price", "low_price", "close_price"], how="all")
    df["volume"] = df["volume"].fillna(0).astype("int64")
    df["dividends"] = df["dividends"].fillna(0.0)
    df["stock_splits"] = df["stock_splits"].fillna(0.0)
    return df


def download_prices(
    tickers: list[str],
    start: str,
    end: str,
    chunk_size: int,
    batch_id: str,
) -> pd.DataFrame:
    log(f"Загрузка котировок из yfinance: {len(tickers)} тикеров, период {start} — {end}")
    frames: list[pd.DataFrame] = []

    for chunk in chunked(tickers, chunk_size):
        log(f"Загрузка пачки: {', '.join(chunk)}")
        try:
            if len(chunk) == 1:
                raw = yf.download(
                    tickers=chunk[0],
                    start=start,
                    end=end,
                    interval="1d",
                    actions=True,
                    auto_adjust=False,
                    group_by="column",
                    threads=True,
                    progress=False,
                    multi_level_index=False,
                )
                if raw is not None and not raw.empty:
                    frames.append(standardize_price_columns(raw, chunk[0], batch_id))
            else:
                raw = yf.download(
                    tickers=chunk,
                    start=start,
                    end=end,
                    interval="1d",
                    actions=True,
                    auto_adjust=False,
                    group_by="ticker",
                    threads=True,
                    progress=False,
                    multi_level_index=True,
                )
                if raw is None or raw.empty:
                    log(f"Предупреждение: пустой ответ для пачки {chunk}")
                    continue

                for ticker in chunk:
                    try:
                        one = raw[ticker].copy()
                        if one.empty:
                            log(f"Предупреждение: нет данных по {ticker}")
                            continue
                        frames.append(standardize_price_columns(one, ticker, batch_id))
                    except Exception as exc:
                        log(f"Предупреждение: не удалось разобрать {ticker}: {exc}")
        except Exception as exc:
            log(f"Ошибка загрузки пачки {chunk}: {exc}")

        time.sleep(0.5)

    if not frames:
        raise RuntimeError("yfinance не вернул данных. Проверьте тикеры, период и доступ к сети.")

    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["ticker", "trade_date"]).drop_duplicates(["ticker", "trade_date"])
    log(f"Загружено строк котировок: {len(prices):,}")
    return prices


def fetch_instruments(tickers: list[str], fetch_info: bool) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        ticker = ticker.upper().strip()
        info = {}
        if fetch_info:
            try:
                info = yf.Ticker(ticker).info or {}
                time.sleep(0.2)
            except Exception as exc:
                log(f"Предупреждение: не удалось получить info для {ticker}: {exc}")
                info = {}

        rows.append({
            "ticker": ticker,
            "instrument_name": info.get("longName") or info.get("shortName") or ticker,
            "instrument_type": "stock",
            "exchange_code": info.get("exchange") or info.get("fullExchangeName") or None,
            "currency_code": info.get("currency") or "USD",
            "sector_name": info.get("sector") or FALLBACK_SECTORS.get(ticker, "Unknown"),
            "is_active": True,
            "valid_from": pd.Timestamp("1900-01-01"),
            "valid_to": pd.NaT,
        })
    return pd.DataFrame(rows)
