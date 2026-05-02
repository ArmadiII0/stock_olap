DROP MATERIALIZED VIEW IF EXISTS mart.mart_aggregates_monthly;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_risk_metrics;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_portfolio_structure;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_portfolio_daily;
DROP MATERIALIZED VIEW IF EXISTS mart.mart_instrument_returns;

TRUNCATE TABLE
    core.fact_portfolio_cash,
    core.fact_positions,
    core.fact_trades,
    core.fact_market_daily,
    core.dim_portfolio,
    core.dim_instrument,
    core.dim_sector,
    core.dim_date,
    staging.stg_yf_prices
RESTART IDENTITY CASCADE;
