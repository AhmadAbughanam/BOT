from __future__ import annotations

from bot.core.formatting import for_instagram, for_telegram


def test_for_telegram_passes_short_text_through() -> None:
    assert for_telegram("  hello  ") == "hello"


def test_for_telegram_trims_to_limit_with_ellipsis() -> None:
    out = for_telegram("x" * 5000)
    assert len(out) == 4096
    assert out.endswith("…")


def test_for_instagram_trims_to_1000() -> None:
    out = for_instagram("y" * 2000)
    assert len(out) == 1000
    assert out.endswith("…")
