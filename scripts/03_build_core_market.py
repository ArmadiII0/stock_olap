from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core_builder import build_and_load_core_market
from src.db import get_project_engine
from src.logger import log


def main() -> None:
    log("Построение CORE-слоя рынка")
    engine = get_project_engine()
    build_and_load_core_market(engine)
    log("CORE-слой рынка построен")


if __name__ == "__main__":
    main()
