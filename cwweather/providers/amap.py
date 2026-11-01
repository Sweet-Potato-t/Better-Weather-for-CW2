"""AMap / 高德天气 provider (Web Service API key required)."""

from __future__ import annotations

from typing import Any, Dict, List

from ..mappings import weather_text_info
from ..models import DailyForecast, Location, WeatherSnapshot
from ..util import ProviderError, as_float, as_int, first
from .base import WeatherProvider


class AmapProvider(WeatherProvider):
    id = "amap"
    name = "高德天气"
    needs_key = True
    supports_alerts = False
    description = "高德开放平台天气查询；需要 Web 服务 Key，使用行政区 adcode 查询。"
    key_label = "高德 Web 服务 Key"

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        self._require_key(config, "amap_api_key")

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        key = self._require_key(config, "amap_api_key")
        adcode = self._adcode(location, key)
        base_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        live_payload = self._get_json(base_url, {
            "key": key, "city": adcode, "extensions": "base",
        })
        all_payload = self._get_json(base_url, {
            "key": key, "city": adcode, "extensions": "all",
        })
        if str(live_payload.get("status", "0")) != "1":
            raise ProviderError(f"高德天气实况请求失败（{live_payload.get('info') or '未知错误'}）")
        live = first(live_payload.get("lives")) or {}
        temp = as_float(live.get("temperature"))
        if temp is None:
            raise ProviderError("高德天气未返回当前温度")

        text = str(live.get("weather") or "未知天气")
        icon, condition = weather_text_info(text, True)
        forecasts = first(all_payload.get("forecasts")) or {}
        casts = forecasts.get("casts") or []
        daily: List[DailyForecast] = []
        for index, item in enumerate(casts[:4]):
            if not isinstance(item, dict):
                continue
            day_text = str(item.get("dayweather") or "")
            day_icon, day_condition = weather_text_info(day_text, True)
            values = [as_float(item.get("daytemp")), as_float(item.get("nighttemp"))]
            values = [v for v in values if v is not None]
            daily.append(DailyForecast(
                date=str(item.get("date") or ""),
                high_c=max(values) if values else None,
                low_c=min(values) if values else None,
                text=day_condition,
                icon=day_icon,
                is_today=index == 0,
            ))

        first_cast = first(casts) or {}
        vals = [as_float(first_cast.get("daytemp")), as_float(first_cast.get("nighttemp"))]
        vals = [v for v in vals if v is not None]
        return WeatherSnapshot(
            provider_id=self.id,
            provider_name=self.name,
            location=location,
            current_temp_c=temp,
            condition=condition,
            icon=icon,
            code=str(live.get("weather") or ""),
            is_day=True,
            high_c=max(vals) if vals else None,
            low_c=min(vals) if vals else None,
            humidity=as_int(live.get("humidity")),
            wind_dir=str(live.get("winddirection") or ""),
            wind_scale=str(live.get("windpower") or ""),
            wind_speed_kmh=as_float(live.get("windspeed")),
            pressure_hpa=as_float(live.get("pressure")),
            obs_time=str(live.get("reporttime") or ""),
            daily=daily,
            hourly=[],
            alerts=[],
        )

    def _adcode(self, location: Location, key: str) -> str:
        try:
            payload = self._get_json(
                "https://restapi.amap.com/v3/geocode/regeo",
                {"key": key, "location": f"{location.longitude:.6f},{location.latitude:.6f}"},
            )
            component = ((payload or {}).get("regeocode") or {}).get("addressComponent") or {}
            adcode = str(component.get("adcode") or "").strip()
            if adcode:
                return adcode
        except Exception:
            pass
        raise ProviderError("高德天气无法从坐标解析行政区 adcode")
