from __future__ import annotations

from pathlib import Path

import pytest

from neuropace.api.app import create_app, ensure_demo_lecture
from neuropace.config import Settings
from neuropace.llm.client import LLMClient
from neuropace.store.db import DB


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    s = Settings(
        data_dir=tmp_path / "data",
        baseline_seconds=20,
        recap_period_seconds=5,
        headset_port="sim",
        totem_port="keyboard",
        allow_offline_llm=True,  # the extractive generator is for tests; the product requires OpenAI
    )
    s.ensure_dirs()
    return s


@pytest.fixture
def db(settings: Settings) -> DB:
    d = DB(settings.db_path)
    ensure_demo_lecture(d)
    yield d
    d.close()


@pytest.fixture
def llm(settings: Settings, db: DB) -> LLMClient:
    return LLMClient(settings, db)  # no key: offline fallback


@pytest.fixture
def app(settings: Settings, db: DB, llm: LLMClient):
    return create_app(settings, db, llm)
