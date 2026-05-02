from __future__ import annotations

from config.settings import SQL_DIR
from src.db import run_sql_file
from src.logger import log


def build_marts(engine) -> None:
    log("Создание materialized views в mart")
    run_sql_file(engine, SQL_DIR / "04_create_marts.sql")
