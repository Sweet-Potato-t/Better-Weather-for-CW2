"""Open-Meteo provider — free, no API key required."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import wmo_icon, wmo_info
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int
from .base import WeatherProvider


class OpenMeteoProvider(WeatherProvider):
    id = "open-meteo"
    name = "Open-Meteo"
    needs_key = False
    supports_alerts = False
    description = "免费、无需 API Key，全球覆盖；数据来自 Open-Meteo。"

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        payload = self._get_json(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": f"{location.latitude:.4f}",
                "longitude": f"{location.longitude:.4f}",
                "current": (
                    "temperature_2m,relative_humidity_2m,apparent_temperature,"
                    "is_day,precipitation,weather_code,cloud_cover,pressure_msl,"
                    "wind_speed_10m,wind_direction_10m,wind_gusts_10m"
                ),
                "daily": (
                    "weather_code,temperature_2m_max,temperature_2m_min,"
                    "sunrise,sunset,precipitation_sum,precipitation_probability_max,"
                    "wind_speed_10m_max"
                ),
                "hourly": (
                    "temperature_2m,weather_code,is_day,precipitation_probability"
                ),
                "timezone": "auto",
                "forecast_days": 4,
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
            },
        )
        current = (payload or {}).get("current") or {}
        daily = (payload or {}).get("daily") or {}
        temp = as_float(current.get("temperature_2m"))
        if temp is None:
            raise ProviderError("Open-Meteo 未返回当前温度")

        code = current.get("weather_code")
        is_day = bool(as_int(current.get("is_day"), 1))
        icon, text = wmo_info(code)
        icon = wmo_icon(code, is_day)

        dates: List[str] = list(daily.get("time") or [])
        highs = list(daily.get("temperature_2m_max") or [])
        lows = list(daily.get("temperature_2m_min") or [])
        codes = list(daily.get("weather_code") or [])
        sunrises = list(daily.get("sunrise") or [])
        sunsets = list(daily.get("sunset") or [])
        forecasts: List[DailyForecast] = []
        for index, date_text in enumerate(dates[:4]):
            day_code = codes[index] if index < len(codes) else code
            day_icon = wmo_icon(day_code, True)
            _, day_text = wmo_info(day_code)
            forecasts.append(
                DailyForecast(
                    date=str(date_text),
                    high_c=as_float(highs[index]) if index < len(highs) else None,
                    low_c=as_float(lows[index]) if index < len(lows) else None,
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        hourly = _parse_hourly((payload or {}).get("hourly") or {}, str(current.get("time") or ""))
        high = forecasts[0].high_c if forecasts else None
        low = forecasts[0].low_c if forecasts else None
        timezone = str((payload or {}).get("timezone") or "")
        if timezone:
            location.timezone = timezone

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=str(code if code is not None else ""),
            feels_like_c=as_float(current.get("apparent_temperature")),
            is_day=is_day,
            high_c=high,
            low_c=low,
            humidity=as_int(current.get("relative_humidity_2m")),
            wind_dir=_wind_direction(as_float(current.get("wind_direction_10m"))),
            wind_scale="",
            wind_speed_kmh=as_float(current.get("wind_speed_10m")),
            pressure_hpa=as_float(current.get("pressure_msl")),
            visibility_km=None,
            obs_time=str(current.get("time") or ""),
            sunrise=str(sunrises[0]) if sunrises else "",
            sunset=str(sunsets[0]) if sunsets else "",
            daily=forecasts,
            hourly=hourly,
            alerts=[],
        )


def _wind_direction(degrees: float | None) -> str:
    if degrees is None:
        return ""
    labels = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    index = int((degrees % 360) / 45.0 + 0.5) % 8
    return labels[index]


def _parse_hourly(hourly: Dict[str, Any], current_time: str) -> List[HourlyForecast]:
    times = list(hourly.get("time") or [])
    temps = list(hourly.get("temperature_2m") or [])
    codes = list(hourly.get("weather_code") or [])
    days = list(hourly.get("is_day") or [])
    pops = list(hourly.get("precipitation_probability") or [])
    result: List[HourlyForecast] = []
    for index, stamp in enumerate(times):
        if current_time and str(stamp) < current_time:
            continue
        if index >= len(temps):
            break
        code = codes[index] if index < len(codes) else None
        is_day = bool(as_int(days[index] if index < len(days) else 1, 1))
        hourly_icon = wmo_icon(code, is_day)
        _, hourly_text = wmo_info(code)
        result.append(
            HourlyForecast(
                time=str(stamp),
                temp_c=as_float(temps[index]),
                icon=hourly_icon,
                text=hourly_text,
                pop=as_int(pops[index]) if index < len(pops) else None,
            )
        )
        if len(result) >= 4:
            break
    return result
