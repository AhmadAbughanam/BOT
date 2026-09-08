from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from bot.main import app
from bot.storage.db import get_session


def _fake_session():
    yield MagicMock()


app.dependency_overrides[get_session] = _fake_session


def test_health_ok() -> None:
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] is True


def test_root_reports_name_and_version() -> None:
    from bot import __version__

    resp = TestClient(app).get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "BOT"
    assert body["version"] == __version__
