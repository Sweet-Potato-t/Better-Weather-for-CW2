"""Normalized weather data model used by every provider."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .mappings import alert_icon_key, normalize_alert_color, normalize_alert_level
from .util import compact_text, iso_now, short_time, today_text, weekday_cn


@dataclass
class Location:
    latitude: float
    longitude: float
    name: str = ""
    city: str = ""
    district: str = ""
    region: str = ""
    country: str = ""
    timezone: str = ""
    source: str = "manual"

    @property
    def display_name(self) -> str:
        parts: List[str] = []
        for value in (self.name, self.district):
            text = (value or "").strip()
            if text and text not in parts:
                parts.append(text)
        # Chinese reverse geocoding often returns a Chinese district plus an
        # English city name. Prefer the district in that case; for Chinese city
        # names keep both (北京市 · 朝阳区).
        if self.city:
            text = self.city.strip()
            has_district = bool(self.district or (self.name and self.name != self.city))
            if text and text not in parts and (_has_cjk(text) or not has_district):
                parts.append(text)
        for value in (self.region, self.country):
            text = (value or "").strip()
            if text and text not in parts:
                parts.append(text)
        return " · ".join(parts[:3]) or self.name or f"{self.latitude:.3f}, {self.longitude:.3f}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "name": self.name,
            "city": self.city,
            "district": self.district,
            "region": self.region,
            "country": self.country,
            "timezone": self.timezone,
            "source": self.source,
            "display_name": self.display_name,
        }


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


@dataclass
class Alert:
    id: str
    title: str
    type: str = ""
    level: str = ""
    color: str = "#0078D4"
    severity: int = 1
    description: str = ""
    sender: str = ""
    pub_time: str = ""
    start_time: str = ""
    end_time: str = ""
    source: str = ""
    icon: str = "alert_generic"
    urgency: str = ""
    certainty: str = ""

    @property
    def level_text(self) -> str:
        label = normalize_alert_level(self.level)
        return f"{label}预警" if label else "天气预警"

    @property
    def short_title(self) -> str:
        return self.title or f"{self.type or '天气'}{self.level_text}"

    def to_dict(self) -> Dict[str, Any]:
        source_names = {
            "qweather": "和风天气",
            "xiaomi": "小米天气",
            "met-no": "MET Norway",
            "openweathermap": "OpenWeatherMap",
            "weatherapi": "WeatherAPI",
            "caiyun": "彩云天气",
        }
        return {
            "id": self.id,
            "title": self.short_title,
            "type": self.type,
            "level": normalize_alert_level(self.level),
            "level_text": self.level_text,
            "color": self.color,
            "severity": self.severity,
            "description": self.description,
            "sender": self.sender,
            "pub_time": self.pub_time,
            "pub_time_short": short_time(self.pub_time),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "source": self.source,
            "source_name": source_names.get(self.source, self.source),
            "icon": self.icon,
            "urgency": self.urgency,
            "certainty": self.certainty,
        }


@dataclass
class DailyForecast:
    date: str
    high_c: Optional[float] = None
    low_c: Optional[float] = None
    text: str = ""
    icon: str = "unknown"
    is_today: bool = False

    def to_dict(self, unit: str = "celsius") -> Dict[str, Any]:
        from .formatting import convert_temp, unit_symbol

        return {
            "date": self.date,
            "weekday": "今天" if self.is_today else weekday_cn(self.date),
            "high": convert_temp(self.high_c, unit),
            "low": convert_temp(self.low_c, unit),
            "text": self.text,
            "icon": self.icon,
            "is_today": self.is_today,
            "unit": unit_symbol(unit),
        }


@dataclass
class HourlyForecast:
    time: str
    temp_c: Optional[float] = None
    icon: str = "unknown"
    text: str = ""
    pop: Optional[int] = None

    def to_dict(self, unit: str = "celsius") -> Dict[str, Any]:
        from .formatting import convert_temp, temp_text

        return {
            "time": self.time,
            "hour": short_time(self.time) or self.time,
            "temp": convert_temp(self.temp_c, unit),
            "temp_text": temp_text(self.temp_c, unit),
            "icon": self.icon,
            "text": self.text,
            "pop": self.pop,
        }


@dataclass
class WeatherSnapshot:
    provider_id: str
    provider_name: str
    location: Location
    current_temp_c: float
    condition: str
    icon: str
    code: str = ""
    feels_like_c: Optional[float] = None
    is_day: bool = True
    high_c: Optional[float] = None
    low_c: Optional[float] = None
    humidity: Optional[int] = None
    wind_dir: str = ""
    wind_scale: str = ""
    wind_speed_kmh: Optional[float] = None
    pressure_hpa: Optional[float] = None
    visibility_km: Optional[float] = None
    aqi: Optional[int] = None
    obs_time: str = ""
    sunrise: str = ""
    sunset: str = ""
    daily: List[DailyForecast] = field(default_factory=list)
    hourly: List[HourlyForecast] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)
    fetched_at: str = field(default_factory=iso_now)
    fallback_used: bool = False
    attempts: List[str] = field(default_factory=list)

    def to_payload(self, unit: str = "celsius", stale: bool = False) -> Dict[str, Any]:
        from .formatting import convert_temp, temp_text, unit_symbol

        now_date = today_text(self.location.timezone)
        daily_payload = [
            item.to_dict(unit) for item in self.daily[:4] if item.date
        ]
        today_entry = next((item for item in daily_payload if item["is_today"]), None)
        if today_entry is None and daily_payload:
            today_entry = daily_payload[0]
            today_entry["is_today"] = True
            today_entry["weekday"] = "今天"

        high = convert_temp(self.high_c, unit)
        low = convert_temp(self.low_c, unit)
        if today_entry:
            if high is None:
                high = today_entry["high"]
            if low is None:
                low = today_entry["low"]

        weather_text = self.condition or (today_entry or {}).get("text", "") or ""
        current = {
            "temp": convert_temp(self.current_temp_c, unit),
            "temp_text": temp_text(self.current_temp_c, unit),
            "feels_like": convert_temp(self.feels_like_c, unit),
            "feels_like_text": temp_text(self.feels_like_c, unit),
            "text": weather_text,
            "icon": self.icon,
            "code": self.code,
            "is_day": self.is_day,
            "humidity": self.humidity,
            "wind_dir": self.wind_dir,
            "wind_scale": self.wind_scale,
            "wind_speed": self.wind_speed_kmh,
            "wind_text": self._wind_text(),
            "pressure": round(self.pressure_hpa, 0) if self.pressure_hpa is not None else None,
            "visibility": round(self.visibility_km, 1) if self.visibility_km is not None else None,
            "aqi": self.aqi,
            "obs_time": short_time(self.obs_time),
        }

        details = self._detail_items(unit, current, high, low)

        return {
            "ok": True,
            "available": True,
            "provider": {
                "id": self.provider_id,
                "name": self.provider_name,
            },
            "location": self.location.to_dict(),
            "current": current,
            "today": {
                "date": now_date,
                "high": high,
                "low": low,
                "high_text": temp_text(high, unit, already_converted=True),
                "low_text": temp_text(low, unit, already_converted=True),
                "text": weather_text,
                "icon": self.icon,
                "sunrise": short_time(self.sunrise),
                "sunset": short_time(self.sunset),
            },
            "daily": daily_payload,
            "hourly": [item.to_dict(unit) for item in self.hourly[:4] if item.time],
            "alerts": [alert.to_dict() for alert in self.alerts],
            "alert_count": len(self.alerts),
            "unit": unit_symbol(unit),
            "updated_at": self.fetched_at,
            "updated_text": short_time(self.fetched_at),
            "stale": stale,
            "fallback_used": self.fallback_used,
            "attempts": list(self.attempts),
            "details": details,
        }

    def _wind_text(self) -> str:
        parts = [part for part in (self.wind_dir, self.wind_scale) if part]
        if not parts and self.wind_speed_kmh is None:
            return ""
        if self.wind_speed_kmh is not None and not self.wind_scale:
            parts.append(f"{self.wind_speed_kmh:.0f} km/h")
        return " ".join(parts)

    def _detail_items(
        self,
        unit: str,
        current: Dict[str, Any],
        high: Optional[float],
        low: Optional[float],
    ) -> List[Dict[str, str]]:
        from .formatting import temp_text, unit_symbol

        items: List[Dict[str, str]] = []
        if current.get("feels_like") is not None:
            items.append(
                {
                    "icon": "ic_fluent_temperature_20_regular",
                    "label": "体感温度",
                    "value": temp_text(self.feels_like_c, unit),
                }
            )
        if current.get("humidity") is not None:
            items.append(
                {
                    "icon": "ic_fluent_water_20_regular",
                    "label": "湿度",
                    "value": f"{current['humidity']}%",
                }
            )
        if current.get("wind_text"):
            items.append(
                {
                    "icon": "ic_fluent_weather_windy_20_regular",
                    "label": "风力",
                    "value": current["wind_text"],
                }
            )
        if current.get("pressure") is not None:
            items.append(
                {
                    "icon": "ic_fluent_gauge_20_regular",
                    "label": "气压",
                    "value": f"{int(current['pressure'])} hPa",
                }
            )
        if current.get("visibility") is not None:
            items.append(
                {
                    "icon": "ic_fluent_eye_20_regular",
                    "label": "能见度",
                    "value": f"{current['visibility']} km",
                }
            )
        if self.aqi is not None:
            items.append(
                {
                    "icon": "ic_fluent_leaf_20_regular",
                    "label": "空气质量",
                    "value": f"AQI {self.aqi}",
                }
            )
        if self.sunrise or self.sunset:
            items.append(
                {
                    "icon": "ic_fluent_weather_sunny_20_regular",
                    "label": "日出 / 日落",
                    "value": f"{short_time(self.sunrise) or '--'} / {short_time(self.sunset) or '--'}",
                }
            )
        if high is not None and low is not None:
            items.append(
                {
                    "icon": "ic_fluent_arrow_up_down_20_regular",
                    "label": "今日温度",
                    "value": f"{temp_text(high, unit, already_converted=True)} / "
                    f"{temp_text(low, unit, already_converted=True)}",
                }
            )
        return items


def normalize_alerts(raw_alerts: List[Dict[str, Any]], source: str) -> List[Alert]:
    """Normalize provider-specific alert dictionaries, de-duplicate and sort.

    Each provider builds a best-effort dictionary.  This function is intentionally
    forgiving because alert APIs frequently add or rename fields.
    """

    normalized: List[Alert] = []
    seen = set()
    for raw in raw_alerts or []:
        if not isinstance(raw, dict):
            continue
        title = compact_text(
            raw.get("title")
            or raw.get("headline")
            or raw.get("event")
            or raw.get("eventAwarenessName")
            or raw.get("name")
            or ""
        )
        alert_type = compact_text(
            raw.get("type")
            or raw.get("typeName")
            or raw.get("category")
            or raw.get("event")
            or ""
        )
        level = compact_text(
            raw.get("level")
            or raw.get("severityColor")
            or raw.get("severity")
            or raw.get("awareness_level")
            or ""
        )
        color = normalize_alert_color(
            raw.get("color") or raw.get("severityColor") or level
        )
        severity = _severity_from(raw, color, level)
        description = compact_text(
            raw.get("description")
            or raw.get("text")
            or raw.get("detail")
            or raw.get("desc")
            or raw.get("instruction")
            or "",
            1200,
        )
        sender = compact_text(
            raw.get("sender")
            or raw.get("sender_name")
            or raw.get("source")
            or raw.get("sourceName")
            or ""
        )
        pub_time = str(
            raw.get("pub_time")
            or raw.get("pubTime")
            or raw.get("sent")
            or raw.get("effective")
            or raw.get("pubtimestamp")
            or ""
        )
        start_time = str(
            raw.get("start_time")
            or raw.get("startTime")
            or raw.get("onset")
            or raw.get("effective")
            or ""
        )
        end_time = str(
            raw.get("end_time")
            or raw.get("endTime")
            or raw.get("expires")
            or ""
        )
        alert_id = str(
            raw.get("id")
            or raw.get("alertId")
            or raw.get("identifier")
            or f"{title}|{alert_type}|{level}|{pub_time}"
        )
        key = (alert_id, title, alert_type, level)
        if key in seen:
            continue
        seen.add(key)
        if not title:
            label = normalize_alert_level(level)
            title = f"{alert_type or '天气'}{label + '预警' if label else '预警'}"
        icon = alert_icon_key(alert_type, title)
        normalized.append(
            Alert(
                id=alert_id,
                title=title,
                type=alert_type,
                level=normalize_alert_level(level),
                color=color,
                severity=severity,
                description=description,
                sender=sender,
                pub_time=pub_time,
                start_time=start_time,
                end_time=end_time,
                source=source,
                icon=icon,
                urgency=compact_text(raw.get("urgency") or ""),
                certainty=compact_text(raw.get("certainty") or ""),
            )
        )

    normalized.sort(key=lambda item: (-item.severity, item.pub_time), reverse=False)
    return normalized


def _severity_from(raw: Dict[str, Any], color: str, level: str) -> int:
    explicit = raw.get("severity")
    if isinstance(explicit, int) and not isinstance(explicit, bool):
        return max(0, min(4, explicit))
    text = str(explicit or "").strip().lower()
    mapping = {
        "cancel": 0,
        "none": 0,
        "unknown": 1,
        "standard": 1,
        "minor": 1,
        "moderate": 2,
        "major": 3,
        "severe": 3,
        "extreme": 4,
    }
    if text in mapping:
        return mapping[text]
    lowered = f"{level} {color}".lower()
    if any(word in lowered for word in ("red", "红", "black", "黑", "extreme", "severe")):
        return 4
    if any(word in lowered for word in ("orange", "橙", "major")):
        return 3
    if any(word in lowered for word in ("yellow", "黄", "moderate")):
        return 2
    if any(word in lowered for word in ("blue", "蓝", "minor", "green", "绿", "white", "白")):
        return 1
    return 1


def snapshot_from_dict(data: Dict[str, Any]) -> WeatherSnapshot:
    """Recover a snapshot from the JSON-safe payload (used by tests/cache)."""

    location = Location(**{k: v for k, v in data.get("location", {}).items() if k != "display_name"})
    daily = [
        DailyForecast(
            date=item.get("date", ""),
            high_c=item.get("high"),
            low_c=item.get("low"),
            text=item.get("text", ""),
            icon=item.get("icon", "unknown"),
            is_today=bool(item.get("is_today")),
        )
        for item in data.get("daily", [])
    ]
    return WeatherSnapshot(
        provider_id=data.get("provider", {}).get("id", ""),
        provider_name=data.get("provider", {}).get("name", ""),
        location=location,
        current_temp_c=float(data.get("current", {}).get("temp") or 0),
        condition=data.get("current", {}).get("text", ""),
        icon=data.get("current", {}).get("icon", "unknown"),
        daily=daily,
    )


def parse_iso_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10:
        return text[:10]
    return datetime.now().strftime("%Y-%m-%d")
