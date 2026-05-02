CREATE TABLE IF NOT EXISTS core.dim_date (
    date_key            INT PRIMARY KEY,
    full_date           DATE NOT NULL UNIQUE,
    year                INT,
    quarter             INT,
    month               INT,
    month_name          TEXT,
    week_number         INT,
    day_of_week         INT,
    is_month_end        BOOLEAN,
    is_quarter_end      BOOLEAN,
    is_year_end         BOOLEAN,
    is_trading_day      BOOLEAN
);

CREATE TABLE IF NOT EXISTS core.dim_sector (
    sector_key          INT PRIMARY KEY,
    sector_name         TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS core.dim_instrument (
    instrument_key      INT PRIMARY KEY,
    ticker              TEXT NOT NULL UNIQUE,
    instrument_name     TEXT,
    instrument_type     TEXT DEFAULT 'stock',
    exchange_code       TEXT,
    currency_code       TEXT,
    sector_key          INT REFERENCES core.dim_sector(sector_key),
    is_active           BOOLEAN DEFAULT TRUE,
    valid_from          DATE,
    valid_to            DATE
);

CREATE TABLE IF NOT EXISTS core.dim_portfolio (
    portfolio_key       INT PRIMARY KEY,
    portfolio_name      TEXT NOT NULL UNIQUE,
    strategy_name       TEXT,
    base_currency       TEXT DEFAULT 'USD',
    initial_capital     NUMERIC(18, 2),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS core.fact_market_daily (
    date_key            INT NOT NULL REFERENCES core.dim_date(date_key),
    instrument_key      INT NOT NULL REFERENCES core.dim_instrument(instrument_key),
    open_price          NUMERIC(18, 6),
    high_price          NUMERIC(18, 6),
    low_price           NUMERIC(18, 6),
    close_price         NUMERIC(18, 6),
    adj_close_price     NUMERIC(18, 6),
    volume              BIGINT,
    dividend_amount     NUMERIC(18, 6),
    split_ratio         NUMERIC(18, 6),
    daily_return        NUMERIC(18, 10),
    log_return          NUMERIC(18, 10),
    price_range         NUMERIC(18, 6),
    batch_id            TEXT,
    load_dttm           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date_key, instrument_key)
);

CREATE TABLE IF NOT EXISTS core.fact_trades (
    trade_id            TEXT PRIMARY KEY,
    trade_date_key      INT NOT NULL REFERENCES core.dim_date(date_key),
    instrument_key      INT NOT NULL REFERENCES core.dim_instrument(instrument_key),
    portfolio_key       INT NOT NULL REFERENCES core.dim_portfolio(portfolio_key),
    side                TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity            NUMERIC(18, 6) NOT NULL,
    trade_price         NUMERIC(18, 6) NOT NULL,
    commission          NUMERIC(18, 6) DEFAULT 0,
    trade_amount        NUMERIC(18, 6),
    trade_reason        TEXT,
    batch_id            TEXT,
    load_dttm           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS core.fact_positions (
    date_key            INT NOT NULL REFERENCES core.dim_date(date_key),
    instrument_key      INT NOT NULL REFERENCES core.dim_instrument(instrument_key),
    portfolio_key       INT NOT NULL REFERENCES core.dim_portfolio(portfolio_key),
    quantity            NUMERIC(18, 6),
    avg_cost_price      NUMERIC(18, 6),
    market_price        NUMERIC(18, 6),
    market_value        NUMERIC(18, 6),
    position_weight     NUMERIC(18, 10),
    unrealized_pnl      NUMERIC(18, 6),
    realized_pnl        NUMERIC(18, 6),
    batch_id            TEXT,
    calculation_dttm    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date_key, instrument_key, portfolio_key)
);

CREATE TABLE IF NOT EXISTS core.fact_portfolio_cash (
    date_key            INT NOT NULL REFERENCES core.dim_date(date_key),
    portfolio_key       INT NOT NULL REFERENCES core.dim_portfolio(portfolio_key),
    cash_value          NUMERIC(18, 6),
    realized_pnl        NUMERIC(18, 6),
    total_commission    NUMERIC(18, 6),
    batch_id            TEXT,
    calculation_dttm    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (date_key, portfolio_key)
);

CREATE INDEX IF NOT EXISTS idx_fact_market_daily_instrument
    ON core.fact_market_daily(instrument_key);

CREATE INDEX IF NOT EXISTS idx_fact_market_daily_date
    ON core.fact_market_daily(date_key);

CREATE INDEX IF NOT EXISTS idx_fact_positions_portfolio_date
    ON core.fact_positions(portfolio_key, date_key);
