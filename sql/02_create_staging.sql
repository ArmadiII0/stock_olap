-- meta.load_log хранит историю запусков загрузки: batch_id, статус, количество строк и текст ошибки.
CREATE TABLE IF NOT EXISTS meta.load_log (
    batch_id            TEXT PRIMARY KEY,
    source_system       TEXT,
    target_table        TEXT,
    load_started_at     TIMESTAMP,
    load_finished_at    TIMESTAMP,
    rows_loaded         INT,
    status              TEXT,
    error_message       TEXT
);


-- staging.stg_yf_prices — копия котировок из yfinance в едином формате, без сложной бизнес-логики.
CREATE TABLE IF NOT EXISTS staging.stg_yf_prices (
    ticker              TEXT NOT NULL,
    trade_date          DATE NOT NULL,
    open_price          NUMERIC(18, 6),
    high_price          NUMERIC(18, 6),
    low_price           NUMERIC(18, 6),
    close_price         NUMERIC(18, 6),
    adj_close_price     NUMERIC(18, 6),
    volume              BIGINT,
    dividends           NUMERIC(18, 6),
    stock_splits        NUMERIC(18, 6),
    source_system       TEXT DEFAULT 'yfinance',
    batch_id            TEXT,
    load_dttm           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Индекс ускоряет выборки по тикеру и дате при построении core-слоя.
CREATE INDEX IF NOT EXISTS idx_stg_yf_prices_ticker_date
    ON staging.stg_yf_prices(ticker, trade_date);
