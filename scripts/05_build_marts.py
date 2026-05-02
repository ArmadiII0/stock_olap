"""Создаёт материализованные витрины для анализа и графиков."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import get_project_engine
from src.logger import log
from src.mart_builder import build_marts


def main() -> None:
    log("Построение OLAP-витрин")
    engine = get_project_engine()
    build_marts(engine)
    log("OLAP-витрины построены")


if __name__ == "__main__":
    main()
