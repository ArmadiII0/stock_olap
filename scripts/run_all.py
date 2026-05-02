from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCRIPTS = [
    "00_create_database.py",
    "01_init_database.py",
    "02_load_staging_prices.py",
    "03_build_core_market.py",
    "04_build_portfolio.py",
    "05_build_marts.py",
    "06_check_dataset_volume.py",
    "07_make_charts.py",
]


def main() -> None:
    for script in SCRIPTS:
        script_path = PROJECT_ROOT / "scripts" / script
        print()
        print("=" * 80)
        print(f"RUNNING: {script}")
        print("=" * 80)

        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            raise SystemExit(f"Script failed: {script}")


if __name__ == "__main__":
    main()
