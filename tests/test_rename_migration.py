import sqlite3

from neuropace.config import Settings, load_settings


def test_legacy_environment_variables_still_load(monkeypatch, tmp_path):
    monkeypatch.setenv("REFLOW_DATA_DIR", str(tmp_path / "old-data"))
    monkeypatch.setenv("REFLOW_PORT", "9001")
    monkeypatch.setenv("REFLOW_HEADSET_PORT", "sim")
    monkeypatch.setenv("REFLOW_LLM_PROVIDER", "openrouter")
    settings = load_settings(tmp_path / "missing.env")
    assert settings.data_dir == tmp_path / "old-data"
    assert settings.port == 9001
    assert settings.headset_port == "sim"
    assert settings.llm_provider == "openrouter"


def test_neuropace_environment_variables_override_legacy(monkeypatch, tmp_path):
    monkeypatch.setenv("REFLOW_PORT", "9001")
    monkeypatch.setenv("NEUROPACE_PORT", "9002")
    assert load_settings(tmp_path / "missing.env").port == 9002


def test_legacy_database_is_copied_to_neuropace_name(tmp_path):
    legacy = tmp_path / "reflow.db"
    with sqlite3.connect(legacy) as db:
        db.execute("create table marker (value text)")
        db.execute("insert into marker values ('preserved')")

    settings = Settings(data_dir=tmp_path)
    settings.ensure_dirs()

    assert settings.db_path.name == "neuropace.db"
    assert legacy.exists()
    with sqlite3.connect(settings.db_path) as db:
        assert db.execute("select value from marker").fetchone() == ("preserved",)


def test_legacy_python_import_resolves_to_renamed_package():
    from reflow.config import Settings as LegacySettings

    assert LegacySettings().db_path.name == "neuropace.db"
