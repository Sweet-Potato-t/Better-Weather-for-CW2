"""QWeather / 和风天气 provider (API key required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import qweather_info
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class QWeatherProvider(WeatherProvider):
    id = "qweather"
    name = "和风天气"
    needs_key = True
    supports_alerts = True
    description = "和风天气 API，需要从 dev.qweather.com 获取 API Key；支持中国及全球城市和官方预警。"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "qweather_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "qweather_api_key")
        base = _base_url(str(config.get("qweather_host") or ""))
        coords = f"{location.longitude:.2f},{location.latitude:.2f}"
        common = {"location": coords, "key": key, "lang": "zh", "unit": "m"}

        now_payload = self._get_json(f"{base}/v7/weather/now", common)
        if str((now_payload or {}).get("code")) != "200":
            raise ProviderError(f"和风天气当前天气请求失败（code {now_payload.get('code')}）")
        now = (now_payload or {}).get("now") or {}
        temp = as_float(now.get("temp"))
        if temp is None:
            raise ProviderError("和风天气未返回当前温度")

        daily_payload = self._get_json(f"{base}/v7/weather/3d", common)
        daily_raw: List[Dict[str, Any]] = []
        if str((daily_payload or {}).get("code")) == "200":
            daily_raw = (daily_payload or {}).get("daily") or []

        hourly = self._fetch_hourly(base, common)
        alerts = self._fetch_alerts(base, common)

        icon_code = str(now.get("icon") or "")
        is_day = not icon_code.startswith("15")
        icon, text = qweather_info(icon_code, str(now.get("text") or ""), is_day)

        forecasts: List[DailyForecast] = []
        for index, item in enumerate(daily_raw[:4]):
            if not isinstance(item, dict):
                continue
            day_icon, day_text = qweather_info(
                item.get("iconDay"), str(item.get("textDay") or ""), True
            )
            forecasts.append(
                DailyForecast(
                    date=str(item.get("fxDate") or ""),
                    high_c=as_float(item.get("tempMax")),
                    low_c=as_float(item.get("tempMin")),
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        first_day = first(daily_raw) or {}
        high = as_float(first_day.get("tempMax"))
        low = as_float(first_day.get("tempMin"))
        if forecasts:
            high = forecasts[0].high_c
            low = forecasts[0].low_c

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=icon_code,
            feels_like_c=as_float(now.get("feelsLike")),
            is_day=is_day,
            high_c=high,
            low_c=low,
            humidity=as_int(now.get("humidity")),
            wind_dir=str(now.get("windDir") or ""),
            wind_scale=f"{now.get('windScale')}级" if now.get("windScale") else "",
            wind_speed_kmh=as_float(now.get("windSpeed")),
            pressure_hpa=as_float(now.get("pressure")),
            visibility_km=as_float(now.get("vis")),
            obs_time=str(now.get("obsTime") or ""),
            sunrise=str(first_day.get("sunrise") or ""),
            sunset=str(first_day.get("sunset") or ""),
            daily=forecasts,
            hourly=hourly,
            alerts=alerts,
        )

    def _fetch_hourly(self, base: str, common: Dict[str, Any]) -> List[HourlyForecast]:
        try:
            payload = self._get_json(f"{base}/v7/weather/24h", common)
        except Exception:
            return []
        if str((payload or {}).get("code")) != "200":
            return []
        result: List[HourlyForecast] = []
        for item in (payload or {}).get("hourly") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("icon") or "")
            is_day = not code.startswith("15")
            icon, text = qweather_info(code, str(item.get("text") or ""), is_day)
            result.append(
                HourlyForecast(
                    time=str(item.get("fxTime") or ""),
                    temp_c=as_float(item.get("temp")),
                    icon=icon,
                    text=text,
                    pop=as_int(item.get("pop")),
                )
            )
            if len(result) >= 4:
                break
        return result

    def _fetch_alerts(self, base: str, common: Dict[str, Any]) -> list:
        try:
            payload = self._get_json(f"{base}/v7/warning/now", common)
        except Exception:
            return []
        if str((payload or {}).get("code")) != "200":
            return []
        warning_data = (payload or {}).get("warning") or []
        if isinstance(warning_data, dict):
            warning_data = [warning_data]
        raw = []
        for item in warning_data:
            if not isinstance(item, dict):
                continue
            raw.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "type": item.get("typeName") or item.get("type"),
                    "level": item.get("severityColor") or item.get("level"),
                    "severity": item.get("severity"),
                    "description": item.get("text"),
                    "sender": item.get("sender"),
                    "pub_time": item.get("pubTime"),
                    "start_time": item.get("startTime"),
                    "end_time": item.get("endTime"),
                    "urgency": item.get("urgency"),
                    "certainty": item.get("certainty"),
                }
            )
        return self._alerts(raw, self.id)


def _base_url(host: str) -> str:
    host = (host or "devapi.qweather.com").strip().rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "https://" + host
    return host
