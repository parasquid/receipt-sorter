import setup_drive
from setup_drive import ensure_base_folders, years_to_create


def test_years_to_create_includes_current_and_previous_year():
    assert years_to_create(2026) == ["2026", "2025"]


def test_ensure_base_folders_creates_years_only(monkeypatch):
    calls = []

    def fake_ensure_child_folder(service, parent_id, name):
        calls.append((service, parent_id, name))
        return f"{name}-id"

    monkeypatch.setattr(setup_drive, "ensure_child_folder", fake_ensure_child_folder)

    ensure_base_folders(
        service="drive-service",
        accounting_folder_id="accounting-id",
        current_year=2026,
    )

    assert calls == [
        ("drive-service", "accounting-id", "2026"),
        ("drive-service", "accounting-id", "2025"),
    ]
