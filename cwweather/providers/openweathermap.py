"""OpenWeatherMap One Call 3.0 provider (API key required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import owm_icon
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class OpenWeatherMapProvider(WeatherProvider):
    id = "openweathermap"
    name = "OpenWeatherMap"
    needs_key = True
    supports_alerts = True
    description = "OpenWeatherMap One Call 3.0，使用 appid；预警覆盖部分国家和地区。"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "openweathermap_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "openweathermap_api_key")
        payload = self._get_json(
            "https://api.openweathermap.org/data/3.0/onecall",
            {
                "lat": f"{location.latitude:.4f}",
                "lon": f"{location.longitude:.4f}",
                "appid": key,
                "units": "metric",
                "lang": "zh_cn",
                "exclude": "minutely",
            },
        )
        current = (payload or {}).get("current") or {}
        temp = as_float(current.get("temp"))
        if temp is None:
            raise ProviderError("OpenWeatherMap 未返回当前温度（One Call 3.0 可能需要订阅）")

        weather = first(current.get("weather")) or {}
        is_day = _is_day(current.get("sunrise"), current.get("sunset"), current.get("dt"))
        icon, text = owm_icon(
            weather.get("id"), str(weather.get("description") or ""), is_day
        )
        daily_raw = (payload or {}).get("daily") or []
        daily: List[DailyForecast] = []
        for index, item in enumerate(daily_raw[:4]):
            if not isinstance(item, dict):
                continue
            day_weather = first(item.get("weather")) or {}
            day_icon, day_text = owm_icon(
                day_weather.get("id"), str(day_weather.get("description") or ""), True
            )
            temp_info = item.get("temp") or {}
            daily.append(
                DailyForecast(
                    date=_date(item.get("dt")),
                    high_c=as_float(temp_info.get("max")),
                    low_c=as_float(temp_info.get("min")),
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        hourly = self._hourly((payload or {}).get("hourly") or [])
        alerts = self._alerts((payload or {}).get("alerts") or [], self.id)
        first_day = first(daily_raw) or {}
        temp_info = first_day.get("temp") or {}
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=str(weather.get("id") or ""),
            feels_like_c=as_float(current.get("feels_like")),
            is_day=is_day,
            high_c=as_float(temp_info.get("max")),
            low_c=as_float(temp_info.get("min")),
            humidity=as_int(current.get("humidity")),
            wind_dir=_wind_direction(as_float(current.get("wind_deg"))),
            wind_scale=_wind_scale(as_float(current.get("wind_speed"))),
            wind_speed_kmh=(
                as_float(current.get("wind_speed")) * 3.6
                if as_float(current.get("wind_speed")) is not None
                else None
            ),
            pressure_hpa=as_float(current.get("pressure")),
            visibility_km=(
                as_float(current.get("visibility")) / 1000.0
                if as_float(current.get("visibility")) is not None
                else None
            ),
            obs_time=_iso(current.get("dt")),
            sunrise=_iso(current.get("sunrise")),
            sunset=_iso(current.get("sunset")),
            daily=daily,
            hourly=hourly,
            alerts=alerts,
        )

    def _hourly(self, raw: list) -> List[HourlyForecast]:
        result: List[HourlyForecast] = []
        for item in raw[:4]:
            if not isinstance(item, dict):
                continue
            weather = first(item.get("weather")) or {}
            icon_code = str(weather.get("icon") or "")
            is_day = not icon_code.endswith("n")
            icon, text = owm_icon(
                weather.get("id"), str(weather.get("description") or ""), is_day
            )
            result.append(
                HourlyForecast(
                    time=_iso(item.get("dt")),
                    temp_c=as_float(item.get("temp")),
                    icon=icon,
                    text=text,
                    pop=as_int(as_float(item.get("pop")) * 100) if item.get("pop") is not None else None,
                )
            )
        return result

    def _alerts(self, raw: list, source: str) -> list:
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("id"),
                    "title": item.get("event"),
                    "type": item.get("event"),
                    "level": "",
                    "severity": (item.get("tags") or [""])[0] if item.get("tags") else "",
                    "description": item.get("description"),
                    "sender": item.get("sender_name"),
                    "pub_time": _iso(item.get("start")),
                    "start_time": _iso(item.get("start")),
                    "end_time": _iso(item.get("end")),
                    "urgency": "",
                    "certainty": "",
                }
            )
        from ..models import normalize_alerts

        return normalize_alerts(normalized, source)


def _date(value: Any) -> str:
    from ..util import parse_datetime

    parsed = parse_datetime(value)
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def _iso(value: Any) -> str:
    from ..util import parse_datetime

    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else ""


def _is_day(sunrise: Any, sunset: Any, now: Any) -> bool:
    from ..util import parse_datetime

    rise = parse_datetime(sunrise)
    setting = parse_datetime(sunset)
    current = parse_datetime(now)
    if not rise or not setting or not current:
        return True
    return rise <= current <= setting


def _wind_direction(degrees: float | None) -> str:
    if degrees is None:
        return ""
    labels = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    return labels[int((degrees % 360) / 45.0 + 0.5) % 8]


def _wind_scale(speed_ms: float | None) -> str:
    if speed_ms is None:
        return ""
    kmh = speed_ms * 3.6
    if kmh < 1:
        return "0级"
    if kmh < 6:
        return "1级"
    if kmh < 12:
        return "2级"
    if kmh < 20:
        return "3级"
    if kmh < 29:
        return "4级"
    if kmh < 39:
        return "5级"
    if kmh < 50:
        return "6级"
    if kmh < 62:
        return "7级"
    return "8级"
