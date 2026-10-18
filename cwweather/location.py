"""IP geolocation, reverse geocoding and city search helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .models import Location
from .util import WeatherError, as_float, first, http_get_json


class LocationError(WeatherError):
    pass


class LocationService:
    IP_CACHE_SECONDS = 30 * 60
    REVERSE_CACHE_SECONDS = 12 * 60 * 60

    def __init__(self) -> None:
        self._ip_location: Optional[Location] = None
        self._ip_cached_at = 0.0
        self._reverse_cache: Dict[tuple[int, int], Dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve(
        self,
        config: Dict[str, Any],
        *,
        device_location: Optional[Dict[str, Any]] = None,
        force_ip: bool = False,
    ) -> Location:
        auto = bool(config.get("auto_location", True))
        if not auto:
            return self.manual_location(config)

        strategy = str(config.get("location_strategy") or "auto").lower()
        if device_location and strategy in ("auto", "device"):
            location = self._from_device(device_location)
            if location is not None:
                return location

        # "device" falls back to IP after the plugin's positioning timeout.
        return self.ip_location(force=force_ip)

    def manual_location(self, config: Dict[str, Any]) -> Location:
        latitude = as_float(config.get("manual_lat"), 39.9042) or 39.9042
        longitude = as_float(config.get("manual_lon"), 116.4074) or 116.4074
        name = str(config.get("manual_city") or "").strip()
        region = str(config.get("manual_region") or "").strip()
        country = str(config.get("manual_country") or "").strip()
        timezone_name = str(config.get("manual_timezone") or "Asia/Shanghai").strip()
        location = Location(
            latitude=latitude,
            longitude=longitude,
            name=name or "自定义位置",
            city=name if name and not region else "",
            region=region,
            country=country,
            timezone=timezone_name,
            source="manual",
        )
        if not location.name or location.name == "自定义位置":
            info = self.reverse_geocode(latitude, longitude, timezone_name)
            _apply_reverse(location, info)
        return location

    def invalidate_ip(self) -> None:
        self._ip_location = None
        self._ip_cached_at = 0.0

    def ip_location(self, *, force: bool = False) -> Location:
        now = time.monotonic()
        if (
            not force
            and self._ip_location is not None
            and now - self._ip_cached_at < self.IP_CACHE_SECONDS
        ):
            return self._ip_location

        errors: List[str] = []
        for source, loader in (
            ("ipwho.is", self._ipwho),
            ("ipapi.co", self._ipapi),
            ("ip.sb", self._ipsb),
            ("ipinfo.io", self._ipinfo),
            ("ip-api.com", self._ipapi_com),
        ):
            try:
                location = loader()
            except Exception as exc:
                errors.append(f"{source}: {exc}")
                continue
            if location is None:
                continue
            location.source = "ip"
            if not location.name:
                info = self.reverse_geocode(location.latitude, location.longitude)
                _apply_reverse(location, info)
            if not location.timezone:
                location.timezone = "Asia/Shanghai"
            self._ip_location = location
            self._ip_cached_at = time.monotonic()
            return location

        raise LocationError("无法通过公网 IP 获取位置：" + "；".join(errors[-2:]))

    def reverse_geocode(
        self, latitude: float, longitude: float, timezone_name: str = ""
    ) -> Dict[str, str]:
        key = (round(latitude, 2), round(longitude, 2))
        cached = self._reverse_cache.get(key)
        if cached:
            try:
                age = time.time() - float(cached.get("_ts", 0))
            except (TypeError, ValueError):
                age = self.REVERSE_CACHE_SECONDS + 1
            if age < self.REVERSE_CACHE_SECONDS:
                return cached

        info: Dict[str, str] = {}
        try:
            payload = http_get_json(
                "https://api.bigdatacloud.net/data/reverse-geocode-client",
                {
                    "latitude": f"{latitude:.4f}",
                    "longitude": f"{longitude:.4f}",
                    "localityLanguage": "zh",
                },
                timeout=10,
                retries=1,
            )
            if isinstance(payload, dict):
                info = {
                    "name": str(payload.get("locality") or payload.get("city") or ""),
                    "city": str(payload.get("city") or payload.get("locality") or ""),
                    "district": str(payload.get("locality") or ""),
                    "region": str(payload.get("principalSubdivision") or ""),
                    "country": str(payload.get("countryName") or ""),
                }
        except Exception:
            info = {}

        if not info.get("city"):
            try:
                payload = http_get_json(
                    "https://nominatim.openstreetmap.org/reverse",
                    {
                        "format": "jsonv2",
                        "lat": f"{latitude:.4f}",
                        "lon": f"{longitude:.4f}",
                        "accept-language": "zh-CN",
                    },
                    timeout=10,
                    retries=0,
                )
                if isinstance(payload, dict):
                    address = payload.get("address") or {}
                    info = {
                        "name": str(
                            address.get("city")
                            or address.get("town")
                            or address.get("county")
                            or address.get("village")
                            or ""
                        ),
                        "city": str(address.get("city") or address.get("town") or ""),
                        "district": str(
                            address.get("suburb")
                            or address.get("city_district")
                            or address.get("district")
                            or ""
                        ),
                        "region": str(address.get("state") or address.get("province") or ""),
                        "country": str(address.get("country") or ""),
                    }
            except Exception:
                pass

        if info:
            info["_ts"] = time.time()  # type: ignore[assignment]
            self._reverse_cache[key] = info
        return info

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        results: List[Dict[str, Any]] = []
        try:
            payload = http_get_json(
                "https://geocoding-api.open-meteo.com/v1/search",
                {"name": query, "count": limit, "language": "zh", "format": "json"},
                timeout=10,
                retries=1,
            )
            for item in (payload or {}).get("results") or []:
                latitude = as_float(item.get("latitude"))
                longitude = as_float(item.get("longitude"))
                if latitude is None or longitude is None:
                    continue
                name = str(item.get("name") or "").strip()
                region = str(item.get("admin1") or "").strip()
                country = str(item.get("country") or "").strip()
                display = " · ".join(part for part in (name, region, country) if part)
                results.append(
                    {
                        "name": name,
                        "display_name": display or f"{latitude:.3f}, {longitude:.3f}",
                        "latitude": latitude,
                        "longitude": longitude,
                        "region": region,
                        "country": country,
                        "timezone": str(item.get("timezone") or ""),
                        "source": "open-meteo",
                    }
                )
        except Exception:
            pass

        if not results:
            try:
                payload = http_get_json(
                    "https://nominatim.openstreetmap.org/search",
                    {
                        "format": "jsonv2",
                        "q": query,
                        "limit": limit,
                        "accept-language": "zh-CN",
                        "addressdetails": "1",
                    },
                    timeout=10,
                    retries=0,
                )
                for item in payload if isinstance(payload, list) else []:
                    latitude = as_float(item.get("lat"))
                    longitude = as_float(item.get("lon"))
                    if latitude is None or longitude is None:
                        continue
                    address = item.get("address") or {}
                    name = str(
                        item.get("name")
                        or address.get("city")
                        or address.get("town")
                        or address.get("village")
                        or item.get("display_name")
                        or ""
                    )
                    region = str(address.get("state") or address.get("province") or "")
                    country = str(address.get("country") or "")
                    results.append(
                        {
                            "name": name,
                            "display_name": str(item.get("display_name") or name),
                            "latitude": latitude,
                            "longitude": longitude,
                            "region": region,
                            "country": country,
                            "timezone": "",
                            "source": "nominatim",
                        }
                    )
            except Exception as exc:
                if not results:
                    raise LocationError(f"城市搜索失败：{exc}") from exc

        return results[:limit]

    # ------------------------------------------------------------------
    # IP providers
    # ------------------------------------------------------------------

    def _ipwho(self) -> Optional[Location]:
        payload = http_get_json(
            "https://ipwho.is/",
            timeout=10,
            retries=1,
        )
        if not isinstance(payload, dict) or payload.get("success") is False:
            return None
        latitude = as_float(payload.get("latitude"))
        longitude = as_float(payload.get("longitude"))
        if latitude is None or longitude is None:
            return None
        timezone_data = payload.get("timezone") or {}
        return Location(
            latitude=latitude,
            longitude=longitude,
            city=str(payload.get("city") or ""),
            region=str(payload.get("region") or ""),
            country=str(payload.get("country") or ""),
            timezone=str(timezone_data.get("id") or "") if isinstance(timezone_data, dict) else "",
        )

    def _ipapi(self) -> Optional[Location]:
        payload = http_get_json("https://ipapi.co/json/", timeout=10, retries=0)
        if not isinstance(payload, dict) or payload.get("error"):
            return None
        latitude = as_float(payload.get("latitude"))
        longitude = as_float(payload.get("longitude"))
        if latitude is None or longitude is None:
            return None
        return Location(
            latitude=latitude,
            longitude=longitude,
            city=str(payload.get("city") or ""),
            region=str(payload.get("region") or ""),
            country=str(payload.get("country_name") or ""),
            timezone=str(payload.get("timezone") or ""),
        )

    def _ipsb(self) -> Optional[Location]:
        payload = http_get_json("https://api.ip.sb/geoip", timeout=10, retries=0)
        if not isinstance(payload, dict):
            return None
        latitude = as_float(payload.get("latitude"))
        longitude = as_float(payload.get("longitude"))
        if latitude is None or longitude is None:
            return None
        return Location(
            latitude=latitude,
            longitude=longitude,
            city=str(payload.get("city") or ""),
            region=str(payload.get("region") or ""),
            country=str(payload.get("country") or ""),
            timezone=str(payload.get("timezone") or ""),
        )

    def _ipinfo(self) -> Optional[Location]:
        payload = http_get_json("https://ipinfo.io/json", timeout=10, retries=0)
        if not isinstance(payload, dict):
            return None
        loc = str(payload.get("loc") or "")
        if "," not in loc:
            return None
        lat_text, lon_text = loc.split(",", 1)
        latitude = as_float(lat_text)
        longitude = as_float(lon_text)
        if latitude is None or longitude is None:
            return None
        return Location(
            latitude=latitude,
            longitude=longitude,
            city=str(payload.get("city") or ""),
            region=str(payload.get("region") or ""),
            country=str(payload.get("country") or ""),
            timezone=str(payload.get("timezone") or ""),
        )

    def _ipapi_com(self) -> Optional[Location]:
        payload = http_get_json(
            "http://ip-api.com/json/",
            {"fields": "status,message,country,regionName,city,lat,lon,timezone", "lang": "zh-CN"},
            timeout=10,
            retries=0,
        )
        if not isinstance(payload, dict) or payload.get("status") != "success":
            return None
        latitude = as_float(payload.get("lat"))
        longitude = as_float(payload.get("lon"))
        if latitude is None or longitude is None:
            return None
        return Location(
            latitude=latitude,
            longitude=longitude,
            city=str(payload.get("city") or ""),
            region=str(payload.get("regionName") or ""),
            country=str(payload.get("country") or ""),
            timezone=str(payload.get("timezone") or ""),
        )

    # ------------------------------------------------------------------

    def _from_device(self, data: Dict[str, Any]) -> Optional[Location]:
        latitude = as_float(data.get("latitude"))
        longitude = as_float(data.get("longitude"))
        if latitude is None or longitude is None:
            return None
        location = Location(
            latitude=latitude,
            longitude=longitude,
            name=str(data.get("name") or ""),
            timezone=str(data.get("timezone") or ""),
            source="device",
        )
        if not location.name:
            info = self.reverse_geocode(latitude, longitude, location.timezone)
            _apply_reverse(location, info)
        return location


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in str(text or ""))


def _prefer_text(existing: str, incoming: str) -> str:
    existing = (existing or "").strip()
    incoming = (incoming or "").strip()
    if not incoming:
        return existing
    if not existing:
        return incoming
    # IP services often return an English city while the reverse-geocoder has
    # the localized Chinese name. Prefer the localized value in that case.
    if _has_cjk(incoming) and not _has_cjk(existing):
        return incoming
    return existing


def _apply_reverse(location: Location, info: Dict[str, str]) -> None:
    if not info:
        return
    if location.name == "自定义位置":
        location.name = ""
    location.name = _prefer_text(location.name, info.get("name", "") or info.get("city", ""))
    location.city = _prefer_text(location.city, info.get("city", ""))
    location.district = _prefer_text(location.district, info.get("district", ""))
    location.region = _prefer_text(location.region, info.get("region", ""))
    location.country = _prefer_text(location.country, info.get("country", ""))
