from __future__ import annotations

from datetime import date

from receipt_sorter.config import parse_config
from receipt_sorter.drive import drive_service, ensure_child_folder


def years_to_create(current_year: int) -> list[str]:
    return [str(current_year), str(current_year - 1)]


def ensure_base_folders(service, accounting_folder_id: str, current_year: int) -> None:
    for year in years_to_create(current_year):
        ensure_child_folder(service, accounting_folder_id, year)
        print(f"Ensured {year}/")


def main() -> None:
    config = parse_config()
    service = drive_service()
    ensure_base_folders(service, config.accounting_folder_id, date.today().year)


if __name__ == "__main__":
    main()
