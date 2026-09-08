from __future__ import annotations

import logging
from dataclasses import dataclass

import bot.logging_setup as logging_setup


@dataclass
class _Stub:
    log_level: str = "warning"
    log_file: str = ""


def test_configure_logging_adds_file_handler_when_log_file_set(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "bot.log"
    monkeypatch.setattr(logging_setup, "get_settings", lambda: _Stub(log_file=str(log_path)))
    try:
        logging_setup.configure_logging()
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        assert any(h.baseFilename == str(log_path) for h in file_handlers)
        assert root.level == logging.WARNING

        logging.getLogger("test").warning("hello file")
        for h in file_handlers:
            h.flush()
        assert "hello file" in log_path.read_text(encoding="utf-8")
    finally:
        monkeypatch.undo()
        logging_setup.configure_logging()  # restore real config for other tests


def test_configure_logging_stream_only_by_default(monkeypatch) -> None:
    monkeypatch.setattr(logging_setup, "get_settings", lambda: _Stub())
    try:
        logging_setup.configure_logging()
        root = logging.getLogger()
        assert not any(isinstance(h, logging.FileHandler) for h in root.handlers)
    finally:
        monkeypatch.undo()
        logging_setup.configure_logging()
