"""Caiyun Weather provider (彩云天气, token required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import caiyun_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class CaiyunProvider(WeatherProvider):
    id = "caiyun"
    name = "彩云天气"
    needs_key = True
    supports_alerts = True
    description = "彩云天气，需要 Token；v2.6 Token 路径认证，官方推荐 App Key/Secret 签名。"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "caiyun_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        token = self._require_key(config, "caiyun_api_key")
        coords = f"{location.longitude:.4f},{location.latitude:.4f}"
        realtime = self._get_json(
            f"https://api.caiyunapp.com/v2.6/{token}/{coords}/realtime",
            {"lang": "zh_CN"},
        )
        result = (realtime or {}).get("result") or {}
        realtime_data = result.get("realtime") or {}
        temp = as_float(realtime_data.get("temperature"))
        if temp is None:
            raise ProviderError("彩云天气未返回当前温度")

        skycon = str(realtime_data.get("skycon") or "")
        is_day = "NIGHT" not in skycon
        icon, text = caiyun_info(skycon, is_day)
        daily_payload = {}
        try:
            daily_response = self._get_json(
                f"https://api.caiyunapp.com/v2.6/{token}/{coords}/daily",
                {"lang": "zh_CN", "alert": "true"},
            )
            daily_payload = (daily_response or {}).get("result") or {}
        except Exception:
            daily_payload = {}

        daily_raw = daily_payload.get("daily") or {}
        temperatures = daily_raw.get("temperature") or []
        skycons = daily_raw.get("skycon") or []
        daily: List[DailyForecast] = []
        for index, item in enumerate(temperatures[:4]):
            if not isinstance(item, dict):
                continue
            day_skycon = ""
            if index < len(skycons) and isinstance(skycons[index], dict):
                day_skycon = str(skycons[index].get("value") or "")
            day_icon, day_text = caiyun_info(day_skycon, True)
            daily.append(
                DailyForecast(
                    date=_date(index),
                    high_c=as_float(item.get("max")),
                    low_c=as_float(item.get("min")),
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        astro = first(daily_raw.get("astro")) or {}
        wind = realtime_data.get("wind") or {}
        air_quality = realtime_data.get("air_quality") or {}
        aqi_obj = air_quality.get("aqi") or {}
        aqi = aqi_obj.get("chn") if isinstance(aqi_obj, dict) else None
        if aqi is None and isinstance(aqi_obj, dict):
            aqi = aqi_obj.get("usa")
        sunrise = astro.get("sunrise") if isinstance(astro.get("sunrise"), dict) else {}
        sunset = astro.get("sunset") if isinstance(astro.get("sunset"), dict) else {}
        alerts = self._alerts(
            (daily_payload.get("alert") or {}).get("content") or [],
            self.id,
        )

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=skycon,
            feels_like_c=as_float(realtime_data.get("apparent_temperature")),
            is_day="NIGHT" not in skycon,
            high_c=daily[0].high_c if daily else None,
            low_c=daily[0].low_c if daily else None,
            humidity=(
                as_int(as_float(realtime_data.get("humidity")) * 100)
                if as_float(realtime_data.get("humidity")) is not None
                else None
            ),
            wind_dir=_wind_direction(as_float(wind.get("direction"))),
            wind_scale=_wind_scale(as_float(wind.get("speed"))),
            wind_speed_kmh=as_float(wind.get("speed")),
            pressure_hpa=(
                as_float(realtime_data.get("pressure")) / 100.0
                if as_float(realtime_data.get("pressure")) is not None
                else None
            ),
            visibility_km=as_float(realtime_data.get("visibility")),
            aqi=as_int(aqi),
            obs_time=str(realtime_data.get("server_time") or ""),
            sunrise=str(sunrise.get("time") or ""),
            sunset=str(sunset.get("time") or ""),
            daily=daily,
            alerts=alerts,
        )

    def _alerts(self, raw: list, source: str) -> list:
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "id": item.get("alertId") or item.get("id"),
                    "title": item.get("title"),
                    "type": item.get("type") or item.get("title"),
                    "level": item.get("level") or item.get("severity"),
                    "severity": item.get("severity"),
                    "description": item.get("description"),
                    "sender": item.get("source") or "彩云天气",
                    "pub_time": item.get("pubtimestamp"),
                    "start_time": item.get("pubtimestamp"),
                    "end_time": item.get("expires"),
                }
            )
        from ..models import normalize_alerts

        return normalize_alerts(normalized, source)


def _date(index: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.now() + timedelta(days=index)).strftime("%Y-%m-%d")


def _wind_direction(degrees: float | None) -> str:
    if degrees is None:
        return ""
    labels = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    return labels[int((degrees % 360) / 45.0 + 0.5) % 8]


def _wind_scale(speed_kmh: float | None) -> str:
    if speed_kmh is None:
        return ""
    kmh = speed_kmh
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
