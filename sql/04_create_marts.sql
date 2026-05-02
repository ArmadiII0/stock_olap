DROP MATERIALIZED VIEW IF EXISTS mart.mart_aggregates_monthly;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_risk_metrics;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_portfolio_structure;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_portfolio_daily;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_instrument_returns;

CREATE MATERIALIZED VIEW mart.mart_instrument_returns AS
SELECT
    d.full_date AS trade_date,
    i.ticker,
    i.instrument_name,
    s.sector_name,
    f.adj_close_price,
    f.volume,
    f.daily_return,
    EXP(
        SUM(CASE WHEN f.daily_return > -1 THEN LN(1 + f.daily_return) END)
        OVER (PARTITION BY i.instrument_key ORDER BY d.full_date)
    ) - 1 AS cumulative_return,
    AVG(f.daily_return)
        OVER (
            PARTITION BY i.instrument_key
            ORDER BY d.full_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS avg_return_30d,
    STDDEV_SAMP(f.daily_return)
        OVER (
            PARTITION BY i.instrument_key
            ORDER BY d.full_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) * SQRT(252) AS volatility_30d,
    STDDEV_SAMP(f.daily_return)
        OVER (
            PARTITION BY i.instrument_key
            ORDER BY d.full_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) * SQRT(252) AS volatility_252d,
    f.adj_close_price / NULLIF(
        LAG(f.adj_close_price, 252)
        OVER (PARTITION BY i.instrument_key ORDER BY d.full_date), 0
    ) - 1 AS return_252d
FROM core.fact_market_daily f
JOIN core.dim_date d ON f.date_key = d.date_key
JOIN core.dim_instrument i ON f.instrument_key = i.instrument_key
LEFT JOIN core.dim_sector s ON i.sector_key = s.sector_key
WHERE f.daily_return IS NOT NULL;

CREATE INDEX idx_mart_instrument_returns_ticker_date
    ON mart.mart_instrument_returns(ticker, trade_date);

CREATE MATERIALIZED VIEW mart.mart_portfolio_daily AS
WITH position_values AS (
    SELECT
        fp.date_key,
        fp.portfolio_key,
        SUM(fp.market_value) AS invested_value,
        SUM(fp.unrealized_pnl) AS unrealized_pnl
    FROM core.fact_positions fp
    GROUP BY fp.date_key, fp.portfolio_key
),
daily_values AS (
    SELECT
        d.full_date AS trade_date,
        p.portfolio_name,
        COALESCE(pv.invested_value, 0) AS invested_value,
        COALESCE(c.cash_value, 0) AS cash_value,
        COALESCE(pv.invested_value, 0) + COALESCE(c.cash_value, 0) AS portfolio_value,
        COALESCE(pv.unrealized_pnl, 0) AS unrealized_pnl,
        COALESCE(c.realized_pnl, 0) AS realized_pnl,
        COALESCE(c.total_commission, 0) AS total_commission
    FROM core.fact_portfolio_cash c
    JOIN core.dim_date d ON c.date_key = d.date_key
    JOIN core.dim_portfolio p ON c.portfolio_key = p.portfolio_key
    LEFT JOIN position_values pv
        ON c.date_key = pv.date_key
       AND c.portfolio_key = pv.portfolio_key
),
returns AS (
    SELECT
        *,
        portfolio_value / NULLIF(
            LAG(portfolio_value) OVER (PARTITION BY portfolio_name ORDER BY trade_date), 0
        ) - 1 AS daily_return,
        MAX(portfolio_value) OVER (
            PARTITION BY portfolio_name
            ORDER BY trade_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_max_value
    FROM daily_values
)
SELECT
    trade_date,
    portfolio_name,
    invested_value,
    cash_value,
    portfolio_value,
    unrealized_pnl,
    realized_pnl,
    total_commission,
    daily_return,
    EXP(
        SUM(CASE WHEN daily_return > -1 THEN LN(1 + daily_return) END)
        OVER (PARTITION BY portfolio_name ORDER BY trade_date)
    ) - 1 AS cumulative_return,
    portfolio_value / NULLIF(running_max_value, 0) - 1 AS max_drawdown,
    STDDEV_SAMP(daily_return)
        OVER (
            PARTITION BY portfolio_name
            ORDER BY trade_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) * SQRT(252) AS volatility_30d,
    STDDEV_SAMP(daily_return)
        OVER (
            PARTITION BY portfolio_name
            ORDER BY trade_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) * SQRT(252) AS volatility_252d
FROM returns;

CREATE INDEX idx_mart_portfolio_daily_name_date
    ON mart.mart_portfolio_daily(portfolio_name, trade_date);

CREATE MATERIALIZED VIEW mart.mart_portfolio_structure AS
SELECT
    d.full_date AS trade_date,
    p.portfolio_name,
    i.ticker,
    i.instrument_name,
    s.sector_name,
    fp.quantity,
    fp.avg_cost_price,
    fp.market_price,
    fp.market_value,
    fp.position_weight,
    fp.unrealized_pnl,
    fp.realized_pnl
FROM core.fact_positions fp
JOIN core.dim_date d ON fp.date_key = d.date_key
JOIN core.dim_portfolio p ON fp.portfolio_key = p.portfolio_key
JOIN core.dim_instrument i ON fp.instrument_key = i.instrument_key
LEFT JOIN core.dim_sector s ON i.sector_key = s.sector_key;

CREATE INDEX idx_mart_portfolio_structure_name_date
    ON mart.mart_portfolio_structure(portfolio_name, trade_date);

CREATE MATERIALIZED VIEW mart.mart_risk_metrics AS
WITH instrument_metrics AS (
    SELECT
        trade_date AS calc_date,
        'instrument'::TEXT AS object_type,
        ticker AS object_name,
        sector_name,
        return_252d,
        volatility_30d,
        volatility_252d,
        daily_return,
        adj_close_price / NULLIF(
            MAX(adj_close_price) OVER (
                PARTITION BY ticker
                ORDER BY trade_date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ), 0
        ) - 1 AS current_drawdown,
        AVG(daily_return) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) - 1.65 * STDDEV_SAMP(daily_return) OVER (
            PARTITION BY ticker
            ORDER BY trade_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) AS var_95_parametric
    FROM mart.mart_instrument_returns
),
portfolio_metrics AS (
    SELECT
        trade_date AS calc_date,
        'portfolio'::TEXT AS object_type,
        portfolio_name AS object_name,
        NULL::TEXT AS sector_name,
        portfolio_value / NULLIF(
            LAG(portfolio_value, 252) OVER (PARTITION BY portfolio_name ORDER BY trade_date), 0
        ) - 1 AS return_252d,
        volatility_30d,
        volatility_252d,
        daily_return,
        max_drawdown AS current_drawdown,
        AVG(daily_return) OVER (
            PARTITION BY portfolio_name
            ORDER BY trade_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) - 1.65 * STDDEV_SAMP(daily_return) OVER (
            PARTITION BY portfolio_name
            ORDER BY trade_date
            ROWS BETWEEN 251 PRECEDING AND CURRENT ROW
        ) AS var_95_parametric
    FROM mart.mart_portfolio_daily
)
SELECT
    calc_date,
    object_type,
    object_name,
    sector_name,
    return_252d,
    volatility_30d,
    volatility_252d,
    current_drawdown,
    var_95_parametric,
    return_252d / NULLIF(volatility_252d, 0) AS sharpe_like_ratio
FROM instrument_metrics
UNION ALL
SELECT
    calc_date,
    object_type,
    object_name,
    sector_name,
    return_252d,
    volatility_30d,
    volatility_252d,
    current_drawdown,
    var_95_parametric,
    return_252d / NULLIF(volatility_252d, 0) AS sharpe_like_ratio
FROM portfolio_metrics;

CREATE INDEX idx_mart_risk_metrics_date_type
    ON mart.mart_risk_metrics(calc_date, object_type);

CREATE MATERIALIZED VIEW mart.mart_aggregates_monthly AS
SELECT
    d.year,
    d.month,
    DATE_TRUNC('month', d.full_date)::DATE AS period_start,
    s.sector_name,
    i.ticker,
    p.portfolio_name,
    AVG(f.daily_return) AS avg_daily_return,
    STDDEV_SAMP(f.daily_return) * SQRT(252) AS annualized_volatility,
    SUM(f.volume) AS total_volume,
    AVG(fp.position_weight) AS avg_portfolio_weight,
    SUM(fp.market_value) AS total_market_value
FROM core.fact_market_daily f
JOIN core.dim_date d ON f.date_key = d.date_key
JOIN core.dim_instrument i ON f.instrument_key = i.instrument_key
LEFT JOIN core.dim_sector s ON i.sector_key = s.sector_key
LEFT JOIN core.fact_positions fp
    ON f.date_key = fp.date_key
   AND f.instrument_key = fp.instrument_key
LEFT JOIN core.dim_portfolio p ON fp.portfolio_key = p.portfolio_key
GROUP BY
    d.year,
    d.month,
    DATE_TRUNC('month', d.full_date),
    s.sector_name,
    i.ticker,
    p.portfolio_name;

CREATE INDEX idx_mart_aggregates_monthly_period
    ON mart.mart_aggregates_monthly(period_start, sector_name, ticker);

CREATE OR REPLACE PROCEDURE mart.refresh_all_marts()
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mart.mart_instrument_returns;
    REFRESH MATERIALIZED VIEW mart.mart_portfolio_daily;
    REFRESH MATERIALIZED VIEW mart.mart_portfolio_structure;
    REFRESH MATERIALIZED VIEW mart.mart_risk_metrics;
    REFRESH MATERIALIZED VIEW mart.mart_aggregates_monthly;
END;
$$;
