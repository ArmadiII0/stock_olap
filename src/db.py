"""Небольшой слой доступа к PostgreSQL.

Остальной код не создаёт подключения напрямую, а использует эти функции для SQL-запросов и записи DataFrame в таблицы."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import ADMIN_DB_URL, PROJECT_DB_URL


def get_admin_engine() -> Engine:
    """Создаёт подключение к административной БД, через которую можно выполнить CREATE DATABASE."""
    return create_engine(ADMIN_DB_URL, isolation_level="AUTOCOMMIT")


def get_project_engine() -> Engine:
    """Создаёт подключение к основной БД проекта stock_olap."""
    return create_engine(PROJECT_DB_URL)


def run_sql_file(engine: Engine, sql_path: str | Path) -> None:
    """Читает SQL-файл целиком и выполняет его в одной транзакции."""
    path = Path(sql_path)
    sql = path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(sql))


def execute_sql(engine: Engine, sql: str, params: dict | None = None) -> None:
    """Выполняет один SQL-запрос с необязательными параметрами."""
    with engine.begin() as conn:
        conn.execute(text(sql), params or {})


def read_sql(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    """Выполняет SELECT-запрос и возвращает результат как pandas DataFrame."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def write_df(engine: Engine, df: pd.DataFrame, schema: str, table: str, chunksize: int = 5000) -> None:
    """Добавляет DataFrame в указанную таблицу PostgreSQL."""
    if df.empty:
        return
    df.to_sql(
        name=table,
        con=engine,
        schema=schema,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=chunksize,
    )
