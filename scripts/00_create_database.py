"""Создаёт рабочую базу PostgreSQL, если она ещё не создана."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from config.settings import POSTGRES_DB
from src.db import get_admin_engine
from src.logger import log


def main() -> None:
    log(f"Проверка существования базы данных: {POSTGRES_DB}")
    engine = get_admin_engine()

    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
            {"db_name": POSTGRES_DB},
        ).scalar()

        if exists:
            log(f"База данных {POSTGRES_DB} уже существует")
        else:
            # Имя БД берётся из .env. Для учебного проекта ожидается простое имя stock_olap.
            conn.execute(text(f'CREATE DATABASE "{POSTGRES_DB}"'))
            log(f"База данных {POSTGRES_DB} создана")


if __name__ == "__main__":
    main()
