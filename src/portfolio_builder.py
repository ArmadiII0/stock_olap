from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.engine import Engine

from config.settings import PORTFOLIO_CONFIG
from src.db import read_sql, write_df
from src.logger import log


@dataclass
class PortfolioConfig:
    name: str
    strategy_name: str
    initial_capital: float
    top_n: int
    lookback_days: int
    rebalance_threshold: float
    commission_rate: float
    requested_start_date: pd.Timestamp


def load_market_from_core(engine: Engine) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prices_sql = """
    SELECT
        d.full_date AS trade_date,
        i.ticker,
        i.instrument_key,
        f.adj_close_price,
        f.volume
    FROM core.fact_market_daily f
    JOIN core.dim_date d ON f.date_key = d.date_key
    JOIN core.dim_instrument i ON f.instrument_key = i.instrument_key
    ORDER BY i.ticker, d.full_date;
    """
    dim_date_sql = "SELECT date_key, full_date FROM core.dim_date ORDER BY full_date;"
    dim_instrument_sql = "SELECT instrument_key, ticker FROM core.dim_instrument ORDER BY ticker;"

    prices = read_sql(engine, prices_sql)
    dim_date = read_sql(engine, dim_date_sql)
    dim_instrument = read_sql(engine, dim_instrument_sql)

    if prices.empty:
        raise RuntimeError("core.fact_market_daily пустая. Сначала запустите scripts/03_build_core_market.py")

    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.normalize()
    dim_date["full_date"] = pd.to_datetime(dim_date["full_date"]).dt.normalize()
    return prices, dim_date, dim_instrument


def get_first_trading_date_on_or_after(prices: pd.DataFrame, requested_date: pd.Timestamp) -> pd.Timestamp:
    dates = sorted(prices.loc[prices["trade_date"] >= requested_date, "trade_date"].dropna().unique())
    if not dates:
        raise ValueError("Нет торговых дат после даты формирования портфеля.")
    return pd.Timestamp(dates[0])


def select_portfolio_instruments(
    prices: pd.DataFrame,
    start_date: pd.Timestamp,
    top_n: int,
    lookback_days: int,
) -> pd.DataFrame:
    history = prices[prices["trade_date"] <= start_date].copy()
    history = history.sort_values(["ticker", "trade_date"])
    history["daily_return"] = history.groupby("ticker")["adj_close_price"].pct_change()

    rows = []
    for ticker, g in history.groupby("ticker"):
        g = g.dropna(subset=["adj_close_price"]).tail(lookback_days)
        if len(g) < max(60, lookback_days // 2):
            continue

        first_price = float(g["adj_close_price"].iloc[0])
        last_price = float(g["adj_close_price"].iloc[-1])
        returns = g["daily_return"].dropna()
        if first_price <= 0 or last_price <= 0 or returns.empty:
            continue

        return_period = last_price / first_price - 1
        volatility = returns.std() * math.sqrt(252)
        avg_volume_60d = g["volume"].tail(60).mean()
        score = return_period / volatility if volatility and volatility > 0 else np.nan

        rows.append({
            "ticker": ticker,
            "last_price": last_price,
            "return_lookback": return_period,
            "volatility_lookback": volatility,
            "avg_volume_60d": avg_volume_60d,
            "risk_adjusted_return": score,
        })

    metrics = pd.DataFrame(rows)
    if metrics.empty:
        raise ValueError("Не удалось рассчитать метрики для отбора портфеля.")

    selected = (
        metrics
        .replace([np.inf, -np.inf], np.nan)
        .dropna(subset=["risk_adjusted_return", "volatility_lookback"])
        .query("avg_volume_60d > 0")
        .sort_values("risk_adjusted_return", ascending=False)
        .head(top_n)
        .copy()
    )

    if selected.empty:
        raise ValueError("После фильтрации не осталось инструментов для портфеля.")

    selected["inv_vol"] = 1 / selected["volatility_lookback"]
    selected["target_weight"] = selected["inv_vol"] / selected["inv_vol"].sum()
    return selected.reset_index(drop=True)


def build_portfolio_frames(
    prices: pd.DataFrame,
    dim_date: pd.DataFrame,
    dim_instrument: pd.DataFrame,
    cfg: PortfolioConfig,
    batch_id: str,
) -> dict[str, pd.DataFrame]:
    prices = prices.copy()
    prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.normalize()
    prices["adj_close_price"] = pd.to_numeric(prices["adj_close_price"], errors="coerce")
    prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce").fillna(0)

    actual_start_date = get_first_trading_date_on_or_after(prices, cfg.requested_start_date)
    selected = select_portfolio_instruments(prices, actual_start_date, cfg.top_n, cfg.lookback_days)

    selected_tickers = selected["ticker"].tolist()
    log("Состав модельного портфеля: " + ", ".join(selected_tickers))

    portfolio_key = 1
    dim_portfolio = pd.DataFrame([{
        "portfolio_key": portfolio_key,
        "portfolio_name": cfg.name,
        "strategy_name": cfg.strategy_name,
        "base_currency": "USD",
        "initial_capital": cfg.initial_capital,
        "created_at": datetime.now(),
    }])

    date_key_map = dict(zip(pd.to_datetime(dim_date["full_date"]).dt.normalize(), dim_date["date_key"]))
    instr_key_map = dict(zip(dim_instrument["ticker"], dim_instrument["instrument_key"]))
    target_weights = dict(zip(selected["ticker"], selected["target_weight"]))

    px = prices[prices["ticker"].isin(selected_tickers)].copy()
    trading_dates = sorted(px.loc[px["trade_date"] >= actual_start_date, "trade_date"].unique())
    if not trading_dates:
        raise ValueError("Нет торговых дат для построения портфеля.")

    price_pivot = (
        px.pivot_table(index="trade_date", columns="ticker", values="adj_close_price", aggfunc="last")
        .sort_index()
        .reindex(trading_dates)
        .ffill()
    )

    date_df = pd.DataFrame({"trade_date": pd.to_datetime(trading_dates)})
    date_df["month"] = date_df["trade_date"].dt.to_period("M")
    rebalance_dates = set(date_df.groupby("month")["trade_date"].min().tolist())
    rebalance_dates.discard(actual_start_date)

    cash = float(cfg.initial_capital)
    holdings = {ticker: 0.0 for ticker in selected_tickers}
    avg_cost = {ticker: 0.0 for ticker in selected_tickers}
    realized_pnl_by_ticker = {ticker: 0.0 for ticker in selected_tickers}
    total_commission = 0.0

    trades_rows = []
    positions_rows = []
    cash_rows = []

    def add_trade(trade_date, ticker, side, quantity, price, commission, reason):
        trades_rows.append({
            "trade_id": str(uuid.uuid4()),
            "trade_date_key": int(date_key_map[pd.Timestamp(trade_date).normalize()]),
            "instrument_key": int(instr_key_map[ticker]),
            "portfolio_key": portfolio_key,
            "side": side,
            "quantity": float(quantity),
            "trade_price": float(price),
            "commission": float(commission),
            "trade_amount": float(quantity * price),
            "trade_reason": reason,
            "batch_id": batch_id,
            "load_dttm": datetime.now(),
        })

    def execute_buy(trade_date, ticker, quantity, price, reason):
        nonlocal cash, total_commission
        if quantity <= 0 or price <= 0:
            return
        gross = quantity * price
        commission = gross * cfg.commission_rate
        total_cost = gross + commission
        if total_cost > cash:
            quantity = math.floor(cash / (price * (1 + cfg.commission_rate)))
            if quantity <= 0:
                return
            gross = quantity * price
            commission = gross * cfg.commission_rate
            total_cost = gross + commission

        old_qty = holdings[ticker]
        old_cost_value = old_qty * avg_cost[ticker]
        new_qty = old_qty + quantity
        avg_cost[ticker] = (old_cost_value + gross) / new_qty if new_qty > 0 else 0.0
        holdings[ticker] = new_qty
        cash -= total_cost
        total_commission += commission
        add_trade(trade_date, ticker, "BUY", quantity, price, commission, reason)

    def execute_sell(trade_date, ticker, quantity, price, reason):
        nonlocal cash, total_commission
        if quantity <= 0 or price <= 0:
            return
        quantity = min(quantity, holdings[ticker])
        if quantity <= 0:
            return
        gross = quantity * price
        commission = gross * cfg.commission_rate
        pnl = quantity * (price - avg_cost[ticker]) - commission
        holdings[ticker] -= quantity
        if holdings[ticker] <= 1e-9:
            holdings[ticker] = 0.0
            avg_cost[ticker] = 0.0
        realized_pnl_by_ticker[ticker] += pnl
        cash += gross - commission
        total_commission += commission
        add_trade(trade_date, ticker, "SELL", quantity, price, commission, reason)

    def portfolio_total_value(trade_date) -> float:
        prices_today = price_pivot.loc[trade_date]
        invested = sum(holdings[t] * float(prices_today[t]) for t in selected_tickers if not pd.isna(prices_today[t]))
        return cash + invested

    first_prices = price_pivot.loc[actual_start_date]
    for ticker in selected_tickers:
        price = float(first_prices[ticker])
        target_value = cfg.initial_capital * float(target_weights[ticker])
        qty = math.floor(target_value / price)
        execute_buy(actual_start_date, ticker, qty, price, "INITIAL_BUY")

    for trade_date in trading_dates:
        trade_date = pd.Timestamp(trade_date).normalize()

        if trade_date in rebalance_dates:
            prices_today = price_pivot.loc[trade_date]
            total_value = portfolio_total_value(trade_date)
            for ticker in selected_tickers:
                price = float(prices_today[ticker])
                if pd.isna(price) or price <= 0:
                    continue
                current_value = holdings[ticker] * price
                target_value = total_value * float(target_weights[ticker])
                diff_value = target_value - current_value
                weight_diff = diff_value / total_value if total_value else 0.0

                if abs(weight_diff) >= cfg.rebalance_threshold:
                    qty = math.floor(abs(diff_value) / price)
                    if qty <= 0:
                        continue
                    if diff_value > 0:
                        execute_buy(trade_date, ticker, qty, price, "REBALANCE")
                    else:
                        execute_sell(trade_date, ticker, qty, price, "REBALANCE")

        prices_today = price_pivot.loc[trade_date]
        total_value_after = portfolio_total_value(trade_date)
        date_key = int(date_key_map[trade_date])
        realized_total = sum(realized_pnl_by_ticker.values())

        for ticker in selected_tickers:
            qty = holdings[ticker]
            if qty <= 0:
                continue
            market_price = float(prices_today[ticker])
            if pd.isna(market_price) or market_price <= 0:
                continue
            market_value = qty * market_price
            positions_rows.append({
                "date_key": date_key,
                "instrument_key": int(instr_key_map[ticker]),
                "portfolio_key": portfolio_key,
                "quantity": float(qty),
                "avg_cost_price": float(avg_cost[ticker]),
                "market_price": market_price,
                "market_value": market_value,
                "position_weight": market_value / total_value_after if total_value_after else np.nan,
                "unrealized_pnl": qty * (market_price - avg_cost[ticker]),
                "realized_pnl": realized_pnl_by_ticker[ticker],
                "batch_id": batch_id,
                "calculation_dttm": datetime.now(),
            })

        cash_rows.append({
            "date_key": date_key,
            "portfolio_key": portfolio_key,
            "cash_value": cash,
            "realized_pnl": realized_total,
            "total_commission": total_commission,
            "batch_id": batch_id,
            "calculation_dttm": datetime.now(),
        })

    trades = pd.DataFrame(trades_rows)
    positions = pd.DataFrame(positions_rows)
    cash_df = pd.DataFrame(cash_rows)

    log(f"Сделок создано: {len(trades):,}")
    log(f"Строк позиций создано: {len(positions):,}")
    return {
        "dim_portfolio": dim_portfolio,
        "fact_trades": trades,
        "fact_positions": positions,
        "fact_portfolio_cash": cash_df,
    }


def build_and_load_portfolio(engine: Engine, batch_id: str) -> None:
    prices, dim_date, dim_instrument = load_market_from_core(engine)
    raw_cfg = PORTFOLIO_CONFIG
    cfg = PortfolioConfig(
        name=raw_cfg["portfolio_name"],
        strategy_name=raw_cfg["strategy_name"],
        initial_capital=float(raw_cfg["initial_capital"]),
        top_n=int(raw_cfg["top_n"]),
        lookback_days=int(raw_cfg["lookback_days"]),
        rebalance_threshold=float(raw_cfg["rebalance_threshold"]),
        commission_rate=float(raw_cfg["commission_rate"]),
        requested_start_date=pd.Timestamp(raw_cfg["portfolio_start"]),
    )

    frames = build_portfolio_frames(prices, dim_date, dim_instrument, cfg, batch_id)

    log(f"Загрузка core.dim_portfolio: {len(frames['dim_portfolio']):,} строк")
    write_df(engine, frames["dim_portfolio"], "core", "dim_portfolio")

    log(f"Загрузка core.fact_trades: {len(frames['fact_trades']):,} строк")
    write_df(engine, frames["fact_trades"], "core", "fact_trades")

    log(f"Загрузка core.fact_positions: {len(frames['fact_positions']):,} строк")
    write_df(engine, frames["fact_positions"], "core", "fact_positions")

    log(f"Загрузка core.fact_portfolio_cash: {len(frames['fact_portfolio_cash']):,} строк")
    write_df(engine, frames["fact_portfolio_cash"], "core", "fact_portfolio_cash")
