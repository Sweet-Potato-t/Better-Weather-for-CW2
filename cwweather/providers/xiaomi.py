"""Xiaomi Weather provider (undocumented, no API key required).

The endpoint is the one used by MIUI/HyperOS Weather.  It needs a
``weathercn:<9-digit city id>`` location key and mainland-China coordinates.
Xiaomi can change or retire this endpoint without notice, so the service treats
failures as normal fallback cases.
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import xiaomi_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class XiaomiProvider(WeatherProvider):
    id = "xiaomi"
    name = "小米天气"
    needs_key = False
    supports_alerts = True
    description = "小米天气 App 同款数据源，无需 API Key，仅支持中国大陆；接口为非官方接口。"

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        if not (73.0 <= location.longitude <= 135.5 and 18.0 <= location.latitude <= 54.0):
            raise ProviderError("小米天气仅支持中国大陆地区")

        city_key, city_name = self._locate(location)
        payload = self._get_json(
            "https://weatherapi.market.xiaomi.com/wtr-v3/weather/all",
            {
                "latitude": f"{location.latitude:.4f}",
                "longitude": f"{location.longitude:.4f}",
                "locationKey": city_key,
                "appKey": "weather20151024",
                "sign": "zUFJoAR2ZVrDy1vF3D07",
                "isGlobal": "false",
                "locale": "zh_cn",
                "days": "4",
            },
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"},
        )
        current = (payload or {}).get("current") or {}
        temperature = current.get("temperature") or {}
        temp = as_float(temperature.get("value"))
        if temp is None:
            raise ProviderError("小米天气未返回当前温度")

        code = str(current.get("weather") or "")
        icon, text = xiaomi_info(code, _is_daytime(current.get("pubTime")))
        daily_raw = (payload or {}).get("forecastDaily") or {}
        daily = self._daily(daily_raw)
        high = daily[0].high_c if daily else None
        low = daily[0].low_c if daily else None
        sun_rise_set = ((daily_raw.get("sunRiseSet") or {}).get("value") or [])
        first_sun = sun_rise_set[0] if sun_rise_set and isinstance(sun_rise_set[0], dict) else {}
        wind = current.get("wind") or {}
        wind_speed = as_float((wind.get("speed") or {}).get("value"))
        wind_direction = as_float((wind.get("direction") or {}).get("value"))

        if city_name:
            if not location.district:
                location.district = city_name
            if not location.city and city_name != location.district:
                location.city = city_name

        alerts = self._alerts(
            (payload or {}).get("alerts")
            or (payload or {}).get("alert")
            or (payload or {}).get("warnings")
            or [],
            self.id,
        )

        aqi = (payload or {}).get("aqi") or {}
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=code,
            feels_like_c=as_float((current.get("feelsLike") or {}).get("value")),
            is_day=_is_daytime(current.get("pubTime")),
            high_c=high,
            low_c=low,
            humidity=as_int((current.get("humidity") or {}).get("value")),
            wind_dir=_wind_direction(wind_direction),
            wind_scale=_wind_scale(wind_speed),
            wind_speed_kmh=wind_speed,
            pressure_hpa=as_float((current.get("pressure") or {}).get("value")),
            visibility_km=as_float((current.get("visibility") or {}).get("value")),
            aqi=as_int(aqi.get("aqi")) if isinstance(aqi, dict) else None,
            obs_time=str(current.get("pubTime") or ""),
            sunrise=str(first_sun.get("from") or ""),
            sunset=str(first_sun.get("to") or ""),
            daily=daily,
            alerts=alerts,
        )

    def _locate(self, location: Location) -> tuple[str, str]:
        payload = self._get_json(
            "https://weatherapi.market.xiaomi.com/wtr-v3/location/city/geo",
            {
                "latitude": f"{location.latitude:.4f}",
                "longitude": f"{location.longitude:.4f}",
                "appKey": "weather20151024",
                "sign": "zUFJoAR2ZVrDy1vF3D07",
                "locale": "zh_cn",
            },
            headers={"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36"},
        )
        items = payload if isinstance(payload, list) else (payload or {}).get("data") or []
        if not items:
            raise ProviderError("小米天气无法定位到中国大陆城市")
        item = first(items) or {}
        key = str(item.get("locationKey") or item.get("key") or "")
        if not key:
            raise ProviderError("小米天气未返回城市标识")
        if not key.startswith("weathercn:"):
            key = "weathercn:" + key
        return key, str(item.get("name") or "")

    def _daily(self, daily_raw: Dict[str, Any]) -> List[DailyForecast]:
        temperatures = ((daily_raw.get("temperature") or {}).get("value") or [])
        weathers = ((daily_raw.get("weather") or {}).get("value") or [])
        result: List[DailyForecast] = []
        for index, pair in enumerate(temperatures[:4]):
            if not isinstance(pair, dict):
                continue
            first_temp = as_float(pair.get("from"))
            second_temp = as_float(pair.get("to"))
            values = [value for value in (first_temp, second_temp) if value is not None]
            high = max(values) if values else None
            low = min(values) if values else None
            code = ""
            if index < len(weathers) and isinstance(weathers[index], dict):
                code = str(weathers[index].get("from") or "")
            icon, text = xiaomi_info(code, True)
            result.append(
                DailyForecast(
                    date=_date_from_index(index),
                    high_c=high,
                    low_c=low,
                    text=text,
                    icon=icon,
                    is_today=index == 0,
                )
            )
        return result

    def _alerts(self, raw: Any, source: str) -> list:
        if isinstance(raw, dict):
            raw = raw.get("warning") or raw.get("alerts") or []
        if not isinstance(raw, list):
            return []
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("alertId") or item.get("id"),
                    "title": item.get("title"),
                    "type": item.get("type") or item.get("typeName"),
                    "level": item.get("level") or item.get("severityColor"),
                    "severity": item.get("severity"),
                    "description": item.get("detail") or item.get("description") or item.get("text"),
                    "sender": item.get("sender") or item.get("source"),
                    "pub_time": item.get("pubTime") or item.get("start_time"),
                    "start_time": item.get("start_time") or item.get("pubTime"),
                    "end_time": item.get("end_time") or item.get("endTime"),
                }
            )
        return self._alerts_list(normalized, source)

    @staticmethod
    def _alerts_list(raw: list, source: str) -> list:
        from ..models import normalize_alerts

        return normalize_alerts(raw, source)


def _date_from_index(index: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.now() + timedelta(days=index)).strftime("%Y-%m-%d")


def _is_daytime(value: Any) -> bool:
    from ..util import parse_datetime

    parsed = parse_datetime(value)
    if parsed is None:
        return True
    return 6 <= parsed.hour < 19


def _wind_direction(degrees: float | None) -> str:
    if degrees is None:
        return ""
    labels = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    return labels[int((degrees % 360) / 45.0 + 0.5) % 8]


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
    return "8级"
