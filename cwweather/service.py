"""Provider selection, fallback and location orchestration."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .location import LocationService
from .models import WeatherSnapshot
from .providers import FREE_PROVIDER_IDS, PROVIDERS, provider_catalog
from .util import ProviderError, WeatherError, dedupe


class WeatherService:
    def __init__(self) -> None:
        self.locations = LocationService()

    def refresh(
        self,
        config: Dict[str, Any],
        *,
        device_location: Optional[Dict[str, Any]] = None,
        force_ip: bool = False,
    ) -> Tuple[WeatherSnapshot, List[str]]:
        location = self.locations.resolve(
            config, device_location=device_location, force_ip=force_ip
        )
        selected = str(config.get("source") or "open-meteo")
        if selected not in PROVIDERS:
            selected = "open-meteo"

        chain = self._provider_chain(selected, config)
        attempts: List[str] = []
        fallback_enabled = bool(config.get("fallback_enabled", True))
        if not fallback_enabled:
            chain = [selected]

        for provider_id in chain:
            provider_class = PROVIDERS.get(provider_id)
            if provider_class is None:
                continue
            provider = provider_class()
            try:
                provider.validate(location, config)
                snapshot = provider.fetch(location, config)
            except Exception as exc:
                attempts.append(f"{provider.name}: {exc}")
                continue
            snapshot.fallback_used = provider_id != selected
            snapshot.attempts = list(attempts)
            return snapshot, attempts

        detail = "；".join(attempts[-3:]) if attempts else "没有可用的天气数据源"
        raise WeatherError(f"获取天气失败：{detail}")

    def search(self, query: str) -> List[Dict[str, Any]]:
        return self.locations.search(query)

    def _provider_chain(self, selected: str, config: Dict[str, Any]) -> List[str]:
        free = [provider_id for provider_id in FREE_PROVIDER_IDS if provider_id != selected]
        keyed: List[str] = []
        if str(config.get("qweather_api_key") or "").strip():
            keyed.append("qweather")
        if str(config.get("openweathermap_api_key") or "").strip():
            keyed.append("openweathermap")
        if str(config.get("weatherapi_api_key") or "").strip():
            keyed.append("weatherapi")
        if str(config.get("caiyun_api_key") or "").strip():
            keyed.append("caiyun")

        # Xiaomi is regional; put it after the global free sources when it is
        # used only as a fallback, but keep it first when explicitly selected.
        ordered = [selected, *free, *keyed]
        if selected == "xiaomi":
            ordered = [selected, *[item for item in free if item != "xiaomi"], *keyed]
        return dedupe(ordered)[:4]

    @staticmethod
    def catalog() -> List[Dict[str, object]]:
        return provider_catalog()


__all__ = ["WeatherService", "WeatherError", "ProviderError", "provider_catalog"]
