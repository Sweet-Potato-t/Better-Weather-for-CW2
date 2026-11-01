"""Tencent Location Service weather provider (WebService key required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import weather_text_info
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class TencentProvider(WeatherProvider):
    id = "tencent"
    name = "腾讯天气"
    needs_key = True
    supports_alerts = True
    description = "腾讯位置服务天气查询；需要 WebService Key，支持实时、预报、24 小时和预警。"
    key_label = "腾讯位置服务 Key"

    _BASE = "https://apis.map.qq.com/ws/weather/v1/"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "tencent_api_key")

    def _get(self, key: str, location: Location, weather_type: str, extra: Dict[str, str] | None = None) -> Dict[str, Any]:
        params = {
            "key": key,
            "location": f"{location.latitude:.6f},{location.longitude:.6f}",
            "type": weather_type,
            "output": "json",
        }
        if extra:
            params.update(extra)
        payload = self._get_json(self._BASE, params)
        status = payload.get("status") if isinstance(payload, dict) else None
        if status is None or int(status) != 0:
            raise ProviderError(f"腾讯天气请求失败（{payload.get('message') if isinstance(payload, dict) else '未知错误'}）")
        return payload.get("result") or {}

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "tencent_api_key")
        now = self._get(key, location, "now", {"added_fields": "alarm,air"})
        future = self._get(key, location, "future")
        hours = self._get(key, location, "hours")

        realtime = first(now.get("realtime")) or {}
        infos = realtime.get("infos") or {}
        temp = as_float(infos.get("temperature"))
        if temp is None:
            raise ProviderError("腾讯天气未返回当前温度")
        text = str(infos.get("weather") or "未知天气")
        icon, condition = weather_text_info(text, True)

        forecast = first(future.get("forecast")) or {}
        forecast_infos = forecast.get("infos") or []
        daily: List[DailyForecast] = []
        for index, item in enumerate(forecast_infos[:4]):
            if not isinstance(item, dict):
                continue
            day = item.get("day") or {}
            night = item.get("night") or {}
            day_text = str(day.get("weather") or "")
            day_icon, day_condition = weather_text_info(day_text, True)
            values = [as_float(day.get("temperature")), as_float(night.get("temperature"))]
            values = [v for v in values if v is not None]
            daily.append(DailyForecast(
                date=str(item.get("date") or ""),
                high_c=max(values) if values else None,
                low_c=min(values) if values else None,
                text=day_condition,
                icon=day_icon,
                is_today=index == 0,
            ))

        hourly: List[HourlyForecast] = []
        hour_block = first(hours.get("forecast_hours")) or {}
        for item in (hour_block.get("infos") or []):
            if not isinstance(item, dict):
                continue
            info = item.get("info") or {}
            hour_text = str(info.get("weather") or "")
            hour_icon, hour_condition = weather_text_info(hour_text, True)
            hourly.append(HourlyForecast(
                time=str(item.get("hour") or ""),
                temp_c=as_float(info.get("temperature")),
                icon=hour_icon,
                text=hour_condition,
            ))
            if len(hourly) >= 4:
                break

        first_day = first(forecast_infos) or {}
        first_day_data = first_day.get("day") or {}
        first_night_data = first_day.get("night") or {}
        values = [as_float(first_day_data.get("temperature")), as_float(first_night_data.get("temperature"))]
        values = [v for v in values if v is not None]
        air = realtime.get("air") or {}
        alerts = self._alerts(realtime.get("alarms") or [], realtime.get("update_time"), self.id)
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=condition,
            icon=icon,
            code=str(infos.get("weather") or ""),
            is_day=True,
            high_c=max(values) if values else None,
            low_c=min(values) if values else None,
            humidity=as_int(infos.get("humidity")),
            wind_dir=str(infos.get("wind_direction") or ""),
            wind_scale=str(infos.get("wind_power_v2") or infos.get("wind_power") or ""),
            pressure_hpa=as_float(infos.get("air_pressure")),
            aqi=as_int(air.get("aqi")),
            obs_time=str(realtime.get("update_time") or ""),
            daily=daily,
            hourly=hourly,
            alerts=alerts,
        )

    def _alerts(self, raw: list, update_time: str, source: str) -> list:
        normalized = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "id": item.get("title"),
                "title": item.get("title"),
                "type": item.get("type_name"),
                "level": item.get("level_name"),
                "description": item.get("pub_content"),
                "sender": "腾讯天气",
                "pub_time": update_time,
                "start_time": update_time,
            })
        from ..models import normalize_alerts
        return normalize_alerts(normalized, source)
