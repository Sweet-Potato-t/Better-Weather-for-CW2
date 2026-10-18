"""WeatherAPI.com provider (API key required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import weatherapi_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class WeatherApiProvider(WeatherProvider):
    id = "weatherapi"
    name = "WeatherAPI"
    needs_key = True
    supports_alerts = True
    description = "WeatherAPI.com，需要 API Key；提供实时天气、3 天预报和天气预警。"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "weatherapi_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "weatherapi_api_key")
        payload = self._get_json(
            "https://api.weatherapi.com/v1/forecast.json",
            {
                "key": key,
                "q": f"{location.latitude:.4f},{location.longitude:.4f}",
                "days": "4",
                "aqi": "yes",
                "alerts": "yes",
                "lang": "zh",
            },
        )
        current = (payload or {}).get("current") or {}
        temp = as_float(current.get("temp_c"))
        if temp is None:
            raise ProviderError("WeatherAPI 未返回当前温度")

        condition = current.get("condition") or {}
        is_day = bool(as_int(current.get("is_day"), 1))
        icon, text = weatherapi_info(
            condition.get("code"), str(condition.get("text") or ""), is_day
        )

        forecast_raw = ((payload or {}).get("forecast") or {}).get("forecastday") or []
        daily: List[DailyForecast] = []
        for index, item in enumerate(forecast_raw[:4]):
            if not isinstance(item, dict):
                continue
            day = item.get("day") or {}
            day_condition = day.get("condition") or {}
            day_icon, day_text = weatherapi_info(
                day_condition.get("code"), str(day_condition.get("text") or ""), True
            )
            daily.append(
                DailyForecast(
                    date=str(item.get("date") or ""),
                    high_c=as_float(day.get("maxtemp_c")),
                    low_c=as_float(day.get("mintemp_c")),
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        first_day = first(forecast_raw) or {}
        astro = first_day.get("astro") or {}
        first_day_data = first_day.get("day") or {}
        air_quality = current.get("air_quality") or {}
        alerts = self._alerts(((payload or {}).get("alerts") or {}).get("alert") or [], self.id)

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=str(condition.get("code") or ""),
            feels_like_c=as_float(current.get("feelslike_c")),
            is_day=is_day,
            high_c=as_float(first_day_data.get("maxtemp_c")),
            low_c=as_float(first_day_data.get("mintemp_c")),
            humidity=as_int(current.get("humidity")),
            wind_dir=str(current.get("wind_dir") or ""),
            wind_scale=_wind_scale(as_float(current.get("wind_kph"))),
            wind_speed_kmh=as_float(current.get("wind_kph")),
            pressure_hpa=as_float(current.get("pressure_mb")),
            visibility_km=as_float(current.get("vis_km")),
            aqi=as_int(air_quality.get("us-epa-index")) if isinstance(air_quality, dict) else None,
            obs_time=str(current.get("last_updated") or ""),
            sunrise=str(astro.get("sunrise") or ""),
            sunset=str(astro.get("sunset") or ""),
            daily=daily,
            alerts=alerts,
        )

    @staticmethod
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

    def _alerts(self, raw: list, source: str) -> list:
        if isinstance(raw, dict):
            raw = [raw]
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("id") or item.get("headline"),
                    "title": item.get("headline") or item.get("event"),
                    "type": item.get("category") or item.get("event"),
                    "level": item.get("severity"),
                    "severity": item.get("severity"),
                    "description": item.get("desc") or item.get("msg"),
                    "sender": item.get("sender_name") or "WeatherAPI",
                    "pub_time": item.get("effective"),
                    "start_time": item.get("effective"),
                    "end_time": item.get("expires"),
                    "urgency": item.get("urgency"),
                    "certainty": item.get("certainty"),
                }
            )
        from ..models import normalize_alerts

        return normalize_alerts(normalized, source)
