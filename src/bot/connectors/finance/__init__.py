from __future__ import annotations

from typing import Any

from bot.connectors.base import ConnectorError, HttpGet, default_get

_STOOQ_URL = "https://stooq.com/q/l/"
_COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

_COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
}


class FinanceConnector:
    """Keyless quotes: equities via Stooq CSV, crypto via CoinGecko."""

    name = "finance"

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or default_get

    async def fetch(self, params: dict[str, Any]) -> str:
        symbols = params.get("symbols") or params.get("watchlist") or []
        if not symbols:
            return "No symbols configured."

        lines: list[str] = []
        for symbol in symbols:
            try:
                if _is_crypto(symbol):
                    lines.append(await self._crypto(symbol))
                else:
                    lines.append(await self._equity(symbol))
            except ConnectorError as exc:
                lines.append(f"{symbol}: {exc}")
        return "Markets:\n" + "\n".join(lines)

    async def _equity(self, symbol: str) -> str:
        resp = await self._get(
            _STOOQ_URL,
            params={"s": symbol.lower(), "f": "sd2t2ohlcv", "h": "", "e": "csv"},
        )
        resp.raise_for_status()
        rows = resp.text.strip().splitlines()
        if len(rows) < 2:
            raise ConnectorError("no data")
        # Symbol,Date,Time,Open,High,Low,Close,Volume
        cells = rows[-1].split(",")
        if len(cells) < 7 or cells[6] in ("N/D", ""):
            raise ConnectorError("no data")
        open_px, close_px = cells[3], cells[6]
        move = _pct(open_px, close_px)
        return f"{symbol.upper()} {close_px} ({move} vs open)"

    async def _crypto(self, symbol: str) -> str:
        base = symbol.split("-")[0].upper()
        coin_id = _COINGECKO_IDS.get(base, base.lower())
        resp = await self._get(
            _COINGECKO_URL,
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
        )
        resp.raise_for_status()
        data = resp.json().get(coin_id)
        if not data:
            raise ConnectorError("no data")
        price = data.get("usd")
        change = data.get("usd_24h_change")
        change_str = f"{change:+.2f}%/24h" if isinstance(change, (int, float)) else "?"
        return f"{base}-USD {price} ({change_str})"


def _is_crypto(symbol: str) -> bool:
    s = symbol.upper()
    return s.endswith("-USD") or s.split("-")[0] in _COINGECKO_IDS


def _pct(a: str, b: str) -> str:
    try:
        fa, fb = float(a), float(b)
        return f"{(fb - fa) / fa * 100:+.2f}%" if fa else "?"
    except ValueError:
        return "?"
