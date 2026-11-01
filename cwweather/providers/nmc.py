"""National Meteorological Center (NMC) public weather pages provider."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..mappings import weather_text_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


def _num(value: Any) -> Optional[float]:
    number = as_float(value)
    if number is None or abs(number) >= 9999:
        return None
    return number


def _norm(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"(维吾尔|壮族|回族|自治区|自治州|特别行政区|省|市|地区|盟|区|县|旗)$", "", text)
    return text.strip()


class NmcProvider(WeatherProvider):
    id = "nmc"
    name = "中央气象台（NMC）"
    needs_key = False
    supports_alerts = True
    description = "中央气象台公开页面数据；无需 Key，仅支持中国大陆站点，覆盖当前天气和逐日预报。"
    key_label = ""

    _BASE = "https://www.nmc.cn"
    _provinces: Optional[List[Dict[str, Any]]] = None
    _stations: Dict[str, List[Dict[str, Any]]] = {}

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        station = self._find_station(location)
        payload = self._get_json(
            f"{self._BASE}/rest/weather",
            {"stationid": station["code"]},
        )
        data = (payload or {}).get("data") or {}
        real = data.get("real") or {}
        weather = real.get("weather") or {}
        temp = as_float(weather.get("temperature"))
        if temp is None:
            raise ProviderError("中央气象台未返回当前温度")
        wind = real.get("wind") or {}
        predict = data.get("predict") or {}
        details = predict.get("detail") or []
        temperature_chart = data.get("tempchart") or []
        chart_temps: Dict[str, tuple] = {}
        for row in temperature_chart:
            if not isinstance(row, dict):
                continue
            date = str(row.get("time") or "").replace("/", "-")
            high = _num(row.get("max_temp"))
            low = _num(row.get("min_temp"))
            if date and (high is not None or low is not None):
                chart_temps[date] = (high, low)
        text = str(weather.get("info") or "").strip()
        if not text or text in ("-", "9999"):
            for item in details:
                if not isinstance(item, dict):
                    continue
                for part in (item.get("night"), item.get("day")):
                    info = str(((part or {}).get("weather") or {}).get("info") or "").strip()
                    if info and info not in ("-", "9999"):
                        text = info
                        break
                if text and text not in ("-", "9999"):
                    break
        text = text if text and text not in ("-", "9999") else "未知天气"
        icon, condition = weather_text_info(text, True)
        daily: List[DailyForecast] = []
        for index, item in enumerate(details[:4]):
            if not isinstance(item, dict):
                continue
            day = item.get("day") or {}
            night = item.get("night") or {}
            day_weather = day.get("weather") or {}
            day_text = str(day_weather.get("info") or "")
            if not day_text or day_text in ("-", "9999"):
                day_text = str((night.get("weather") or {}).get("info") or text)
            day_icon, day_condition = weather_text_info(day_text, True)
            values = [
                _num(day_weather.get("temperature")),
                _num((night.get("weather") or {}).get("temperature")),
            ]
            values = [v for v in values if v is not None]
            date = str(item.get("date") or "")
            chart = chart_temps.get(date)
            if chart:
                values = [v for v in chart if v is not None] or values
            daily.append(DailyForecast(
                date=date,
                high_c=max(values) if values else None,
                low_c=min(values) if values else None,
                text=day_condition,
                icon=day_icon,
                is_today=index == 0,
            ))
        first_day = first(daily)
        today_chart = chart_temps.get(datetime.now().strftime("%Y-%m-%d"), (None, None))
        current_high = today_chart[0] if today_chart[0] is not None else (first_day.high_c if first_day else None)
        current_low = today_chart[1] if today_chart[1] is not None else (first_day.low_c if first_day else None)
        sunrise_sunset = real.get("sunriseSunset") or {}
        alerts = self._alerts(real.get("warn") or {}, self.id)
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=condition,
            icon=icon,
            code=str(weather.get("img") or ""),
            is_day=True,
            high_c=current_high,
            low_c=current_low,
            feels_like_c=_num(weather.get("feelst")),
            humidity=as_int(weather.get("humidity")),
            wind_dir=str(wind.get("direct") or ""),
            wind_scale=str(wind.get("power") or ""),
            wind_speed_kmh=as_float(wind.get("speed")),
            pressure_hpa=_num(weather.get("airpressure")),
            obs_time=str(real.get("publish_time") or ""),
            sunrise=str(sunrise_sunset.get("sunrise") or ""),
            sunset=str(sunrise_sunset.get("sunset") or ""),
            daily=daily,
            hourly=[],
            alerts=alerts,
        )

    def _find_station(self, location: Location) -> Dict[str, Any]:
        provinces = self._get_json(f"{self._BASE}/rest/province/all")
        if not isinstance(provinces, list):
            raise ProviderError("中央气象台站点列表不可用")
        if self._provinces is None:
            self._provinces = provinces
        region = _norm(location.region)
        candidates = [p for p in provinces if _norm(p.get("name")) == region or region in _norm(p.get("name"))]
        if not candidates:
            candidates = provinces
        targets = [location.district, location.city, location.name, location.region]
        targets = [_norm(x) for x in targets if _norm(x)]
        best: Optional[Dict[str, Any]] = None
        best_score = -1
        for province in candidates:
            code = str(province.get("code") or "")
            stations = self._stations.get(code)
            if stations is None:
                stations = self._get_json(f"{self._BASE}/rest/province/{code}") or []
                self._stations[code] = stations if isinstance(stations, list) else []
            for station in stations:
                if not isinstance(station, dict):
                    continue
                city = _norm(station.get("city"))
                score = 0
                for target in targets:
                    if target == city:
                        score = max(score, 100)
                    elif target and (target in city or city in target):
                        score = max(score, 50 + len(city))
                if score > best_score:
                    best_score = score
                    best = station
            if best_score >= 100:
                break
        if not best:
            raise ProviderError("中央气象台未找到该地区站点")
        return best

    def _alerts(self, warn: Dict[str, Any], source: str) -> list:
        alert = str(warn.get("alert") or "").strip()
        if not alert or alert == "9999":
            return []
        normalized = [{
            "id": f"{warn.get('signaltype')}-{warn.get('issuetime')}",
            "title": warn.get("issuecontent") or alert,
            "type": warn.get("signaltype"),
            "level": warn.get("signallevel"),
            "description": warn.get("issuecontent"),
            "sender": warn.get("province") or "中央气象台",
            "pub_time": warn.get("issuetime"),
            "start_time": warn.get("issuetime"),
        }]
        from ..models import normalize_alerts
        return normalize_alerts(normalized, source)
