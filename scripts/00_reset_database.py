from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import SQL_DIR
from src.db import get_project_engine, run_sql_file
from src.logger import log


def main() -> None:
    log("Очистка таблиц и удаление materialized views")
    engine = get_project_engine()
    run_sql_file(engine, SQL_DIR / "99_reset_all.sql")
    log("Очистка завершена")


if __name__ == "__main__":
    main()
