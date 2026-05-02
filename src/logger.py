"""Простой логгер для учебного проекта.

Печатает сообщение с текущим временем, чтобы в консоли было видно, какой этап выполняется."""

from __future__ import annotations

from datetime import datetime


def log(message: str) -> None:
    """Выводит сообщение с timestamp. flush=True нужен, чтобы логи сразу появлялись в терминале."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)
