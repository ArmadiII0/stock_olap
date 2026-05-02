# Stock OLAP

Учебный проект аналитического хранилища фондового рынка:

```text
source/yfinance → staging → core → mart → reports/charts
```

Проект использует PostgreSQL, yfinance, pandas, SQLAlchemy и matplotlib.

## 1. Установка

```bash
pip install -r requirements.txt
cp .env.example .env
```

В `.env` укажите свой пароль PostgreSQL.

## 2. Полный запуск

Из корня проекта:

```bash
python scripts/run_all.py
```

Этот запуск выполнит все шаги:

```text
00_create_database.py        создать БД stock_olap
01_init_database.py          создать схемы и таблицы
02_load_staging_prices.py    загрузить котировки из yfinance в staging
03_build_core_market.py      построить core-слой рынка
04_build_portfolio.py        построить модельный портфель
05_build_marts.py            создать materialized views в mart
06_check_dataset_volume.py   вывести объём таблиц
07_make_charts.py            построить графики в reports/charts
```

## 3. Ручной запуск по этапам

```bash
python scripts/00_create_database.py
python scripts/01_init_database.py
python scripts/02_load_staging_prices.py
python scripts/03_build_core_market.py
python scripts/04_build_portfolio.py
python scripts/05_build_marts.py
python scripts/06_check_dataset_volume.py
python scripts/07_make_charts.py
```

## 4. Настройки

Основной конфиг:

```text
config/settings.py
```

Там задаются тикеры, период загрузки и параметры портфеля.

## 5. Что получится в PostgreSQL

База данных:

```text
stock_olap
```

Схемы:

```text
staging
core
mart
meta
```

Главные таблицы и витрины:

```text
staging.stg_yf_prices
core.dim_date
core.dim_sector
core.dim_instrument
core.dim_portfolio
core.fact_market_daily
core.fact_trades
core.fact_positions
core.fact_portfolio_cash
mart.mart_instrument_returns
mart.mart_portfolio_daily
mart.mart_portfolio_structure
mart.mart_risk_metrics
mart.mart_aggregates_monthly
```

## 6. Графики

После запуска `07_make_charts.py` появятся изображения:

```text
reports/charts/portfolio_value.png
reports/charts/portfolio_cumulative_return.png
reports/charts/portfolio_drawdown.png
reports/charts/top_instrument_returns.png
reports/charts/risk_return_scatter.png
reports/charts/portfolio_structure.png
reports/charts/monthly_sector_returns.png
```

Графики строятся из OLAP-витрин `mart`, а не напрямую из сырых данных.

## 7. Проверочные SQL-запросы

```sql
SELECT COUNT(*) FROM staging.stg_yf_prices;
SELECT COUNT(*) FROM core.fact_market_daily;
SELECT COUNT(*) FROM core.fact_trades;
SELECT COUNT(*) FROM core.fact_positions;

SELECT *
FROM mart.mart_portfolio_daily
ORDER BY trade_date DESC
LIMIT 10;

SELECT *
FROM mart.mart_risk_metrics
WHERE calc_date = (SELECT MAX(calc_date) FROM mart.mart_risk_metrics)
ORDER BY object_type, sharpe_like_ratio DESC NULLS LAST
LIMIT 20;
```

## 8. Пересборка

Если нужно очистить данные и начать заново:

```bash
python scripts/00_reset_database.py
python scripts/01_init_database.py
python scripts/02_load_staging_prices.py
python scripts/03_build_core_market.py
python scripts/04_build_portfolio.py
python scripts/05_build_marts.py
python scripts/06_check_dataset_volume.py
python scripts/07_make_charts.py
```
