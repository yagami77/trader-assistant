from app.config import get_settings
from app.providers.market_data_provider import MarketDataProvider
from app.providers.mock import MockDataProvider
from app.providers.remote_mt5_provider import RemoteMT5Provider


def get_provider() -> MarketDataProvider:
    settings = get_settings()
    if settings.market_provider == "mock":
        return MockDataProvider()
    if settings.market_provider == "remote_mt5":
        return RemoteMT5Provider()
    raise NotImplementedError("MARKET_PROVIDER non supporté")
