"""QWeather / 和风天气 provider (API key required)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from ..mappings import qweather_info
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first, short_time
from .base import WeatherProvider

try:
    from loguru import logger  # type: ignore
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("classwidgets.weather")


class QWeatherProvider(WeatherProvider):
    id = "qweather"
    name = "和风天气"
    needs_key = True
    supports_alerts = True
    description = "和风天气 API，需要 API Key 和专属 API Host；支持中国及全球城市和官方预警。"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "qweather_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "qweather_api_key")
        host = str(config.get("qweather_host") or "").strip()
        if not host:
            raise ProviderError("请先在插件设置中填写和风天气 API Host")
        base = _base_url(host)
        headers = (
            {"Authorization": f"Bearer {key}"}
            if key.count(".") == 2
            else {"X-QW-Api-Key": key}
        )
        lat, lon = location.latitude, location.longitude
        current_payload = self._get_json(
            f"{base}/weather/v1/current/{lat:.2f}/{lon:.2f}",
            {"localTime": "true", "lang": "zh"},
            headers=headers,
        )
        if not isinstance(current_payload, dict) or current_payload.get("error"):
            raise ProviderError(f"和风天气实时天气请求失败：{str(current_payload)[:160]}")
        temp = as_float((current_payload.get("temperature") or {}).get("value"))
        if temp is None:
            raise ProviderError("和风天气未返回当前温度")

        daily_payload = self._get_json(
            f"{base}/weather/v1/daily/{lat:.2f}/{lon:.2f}",
            {"days": "4", "localTime": "true", "lang": "zh"},
            headers=headers,
        )
        days = (daily_payload or {}).get("days") or []
        hourly = self._fetch_hourly(base, location, headers)
        alerts = self._fetch_alerts(base, location, headers)
        precipitation = self._fetch_precipitation(base, location, headers)

        condition = current_payload.get("condition") or {}
        icon_code = str(condition.get("code") or "")
        weather_text = str(condition.get("text") or "")
        is_day = 6 <= datetime.now().hour < 18
        icon, text = qweather_info(icon_code, weather_text, is_day)

        forecasts: List[DailyForecast] = []
        for index, item in enumerate(days[:4]):
            if not isinstance(item, dict):
                continue
            day = item.get("daytime") or {}
            day_condition = day.get("condition") or {}
            day_icon, day_text = qweather_info(
                day_condition.get("code"), str(day_condition.get("text") or ""), True
            )
            date = str(item.get("forecastStartTime") or "").split("T")[0]
            high = as_float((item.get("temperatureMax") or {}).get("value"))
            low = as_float((item.get("temperatureMin") or {}).get("value"))
            forecasts.append(DailyForecast(
                date=date, high_c=high, low_c=low,
                text=day_text, icon=day_icon, is_today=index == 0,
            ))

        first_day = first(forecasts)
        first_raw = first(days) or {}
        astro = first_raw.get("astro") or {}
        wind = current_payload.get("wind") or {}
        wind_dir = wind.get("direction") or {}
        pressure = current_payload.get("pressure") or {}
        visibility = current_payload.get("visibility") or {}
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=icon_code,
            feels_like_c=as_float((current_payload.get("feelsLike") or {}).get("value")),
            is_day=is_day,
            high_c=first_day.high_c if first_day else None,
            low_c=first_day.low_c if first_day else None,
            humidity=as_int(as_float(current_payload.get("humidity")) * 100)
                if current_payload.get("humidity") is not None else None,
            wind_dir=_compass_zh(str(wind_dir.get("compass") or "")),
            wind_scale=(str(wind.get("scale")) + "级") if wind.get("scale") is not None else "",
            wind_speed_kmh=as_float((wind.get("speed") or {}).get("value")) * 3.6
                if (wind.get("speed") or {}).get("value") is not None else None,
            pressure_hpa=as_float(pressure.get("value")),
            visibility_km=as_float(visibility.get("value")) / 1000.0
                if visibility.get("value") is not None else None,
            obs_time=str(current_payload.get("time") or ""),
            sunrise=str(astro.get("sunrise") or ""),
            sunset=str(astro.get("sunset") or ""),
            daily=forecasts,
            hourly=hourly,
            alerts=alerts,
            precipitation=precipitation,
        )

    def _fetch_hourly(self, base: str, location: Location, headers: Dict[str, str]) -> List[HourlyForecast]:
        try:
            payload = self._get_json(
                f"{base}/weather/v1/hourly/{location.latitude:.2f}/{location.longitude:.2f}",
                {"hours": "24", "localTime": "true", "lang": "zh"},
                headers=headers,
            )
        except Exception as exc:
            logger.warning(f"QWeather hourly request failed: {exc}")
            return []
        result: List[HourlyForecast] = []
        for item in (payload or {}).get("hours") or []:
            if not isinstance(item, dict):
                continue
            condition = item.get("condition") or {}
            icon, text = qweather_info(
                condition.get("code"), str(condition.get("text") or ""), True
            )
            precipitation = item.get("precipitation") or {}
            probability = as_float(precipitation.get("probability"))
            result.append(HourlyForecast(
                time=str(item.get("forecastTime") or ""),
                temp_c=as_float((item.get("temperature") or {}).get("value")),
                icon=icon, text=text,
                pop=as_int(probability * 100) if probability is not None else None,
            ))
            if len(result) >= 4:
                break
        return result

    def _fetch_alerts(self, base: str, location: Location, headers: Dict[str, str]) -> list:
        url = (
            f"{base}/weatheralert/v1/current/"
            f"{location.latitude:.2f}/{location.longitude:.2f}"
        )
        try:
            payload = self._get_json(
                url, {"localTime": "true", "lang": "zh"}, headers=headers
            )
        except Exception as exc:
            logger.warning(f"QWeather warning request failed: {exc}")
            return []
        if not isinstance(payload, dict) or payload.get("error"):
            logger.warning(f"QWeather warning response invalid: {str(payload)[:160]}")
            return []
        raw = []
        for item in payload.get("alerts") or []:
            if not isinstance(item, dict):
                continue
            event = item.get("eventType") or {}
            color = item.get("color") or {}
            color_code = color.get("code") if isinstance(color, dict) else str(color or "")
            description = str(item.get("description") or "")
            instruction = str(item.get("instruction") or "")
            if instruction and instruction not in description:
                description = (description + "\n\n" + instruction).strip()
            raw.append(
                {
                    "id": item.get("id"),
                    "title": item.get("headline"),
                    "type": event.get("name") if isinstance(event, dict) else "",
                    "level": color_code,
                    "severity": item.get("severity"),
                    "description": description,
                    "sender": item.get("senderName"),
                    "pub_time": item.get("issuedTime"),
                    "start_time": item.get("effectiveTime") or item.get("onsetTime"),
                    "end_time": item.get("expireTime"),
                    "urgency": item.get("urgency"),
                    "certainty": item.get("certainty"),
                }
            )
        logger.info(f"QWeather warnings: {len(raw)}")
        return self._alerts(raw, self.id)

    def _fetch_precipitation(
        self, base: str, location: Location, headers: Dict[str, str]
    ) -> Dict[str, Any]:
        coords = f"{location.longitude:.2f},{location.latitude:.2f}"
        try:
            payload = self._get_json(
                f"{base}/v7/minutely/5m",
                {"location": coords, "lang": "zh"},
                headers=headers,
            )
        except Exception as exc:
            logger.warning(f"QWeather minutely request failed: {exc}")
            return {}
        if not isinstance(payload, dict) or str(payload.get("code")) != "200":
            logger.warning(f"QWeather minutely response code: {payload.get('code') if isinstance(payload, dict) else '?'}")
            return {}
        rows = payload.get("minutely") or []
        first_wet = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (as_float(row.get("precip")) or 0.0) > 0:
                first_wet = row
                break
        if not first_wet:
            return {"active": False, "summary": str(payload.get("summary") or "")}
        kind = str(first_wet.get("type") or "rain")
        return {
            "active": True,
            "summary": str(payload.get("summary") or ""),
            "time": short_time(first_wet.get("fxTime")),
            "type": kind,
            "icon": "snow" if kind == "snow" else "rain_light",
            "probability": 100,
        }


_COMPASS = {
    "n": "北风", "nne": "东北偏北风", "ne": "东北风", "ene": "东北偏东风",
    "e": "东风", "ese": "东南偏东风", "se": "东南风", "sse": "东南偏南风",
    "s": "南风", "ssw": "西南偏南风", "sw": "西南风", "wsw": "西南偏西风",
    "w": "西风", "wnw": "西北偏西风", "nw": "西北风", "nnw": "西北偏北风",
    "none": "", "vrb": "风向不定",
}


def _compass_zh(value: str) -> str:
    return _COMPASS.get(str(value or "").lower(), value or "")


def _base_url(host: str) -> str:
    host = (host or "").strip().rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "https://" + host
    return host
