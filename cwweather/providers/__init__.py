"""Provider registry.

Order matters for the fallback chain: free, no-key providers come first so a
temporary failure of a keyed provider still leaves the widget usable.
"""

from __future__ import annotations

from typing import Dict, List, Type

from .base import WeatherProvider
from .caiyun import CaiyunProvider
from .met_no import MetNoProvider
from .open_meteo import OpenMeteoProvider
from .openweathermap import OpenWeatherMapProvider
from .qweather import QWeatherProvider
from .weatherapi import WeatherApiProvider
from .wttr import WttrProvider
from .xiaomi import XiaomiProvider

PROVIDER_CLASSES: List[Type[WeatherProvider]] = [
    OpenMeteoProvider,
    XiaomiProvider,
    WttrProvider,
    MetNoProvider,
    QWeatherProvider,
    OpenWeatherMapProvider,
    WeatherApiProvider,
    CaiyunProvider,
]

PROVIDERS: Dict[str, Type[WeatherProvider]] = {
    provider.id: provider for provider in PROVIDER_CLASSES
}

FREE_PROVIDER_IDS = [
    provider.id for provider in PROVIDER_CLASSES if not provider.needs_key
]


_CAPABILITIES = {
    "open-meteo": {"current": True, "tomorrow": True, "hourly": True, "precipitation": True, "alerts": False},
    "xiaomi": {"current": True, "tomorrow": True, "hourly": True, "precipitation": False, "alerts": True},
    "wttr": {"current": True, "tomorrow": True, "hourly": True, "precipitation": True, "alerts": False},
    "met-no": {"current": True, "tomorrow": True, "hourly": True, "precipitation": False, "alerts": True},
    "qweather": {"current": True, "tomorrow": True, "hourly": True, "precipitation": True, "alerts": True},
    "openweathermap": {"current": True, "tomorrow": True, "hourly": True, "precipitation": True, "alerts": True},
    "weatherapi": {"current": True, "tomorrow": True, "hourly": True, "precipitation": True, "alerts": True},
    "caiyun": {"current": True, "tomorrow": True, "hourly": False, "precipitation": False, "alerts": True},
}


def provider_catalog() -> List[Dict[str, object]]:
    result = []
    for provider in PROVIDER_CLASSES:
        caps = _CAPABILITIES.get(provider.id, {})
        result.append({
            "id": provider.id,
            "name": provider.name,
            "needs_key": provider.needs_key,
            "supports_current": caps.get("current", True),
            "supports_tomorrow": caps.get("tomorrow", True),
            "supports_hourly": caps.get("hourly", False),
            "supports_precipitation": caps.get("precipitation", False),
            "supports_alerts": provider.supports_alerts,
            "description": provider.description,
            "key_label": _key_label(provider.id),
        })
    return result


def _key_label(provider_id: str) -> str:
    return {
        "qweather": "和风天气 API Key",
        "openweathermap": "OpenWeatherMap API Key",
        "weatherapi": "WeatherAPI Key",
        "caiyun": "彩云天气 Token",
    }.get(provider_id, "")


__all__ = [
    "PROVIDER_CLASSES",
    "PROVIDERS",
    "FREE_PROVIDER_IDS",
    "provider_catalog",
    "WeatherProvider",
]
