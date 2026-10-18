"""wttr.in provider — free, no API key required."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import wwo_icon, wwo_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class WttrProvider(WeatherProvider):
    id = "wttr"
    name = "wttr.in"
    needs_key = False
    supports_alerts = False
    description = "免费、无需 API Key，基于 World Weather Online；在部分地区可能较慢。"

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        payload = self._get_json(
            f"https://wttr.in/{location.latitude:.4f},{location.longitude:.4f}",
            {"format": "j1", "lang": "zh"},
            headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7"},
        )
        current = first((payload or {}).get("current_condition"))
        if not isinstance(current, dict):
            raise ProviderError("wttr.in 未返回当前天气")
        temp = as_float(current.get("temp_C"))
        if temp is None:
            raise ProviderError("wttr.in 未返回当前温度")

        code = current.get("weatherCode")
        desc = _desc(current)
        is_day = _is_daytime(current.get("observation_time"))
        icon = wwo_icon(code, is_day)
        _, text = wwo_info(code, desc)

        daily_raw = (payload or {}).get("weather") or []
        forecasts: List[DailyForecast] = []
        for index, item in enumerate(daily_raw[:4]):
            if not isinstance(item, dict):
                continue
            day_code = None
            hourly = item.get("hourly") or []
            if hourly:
                noon = hourly[min(4, len(hourly) - 1)]
                day_code = noon.get("weatherCode")
            day_icon = wwo_icon(day_code, True)
            _, day_text = wwo_info(day_code, desc)
            forecasts.append(
                DailyForecast(
                    date=str(item.get("date") or ""),
                    high_c=as_float(item.get("maxtempC")),
                    low_c=as_float(item.get("mintempC")),
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        first_day = first(daily_raw) or {}
        astronomy = first((payload or {}).get("weather")) or {}
        astro = first(astronomy.get("astronomy")) or {}
        high = forecasts[0].high_c if forecasts else as_float(first_day.get("maxtempC"))
        low = forecasts[0].low_c if forecasts else as_float(first_day.get("mintempC"))

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=str(code or ""),
            feels_like_c=as_float(current.get("FeelsLikeC")),
            is_day=is_day,
            high_c=high,
            low_c=low,
            humidity=as_int(current.get("humidity")),
            wind_dir=str(current.get("winddir16Point") or ""),
            wind_scale=_wind_scale(as_float(current.get("windspeedKmph"))),
            wind_speed_kmh=as_float(current.get("windspeedKmph")),
            pressure_hpa=as_float(current.get("pressure")),
            visibility_km=as_float(current.get("visibility")),
            obs_time=str(current.get("observation_time") or ""),
            sunrise=str(astro.get("sunrise") or ""),
            sunset=str(astro.get("sunset") or ""),
            daily=forecasts,
            alerts=[],
        )


def _is_daytime(value: Any) -> bool:
    from ..util import parse_datetime

    parsed = parse_datetime(value)
    if parsed is None:
        return True
    return 6 <= parsed.hour < 19


def _desc(current: Dict[str, Any]) -> str:
    for key in ("lang_zh", "weatherDesc"):
        value = current.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            text = str(value[0].get("value") or "").strip()
            if text:
                return text
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _wind_scale(kmh: float | None) -> str:
    if kmh is None:
        return ""
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
    if kmh < 75:
        return "8级"
    return "9级"
