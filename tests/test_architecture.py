def test_bot_entrypoint_delegates_to_package_app():
    import bot
    import receipt_sorter.app

    assert bot.main is receipt_sorter.app.main


def test_refactored_modules_are_importable():
    import receipt_sorter.classifier
    import receipt_sorter.config
    import receipt_sorter.corrections
    import receipt_sorter.drive
    import receipt_sorter.formatting
    import receipt_sorter.memory
    import receipt_sorter.models
    import receipt_sorter.openai_provider
    import receipt_sorter.processor
    import receipt_sorter.telegram_bot

    assert receipt_sorter.models.DocumentResult


def test_runtime_uses_explicit_once_and_server_modes():
    import receipt_sorter.app

    assert hasattr(receipt_sorter.app, "run_once")
    assert hasattr(receipt_sorter.app, "run_server")
    assert not hasattr(receipt_sorter.app, "run_app")


def test_project_metadata_exposes_console_script():
    import tomllib
    from pathlib import Path

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["readme"] == "README.md"
    assert pyproject["project"]["scripts"]["receipt-sorter"] == ("receipt_sorter.app:main")


def test_openai_sdk_imports_are_isolated_to_provider_module():
    from pathlib import Path

    package_dir = Path("receipt_sorter")
    offenders = []
    for path in package_dir.glob("*.py"):
        if path.name == "openai_provider.py":
            continue
        source = path.read_text(encoding="utf-8")
        if "from agents" in source or "import agents" in source or "from openai" in source:
            offenders.append(str(path))

    assert offenders == []
    assert (package_dir / "openai_provider.py").exists()
