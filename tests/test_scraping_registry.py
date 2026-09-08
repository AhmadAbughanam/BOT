from __future__ import annotations

import textwrap

from bot.scraping.registry import load_sites, sites_for


def test_loads_the_example_registry() -> None:
    sites = load_sites("config/sites.example.yaml")
    ids = {s.id for s in sites}
    assert {"reuters", "hn", "techcrunch"} <= ids

    hn = next(s for s in sites if s.id == "hn")
    assert hn.search.mode == "url_template"
    assert hn.search.url_template and "{query}" in hn.search.url_template

    reuters = next(s for s in sites if s.id == "reuters")
    assert reuters.search.mode == "search_bar"
    assert reuters.search.input_selector


def test_sites_for_filters_by_category_and_subcategory() -> None:
    sites = load_sites("config/sites.example.yaml")
    tech = sites_for(sites, categories=["tech"])
    assert tech and all(s.category == "tech" for s in tech)

    startups = sites_for(sites, categories=["tech"], subcategories=["startups"])
    assert {s.id for s in startups} == {"techcrunch"}


def test_invalid_entries_are_skipped(tmp_path) -> None:
    path = tmp_path / "sites.yaml"
    path.write_text(
        textwrap.dedent(
            """
            sites:
              - id: ok
                name: OK
                base_url: https://ok.example
                category: tech
                subcategory: ai
                search:
                  mode: url_template
                  url_template: "https://ok.example/s?q={query}"
                  result_selector: "a.r"
              - id: broken
                name: Broken
                base_url: https://broken.example
                category: tech
                subcategory: ai
                search:
                  mode: search_bar
                  result_selector: "a.r"
            """
        ),
        encoding="utf-8",
    )
    sites = load_sites(path)
    assert [s.id for s in sites] == ["ok"]
