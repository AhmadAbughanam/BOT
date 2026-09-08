from __future__ import annotations

from bot.scraping.extractors import (
    ScrapedResult,
    absolutize,
    clean_title,
    dedup_by_url,
    is_http_url,
)


def test_clean_title_collapses_whitespace() -> None:
    assert clean_title("  hello\n  world \t") == "hello world"


def test_absolutize_and_is_http_url() -> None:
    assert absolutize("https://x.example/news", "/a/b") == "https://x.example/a/b"
    assert is_http_url("https://x.example/a")
    assert not is_http_url("mailto:a@b.com")
    assert not is_http_url("/relative/only")


def _r(url: str) -> ScrapedResult:
    return ScrapedResult(title="t", url=url, source_id="s", category="tech", subcategory="ai")


def test_dedup_by_url_ignores_trailing_slash_and_keeps_first() -> None:
    results = [_r("https://x.example/a"), _r("https://x.example/a/"), _r("https://x.example/b")]
    kept = dedup_by_url(results)
    assert [r.url for r in kept] == ["https://x.example/a", "https://x.example/b"]
