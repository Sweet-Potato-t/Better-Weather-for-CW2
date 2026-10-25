"""QWeather / 和风天气 provider (API key required)."""

from __future__ import annotations

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
        coords = f"{location.longitude:.2f},{location.latitude:.2f}"
        common = {"location": coords, "lang": "zh", "unit": "m"}
        headers = (
            {"Authorization": f"Bearer {key}"}
            if key.count(".") == 2
            else {"X-QW-Api-Key": key}
        )

        now_payload = self._get_json(f"{base}/v7/weather/now", common, headers=headers)
        if str((now_payload or {}).get("code")) != "200":
            raise ProviderError(f"和风天气当前天气请求失败（code {now_payload.get('code')}）")
        now = (now_payload or {}).get("now") or {}
        temp = as_float(now.get("temp"))
        if temp is None:
            raise ProviderError("和风天气未返回当前温度")

        daily_payload = self._get_json(f"{base}/v7/weather/3d", common, headers=headers)
        daily_raw: List[Dict[str, Any]] = []
        if str((daily_payload or {}).get("code")) == "200":
            daily_raw = (daily_payload or {}).get("daily") or []

        hourly = self._fetch_hourly(base, common, headers)
        alerts = self._fetch_alerts(base, location, headers)
        precipitation = self._fetch_precipitation(base, location, headers)

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
            precipitation=precipitation,
        )

    def _fetch_hourly(self, base: str, common: Dict[str, Any], headers: Dict[str, str]) -> List[HourlyForecast]:
        try:
            payload = self._get_json(f"{base}/v7/weather/24h", common, headers=headers)
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


def _base_url(host: str) -> str:
    host = (host or "").strip().rstrip("/")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "https://" + host
    return host
