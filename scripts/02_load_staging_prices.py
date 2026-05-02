"""Загружает котировки из yfinance в staging-слой и фиксирует статус загрузки в meta.load_log."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text

from config.settings import END_DATE, START_DATE, TICKERS, YFINANCE_CHUNK_SIZE
from src.db import get_project_engine, write_df
from src.logger import log
from src.yfinance_loader import download_prices


def main() -> None:
    engine = get_project_engine()
    # batch_id связывает строки котировок и запись в meta.load_log в одну загрузочную сессию.
    batch_id = datetime.now().strftime("%Y%m%d%H%M%S")

    try:
        # Сначала помечаем загрузку как RUNNING, потом обновляем статус на SUCCESS или FAILED.
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO meta.load_log (
                    batch_id, source_system, target_table, load_started_at, status
                )
                VALUES (:batch_id, 'yfinance', 'staging.stg_yf_prices', CURRENT_TIMESTAMP, 'RUNNING')
            """), {"batch_id": batch_id})

        prices = download_prices(
            tickers=TICKERS,
            start=START_DATE,
            end=END_DATE,
            chunk_size=YFINANCE_CHUNK_SIZE,
            batch_id=batch_id,
        )

        log(f"Загрузка staging.stg_yf_prices: {len(prices):,} строк")
        write_df(engine, prices, "staging", "stg_yf_prices")

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE meta.load_log
                SET load_finished_at = CURRENT_TIMESTAMP,
                    rows_loaded = :rows_loaded,
                    status = 'SUCCESS',
                    error_message = NULL
                WHERE batch_id = :batch_id
            """), {"batch_id": batch_id, "rows_loaded": len(prices)})

        log(f"Загрузка staging завершена. batch_id={batch_id}")

    except Exception as exc:
        error_message = str(exc)[:2000]
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE meta.load_log
                SET load_finished_at = CURRENT_TIMESTAMP,
                    status = 'FAILED',
                    error_message = :error_message
                WHERE batch_id = :batch_id
            """), {"batch_id": batch_id, "error_message": error_message})
        raise


if __name__ == "__main__":
    main()
