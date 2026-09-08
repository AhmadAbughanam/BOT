from __future__ import annotations

from bot.scraping.extractors import ScrapedResult
from bot.scraping.registry import SearchConfig, Site
from bot.scraping.service import ScrapingService


def _site(sid: str, category: str, subcategory: str) -> Site:
    return Site(
        id=sid,
        name=sid,
        base_url=f"https://{sid}.example",
        category=category,
        subcategory=subcategory,
        search=SearchConfig(mode="url_template", result_selector="a", url_template="https://x/{query}"),
    )


class FakeRunner:
    def __init__(self, by_site: dict[str, list[ScrapedResult]]) -> None:
        self._by_site = by_site
        self.searched: list[str] = []

    async def search(self, site, query, limit):
        self.searched.append(site.id)
        return self._by_site.get(site.id, [])


class FakeScalars(list):
    def scalars(self):
        return self


class FakeSession:
    def __init__(self, known_urls: set[str] | None = None) -> None:
        self.added: list = []
        self._known = known_urls or set()

    def add(self, obj) -> None:
        self.added.append(obj)

    def execute(self, _stmt):
        return FakeScalars(self._known)


def _result(sid: str, url: str) -> ScrapedResult:
    return ScrapedResult(title=f"t-{url}", url=url, source_id=sid, category="tech", subcategory="ai")


async def test_collect_dedupes_and_persists_only_new_items() -> None:
    sites = [_site("a", "tech", "ai"), _site("b", "tech", "ai")]
    runner = FakeRunner(
        {
            "a": [_result("a", "https://x.example/1"), _result("a", "https://x.example/2")],
            "b": [_result("b", "https://x.example/2/"), _result("b", "https://x.example/3")],
        }
    )
    session = FakeSession(known_urls={"https://x.example/3"})
    service = ScrapingService(runner=runner, sites=sites)

    new_items = await service.collect("q", session, categories=["tech"])

    urls = [i.url for i in new_items]
    assert urls == ["https://x.example/1", "https://x.example/2"]  # /2/ deduped, /3 already known
    assert all(i.category == "tech" and i.subcategory == "ai" for i in new_items)
    assert runner.searched == ["a", "b"]


async def test_collect_returns_empty_when_no_sites_match() -> None:
    service = ScrapingService(runner=FakeRunner({}), sites=[_site("a", "tech", "ai")])
    assert await service.collect("q", FakeSession(), categories=["news"]) == []


async def test_one_failing_site_does_not_abort_the_batch() -> None:
    class Flaky(FakeRunner):
        async def search(self, site, query, limit):
            if site.id == "a":
                raise RuntimeError("boom")
            return await super().search(site, query, limit)

    sites = [_site("a", "tech", "ai"), _site("b", "tech", "ai")]
    runner = Flaky({"b": [_result("b", "https://x.example/9")]})
    new_items = await ScrapingService(runner=runner, sites=sites).collect("q", FakeSession())

    assert [i.url for i in new_items] == ["https://x.example/9"]
