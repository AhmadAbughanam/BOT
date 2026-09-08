from __future__ import annotations

from bot.connectors.base import Connector, ConnectorError
from bot.connectors.feeds import FeedsConnector
from bot.connectors.finance import FinanceConnector
from bot.connectors.weather import WeatherConnector

_REGISTRY: dict[str, type] = {
    "weather": WeatherConnector,
    "finance": FinanceConnector,
    "feeds": FeedsConnector,
}


def get_connector(name: str) -> Connector:
    try:
        return _REGISTRY[name]()
    except KeyError as exc:
        raise ConnectorError(f"unknown connector: {name!r}") from exc


__all__ = [
    "Connector",
    "ConnectorError",
    "FeedsConnector",
    "FinanceConnector",
    "WeatherConnector",
    "get_connector",
]
