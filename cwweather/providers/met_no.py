"""MET Norway (Yr) provider — free, no API key, attribution required."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..mappings import metno_info
from ..models import DailyForecast, HourlyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, parse_datetime
from .base import WeatherProvider


class MetNoProvider(WeatherProvider):
    id = "met-no"
    name = "MET Norway"
    needs_key = False
    supports_alerts = True
    description = "挪威气象局开放数据，全球覆盖、无需 API Key；请保留数据来源署名。"

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        payload = self._get_json(
            "https://api.met.no/weatherapi/locationforecast/2.0/compact",
            {"lat": f"{location.latitude:.4f}", "lon": f"{location.longitude:.4f}"},
        )
        series = (payload or {}).get("properties", {}).get("timeseries") or []
        if not series:
            raise ProviderError("MET Norway 未返回预报数据")
        current = series[0]
        details = current.get("data", {}).get("instant", {}).get("details", {})
        temp = as_float(details.get("air_temperature"))
        if temp is None:
            raise ProviderError("MET Norway 未返回当前温度")

        symbol = (
            current.get("data", {}).get("next_1_hours", {}).get("summary", {}).get("symbol_code")
            or current.get("data", {}).get("next_6_hours", {}).get("summary", {}).get("symbol_code")
            or ""
        )
        icon, text = metno_info(symbol, True)
        timezone_name = location.timezone or "UTC"
        zone = _zone(timezone_name)

        daily_map: Dict[str, Dict[str, Any]] = {}
        for entry in series:
            time_value = parse_datetime(entry.get("time"))
            if time_value is None:
                continue
            local = time_value.astimezone(zone) if zone else time_value
            date_key = local.strftime("%Y-%m-%d")
            item = daily_map.setdefault(date_key, {"temps": [], "symbols": []})
            item_details = entry.get("data", {}).get("instant", {}).get("details", {})
            value = as_float(item_details.get("air_temperature"))
            if value is not None:
                item["temps"].append(value)
            if 10 <= local.hour <= 15:
                day_symbol = (
                    entry.get("data", {}).get("next_1_hours", {}).get("summary", {}).get("symbol_code")
                    or entry.get("data", {}).get("next_6_hours", {}).get("summary", {}).get("symbol_code")
                )
                if day_symbol:
                    item["symbols"].append(day_symbol)

        daily: List[DailyForecast] = []
        for index, date_key in enumerate(sorted(daily_map.keys())[:4]):
            values = daily_map[date_key]["temps"]
            symbols = daily_map[date_key]["symbols"]
            day_icon, day_text = metno_info(symbols[0] if symbols else symbol, True)
            daily.append(
                DailyForecast(
                    date=date_key,
                    high_c=max(values) if values else None,
                    low_c=min(values) if values else None,
                    text=day_text,
                    icon=day_icon,
                    is_today=index == 0,
                )
            )

        hourly = self._hourly(series, timezone_name)
        alerts = self._fetch_alerts(location, config)

        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=text,
            icon=icon,
            code=str(symbol),
            feels_like_c=None,
            is_day="night" not in str(symbol).lower(),
            high_c=daily[0].high_c if daily else None,
            low_c=daily[0].low_c if daily else None,
            humidity=as_int(details.get("relative_humidity")),
            wind_dir=_wind_direction(as_float(details.get("wind_from_direction"))),
            wind_scale=_wind_scale(as_float(details.get("wind_speed"))),
            wind_speed_kmh=(
                as_float(details.get("wind_speed")) * 3.6
                if as_float(details.get("wind_speed")) is not None
                else None
            ),
            pressure_hpa=as_float(details.get("air_pressure_at_sea_level")),
            visibility_km=None,
            obs_time=str(current.get("time") or ""),
            sunrise="",
            sunset="",
            daily=daily,
            hourly=hourly,
            alerts=alerts,
        )

    @staticmethod
    def _hourly(series: list, timezone_name: str = "") -> List[HourlyForecast]:
        zone = _zone(timezone_name or "UTC")
        result: List[HourlyForecast] = []
        for entry in series:
            if not isinstance(entry, dict):
                continue
            details = entry.get("data", {}).get("instant", {}).get("details", {})
            temp = as_float(details.get("air_temperature"))
            if temp is None:
                continue
            next_hour = entry.get("data", {}).get("next_1_hours", {}) or {}
            symbol = (next_hour.get("summary") or {}).get("symbol_code") or ""
            icon, text = metno_info(symbol, True)
            parsed = parse_datetime(entry.get("time"))
            local_time = parsed.astimezone(zone).isoformat() if parsed is not None else ""
            result.append(
                HourlyForecast(
                    time=local_time,
                    temp_c=temp,
                    icon=icon,
                    text=text,
                )
            )
            if len(result) >= 4:
                break
        return result

    def _fetch_alerts(self, location: Location, config: Dict[str, Any]) -> list:
        try:
            payload = self._get_json(
                "https://api.met.no/weatherapi/metalerts/2.0/current.json",
                {"lat": f"{location.latitude:.4f}", "lon": f"{location.longitude:.4f}", "lang": "en"},
            )
        except Exception:
            return []
        features = (payload or {}).get("features") or []
        raw = []
        for feature in features:
            properties = feature.get("properties") if isinstance(feature, dict) else None
            if not isinstance(properties, dict):
                continue
            awareness = str(properties.get("awareness_level") or "")
            level = _awareness_color(awareness)
            title = (
                properties.get("event")
                or properties.get("eventAwarenessName")
                or properties.get("title")
                or "Weather warning"
            )
            raw.append(
                {
                    "id": properties.get("id") or properties.get("identifier"),
                    "title": title,
                    "type": properties.get("eventAwarenessName") or properties.get("event") or "",
                    "level": level,
                    "severity": awareness,
                    "description": properties.get("description") or properties.get("instruction") or "",
                    "sender": "MET Norway",
                    "pub_time": properties.get("sent") or properties.get("effective"),
                    "start_time": properties.get("onset") or properties.get("effective"),
                    "end_time": properties.get("expires"),
                    "urgency": properties.get("urgency"),
                    "certainty": properties.get("certainty"),
                }
            )
        return self._alerts(raw, self.id)


def _zone(name: str):
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def _awareness_color(value: str) -> str:
    lowered = value.lower()
    for key in ("red", "orange", "yellow", "green"):
        if key in lowered:
            return key
    return ""


def _wind_direction(degrees: Optional[float]) -> str:
    if degrees is None:
        return ""
    labels = ("北风", "东北风", "东风", "东南风", "南风", "西南风", "西风", "西北风")
    return labels[int((degrees % 360) / 45.0 + 0.5) % 8]


def _wind_scale(speed_ms: Optional[float]) -> str:
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
