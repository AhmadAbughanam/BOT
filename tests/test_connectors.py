from __future__ import annotations

import pytest

from bot.connectors import ConnectorError, get_connector
from bot.connectors.feeds import FeedsConnector
from bot.connectors.finance import FinanceConnector
from bot.connectors.weather import WeatherConnector


class FakeResp:
    def __init__(self, *, json_data=None, text: str = "") -> None:
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self) -> None:
        return None


def make_get(routes: dict[str, FakeResp]):
    async def _get(url, *, params=None, headers=None):
        for fragment, resp in routes.items():
            if fragment in url:
                return resp
        raise AssertionError(f"unexpected URL {url}")

    return _get


# --- weather -------------------------------------------------------------------

async def test_weather_geocodes_then_formats_forecast() -> None:
    get = make_get(
        {
            "geocoding-api": FakeResp(
                json_data={"results": [{"name": "Amman", "country_code": "JO", "latitude": 31.9, "longitude": 35.9}]}
            ),
            "api.open-meteo.com": FakeResp(
                json_data={
                    "daily": {
                        "temperature_2m_max": [33],
                        "temperature_2m_min": [19],
                        "precipitation_probability_max": [0],
                        "weather_code": [0],
                    }
                }
            ),
        }
    )
    out = await WeatherConnector(get=get).fetch({"location": "Amman"})
    assert "Amman, JO" in out
    assert "clear" in out
    assert "high 33" in out


async def test_weather_without_location_errors() -> None:
    with pytest.raises(ConnectorError):
        await WeatherConnector(get=make_get({})).fetch({})


# --- finance -----------------------------------------------------------------

async def test_finance_equity_and_crypto() -> None:
    get = make_get(
        {
            "stooq.com": FakeResp(text="Symbol,Date,Time,Open,High,Low,Close,Volume\nAAPL,2026-09-08,22:00:00,100,110,99,105,1000"),
            "coingecko.com": FakeResp(json_data={"bitcoin": {"usd": 60000, "usd_24h_change": 2.5}}),
        }
    )
    out = await FinanceConnector(get=get).fetch({"symbols": ["AAPL", "BTC-USD"]})
    assert "AAPL 105 (+5.00% vs open)" in out
    assert "BTC-USD 60000 (+2.50%/24h)" in out


async def test_finance_reports_missing_data_per_symbol() -> None:
    get = make_get({"stooq.com": FakeResp(text="Symbol,Date,Time,Open,High,Low,Close,Volume\nZZZZ,N/D,N/D,N/D,N/D,N/D,N/D,N/D")})
    out = await FinanceConnector(get=get).fetch({"symbols": ["ZZZZ"]})
    assert "ZZZZ: no data" in out


# --- feeds ------------------------------------------------------------------

_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><title>First post</title><link>https://x.example/1</link></item>
  <item><title>Second post</title><link>https://x.example/2</link></item>
</channel></rss>"""


async def test_feeds_lists_entries() -> None:
    get = make_get({"x.example/feed": FakeResp(text=_RSS)})
    out = await FeedsConnector(get=get).fetch({"feeds": ["https://x.example/feed"], "max_items": 5})
    assert "- First post (https://x.example/1)" in out
    assert "- Second post (https://x.example/2)" in out


async def test_feeds_without_config() -> None:
    out = await FeedsConnector(get=make_get({})).fetch({"feeds": []})
    assert out == "No feeds configured."


def test_get_connector_unknown() -> None:
    with pytest.raises(ConnectorError):
        get_connector("nope")
