"""Plugin configuration model.

Class Widgets 2 injects the real ``ConfigBaseModel`` at runtime.  The fallback
below is only a convenience for static checks and standalone unit tests.
"""

from __future__ import annotations

try:
    from ClassWidgets.SDK import ConfigBaseModel  # type: ignore
except Exception:  # pragma: no cover - only when running outside CW2

    class ConfigBaseModel:  # type: ignore[no-redef]
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        def model_dump(self):
            return dict(self.__dict__)


class WeatherConfig(ConfigBaseModel):
    # Data source / refresh
    source: str = "open-meteo"
    refresh_interval: int = 15          # minutes
    cycle_interval: int = 3             # seconds, warning rotation
    animation_enabled: bool = True
    fallback_enabled: bool = True
    timeout: int = 12                   # seconds per HTTP request
    temperature_unit: str = "celsius"   # celsius | fahrenheit

    # Location
    auto_location: bool = True
    location_strategy: str = "auto"     # auto | ip | device
    manual_city: str = "北京市"
    manual_lat: float = 39.9042
    manual_lon: float = 116.4074
    manual_region: str = "北京市"
    manual_country: str = "中国"
    manual_timezone: str = "Asia/Shanghai"

    # Widget presentation
    show_location: bool = True
    show_provider: bool = False
    widget_content_mode: str = "current"   # current | high_low
    widget_show_hourly: bool = True
    widget_show_precip: bool = True
    widget_carousel: bool = True
    widget_main_seconds: int = 8

    # Keys for providers that need one
    qweather_api_key: str = ""
    qweather_host: str = ""
    openweathermap_api_key: str = ""
    weatherapi_api_key: str = ""
    caiyun_api_key: str = ""

    def as_dict(self) -> dict:
        try:
            return self.model_dump()
        except Exception:
            return dict(self.__dict__)
