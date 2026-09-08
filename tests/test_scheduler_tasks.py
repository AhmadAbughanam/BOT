from __future__ import annotations

import pytest

from bot.scheduler.crontab import crontab_lines
from bot.scheduler.tasks import TaskDeps, run_task
from bot.storage.models import Brief, Item


class FakeEmail:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def digest(self, instruction, session) -> str:
        self.calls.append(instruction)
        return "EMAIL DIGEST"


class FakeScraping:
    def __init__(self, items) -> None:
        self._items = items
        self.calls: list[str] = []

    async def collect(self, query, session, **kwargs):
        self.calls.append(query)
        return self._items


class FakeConnector:
    def __init__(self, text: str) -> None:
        self._text = text
        self.params: dict | None = None

    async def fetch(self, params) -> str:
        self.params = params
        return self._text


class FakeChain:
    async def chat(self, messages, *, temperature=0.7, max_tokens=None):
        from bot.llm.base import ChatResult

        last = messages[-1].content
        text = '{"score": 0.95, "critique": "ok"}' if "Score the draft" in last else "BRIEF TEXT"
        return ChatResult(text=text, provider="fake", model="fake")


class FakeSession:
    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def execute(self, _stmt):
        class _R(list):
            def scalars(self):
                return self

        return _R()


def _deps(*, email=None, scraping=None, connector_text="CONNECTOR OUT") -> TaskDeps:
    return TaskDeps(
        chain=FakeChain(),
        email=email or FakeEmail(),
        scraping=scraping or FakeScraping([]),
        connector=lambda name: FakeConnector(connector_text),
        telegram=None,
    )


async def test_email_task_dispatches_to_email_service(monkeypatch) -> None:
    monkeypatch.setattr(
        "bot.scheduler.tasks.load_task",
        lambda name: {"name": name, "source": "email", "params": {"filter": "skip newsletters"}},
    )
    email = FakeEmail()
    session = FakeSession()

    result = await run_task("email-digest", session, deps=_deps(email=email), deliver=False)

    assert result.content == "EMAIL DIGEST"
    assert email.calls == ["skip newsletters"]
    assert any(isinstance(o, Brief) for o in session.added)


async def test_scraping_task_runs_brief_over_collected_items(monkeypatch) -> None:
    monkeypatch.setattr(
        "bot.scheduler.tasks.load_task",
        lambda name: {"name": name, "source": "scraping", "params": {"subcategories": ["ai", "world"]}},
    )
    scraping = FakeScraping([Item(title="A headline", url="https://x/1")])

    result = await run_task("morning-news", FakeSession(), deps=_deps(scraping=scraping), deliver=False)

    assert result.content == "BRIEF TEXT"
    assert scraping.calls == ["ai, world"]


async def test_connector_task_calls_named_connector(monkeypatch) -> None:
    monkeypatch.setattr(
        "bot.scheduler.tasks.load_task",
        lambda name: {"name": name, "source": "connector", "connector": "weather", "params": {"location": "Amman"}},
    )
    result = await run_task("weather-agenda", FakeSession(), deps=_deps(connector_text="Weather for Amman"), deliver=False)
    assert result.content == "Weather for Amman"


async def test_unknown_source_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        "bot.scheduler.tasks.load_task",
        lambda name: {"name": name, "source": "carrier-pigeon", "params": {}},
    )
    with pytest.raises(ValueError):
        await run_task("bogus", FakeSession(), deps=_deps(), deliver=False)


def test_crontab_lines_from_example_config() -> None:
    lines = crontab_lines(python="/usr/bin/python3", workdir="/srv/bot")
    assert any(
        line.startswith("0 7 * * * cd /srv/bot && /usr/bin/python3 -m bot.scheduler run email-digest")
        for line in lines
    )
    assert any("30 7 * * *" in line and "morning-news" in line for line in lines)
