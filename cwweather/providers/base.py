"""Provider interface and shared validation helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..models import Alert, Location, WeatherSnapshot
from ..util import ProviderError, http_get_json


class WeatherProvider:
    id = "base"
    name = "Base"
    needs_key = False
    supports_alerts = False
    description = ""
    key_label = ""

    def validate(self, location: Location, config: Dict[str, Any]) -> None:
        """Raise ProviderError when this provider cannot serve this request."""

    def fetch(self, location: Location, config: Dict[str, Any]) -> WeatherSnapshot:
        raise NotImplementedError

    def _get_json(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        timeout = 12.0
        if config:
            try:
                timeout = max(5.0, min(45.0, float(config.get("timeout", 12))))
            except (TypeError, ValueError):
                timeout = 12.0
        return http_get_json(url, params, headers=headers, timeout=timeout)

    def _require_key(self, config: Dict[str, Any], name: str) -> str:
        key = str(config.get(name, "") or "").strip()
        if not key:
            raise ProviderError(f"未配置 {self.name} 的 API Key")
        return key

    @staticmethod
    def _base_snapshot(location: Location, **kwargs: Any) -> WeatherSnapshot:
        return WeatherSnapshot(location=location, **kwargs)

    @staticmethod
    def _alerts(raw: Any, source: str) -> list[Alert]:
        from ..models import normalize_alerts

        if isinstance(raw, dict):
            raw = raw.get("alert") or raw.get("alerts") or raw.get("warning") or []
        if not isinstance(raw, list):
            return []
        return normalize_alerts([item for item in raw if isinstance(item, dict)], source)
