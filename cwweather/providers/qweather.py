"""QWeather / 和风天气 provider (API key required)."""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

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
        condition = current_payload.get("condition") or {}
        icon_code = str(condition.get("code") or "")
        weather_text = str(condition.get("text") or "")
        is_day = _is_daylight(location, astro)
        display_code = icon_code
        if is_day and display_code.startswith("15") and len(display_code) == 3:
            # QWeather sometimes returns a night-only icon id just before the
            # API's own sunset boundary; the daily astro data is authoritative.
            display_code = "10" + display_code[2:]
        icon, text = qweather_info(display_code, weather_text, is_day)
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
        summary = str(payload.get("summary") or "")
        typed_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            typed_rows.append((as_float(row.get("precip")) or 0.0, row))
        if not typed_rows:
            return {"active": False, "summary": summary}
        raining_now = typed_rows[0][0] > 0.0
        first_wet = next((row for amount, row in typed_rows if amount > 0.0), None)
        kind = str((first_wet or {}).get("type") or "rain")
        snowing = kind == "snow"
        change_minutes = None
        for index, (amount, _row) in enumerate(typed_rows):
            if (amount > 0.0) != raining_now:
                change_minutes = index * 5
                break
        if change_minutes is None:
            if raining_now:
                return {
                    "active": True,
                    "title": "降水预报",
                    "value": "持续",
                    "unit": "正在降雪" if snowing else "正在降雨",
                    "summary": summary,
                    "type": kind,
                    "icon": "snow" if snowing else "rain_light",
                    "probability": 100,
                }
            return {"active": False, "summary": summary}
        if change_minutes > 120:
            if raining_now:
                return {
                    "active": True,
                    "title": "降水预报",
                    "value": "持续",
                    "unit": "正在降雪" if snowing else "正在降雨",
                    "summary": summary,
                    "type": kind,
                    "icon": "snow" if snowing else "rain_light",
                    "probability": 100,
                }
            return {"active": False, "summary": summary}
        if raining_now:
            unit = "分钟后雪停" if snowing else "分钟后雨停"
        else:
            unit = "分钟后有雪" if snowing else "分钟后有雨"
        return {
            "active": True,
            "title": "降水预报",
            "value": str(change_minutes),
            "unit": unit,
            "minutes": change_minutes,
            "summary": summary,
            "time": short_time((first_wet or {}).get("fxTime")),
            "type": kind,
            "icon": "snow" if snowing else "rain_light",
            "probability": 100,
        }


def _clock(value: Any) -> dt_time | None:
    text = str(value or "").strip()
    if not text:
        return None
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timetz().replace(tzinfo=None)
        except ValueError:
            pass
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return None


def _astro_now(location: Location, astro: Dict[str, Any]) -> datetime:
    sample = str(astro.get("sunrise") or astro.get("sunset") or "").strip()
    if "T" in sample:
        try:
            parsed = datetime.fromisoformat(sample.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return datetime.now(parsed.tzinfo)
        except ValueError:
            pass
    try:
        zone = ZoneInfo(location.timezone or "Asia/Shanghai")
    except Exception:
        zone = ZoneInfo("Asia/Shanghai")
    return datetime.now(zone)


def _is_daylight(location: Location, astro: Dict[str, Any]) -> bool:
    now = _astro_now(location, astro)
    sunrise = _clock(astro.get("sunrise"))
    sunset = _clock(astro.get("sunset"))
    if sunrise is not None and sunset is not None:
        if sunrise <= sunset:
            return sunrise <= now.time() < sunset
        return now.time() >= sunrise or now.time() < sunset
    return 6 <= now.hour < 19


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
