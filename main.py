"""Better Weather for CW2.

The Qt-facing layer is deliberately thin: network calls and provider fallback
run in a daemon thread, and QML receives immutable dictionaries through queued
signals.  The widget and the settings page both use the same backend object.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Property, QTimer, Qt, Signal, Slot

from ClassWidgets.SDK import CW2Plugin, PluginAPI

from cwweather import secrets as secret_store
from cwweather.config import WeatherConfig
from cwweather.formatting import high_low_text, temp_text, unit_symbol
from cwweather.models import WeatherSnapshot
from cwweather.service import WeatherService
from cwweather.util import alert_time_text, short_time

try:
    from loguru import logger  # type: ignore
except Exception:  # pragma: no cover - CW2 always ships loguru
    import logging

    logger = logging.getLogger("classwidgets.weather")


PLUGIN_ID = "com.sweetpotato.weather"
WIDGET_ID = "com.sweetpotato.weather.widget"
_BOOL_FIELDS = {
    "animation_enabled",
    "fallback_enabled",
    "auto_location",
    "show_location",
    "show_provider",
    "widget_show_hourly",
    "widget_show_precip",
    "widget_carousel",
    "widget_tomorrow_enabled",
}
_INT_FIELDS = {"refresh_interval", "cycle_interval", "timeout", "widget_main_seconds"}
_FLOAT_FIELDS = {"manual_lat", "manual_lon"}
_STRING_FIELDS = {
    "source",
    "location_strategy",
    "manual_city",
    "manual_region",
    "manual_country",
    "manual_timezone",
    "temperature_unit",
    "widget_content_mode",
    "widget_tomorrow_start",
    "widget_tomorrow_end",
    "qweather_api_key",
    "qweather_host",
    "openweathermap_api_key",
    "weatherapi_api_key",
    "caiyun_api_key",
}
_FIELDS = _BOOL_FIELDS | _INT_FIELDS | _FLOAT_FIELDS | _STRING_FIELDS
SECRET_FIELDS = {
    "qweather_api_key",
    "openweathermap_api_key",
    "weatherapi_api_key",
    "caiyun_api_key",
}


def _config_fields() -> set[str]:
    fields = getattr(WeatherConfig, "model_fields", None)
    if isinstance(fields, dict):
        return set(fields.keys())
    annotations = getattr(WeatherConfig, "__annotations__", None)
    return set(annotations.keys()) if isinstance(annotations, dict) else set()


class Plugin(CW2Plugin):
    weatherChanged = Signal()
    alertsChanged = Signal()
    slidesChanged = Signal()
    configChanged = Signal()
    loadingChanged = Signal()
    statusChanged = Signal()
    searchingChanged = Signal()
    searchResultsChanged = Signal()

    _result_ready = Signal(object)
    _search_ready = Signal(int, object, str)

    def __init__(self, api: PluginAPI):
        super().__init__(api)
        self.config = WeatherConfig()
        self.service = WeatherService()

        self._state_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._alive = True
        self._worker: Optional[threading.Thread] = None
        self._next_refresh = 0.0
        self._force_ip_next = False

        self._payload: Dict[str, Any] = self._empty_payload("正在获取天气…")
        self._alerts: List[Dict[str, Any]] = []
        self._slides: List[Dict[str, Any]] = [self._placeholder_slide("正在获取天气…")]
        self._last_snapshot: Optional[WeatherSnapshot] = None
        self._loading = False
        self._status_text = "正在准备…"
        self._error_text = ""
        self._last_updated_text = ""
        self._device_location: Optional[Dict[str, Any]] = None
        self._device_status = "尚未请求设备定位"
        self._position_source = None
        self._device_request_id = 0

        self._searching = False
        self._search_results: List[Dict[str, Any]] = []
        self._search_error = ""
        self._search_token = 0

        self._result_ready.connect(self._on_result_ready, Qt.ConnectionType.QueuedConnection)
        self._search_ready.connect(self._on_search_ready, Qt.ConnectionType.QueuedConnection)

        self._provider_catalog = WeatherService.catalog()
        self._field_names = _config_fields() or set(_FIELDS)

    # ------------------------------------------------------------------
    # CW2 lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        super().on_load()
        if self.pid is None:
            logger.warning("Weather plugin is missing meta.id")
            return
        logger.info(
            "Better Weather loaded: id=%s version=%s source=%s",
            self.pid, self.meta.get("version", "?"), getattr(self.config, "source", "?"),
        )

        try:
            self.api.config.register_plugin_model(self.pid, self.config)
            self._migrate_secrets()
        except Exception:
            logger.exception("Failed to register weather plugin config")

        try:
            self.api.widgets.register(
                widget_id=WIDGET_ID,
                name="Better Weather",
                qml_path=self.PATH / "assets" / "qml" / "WeatherWidget.qml",
                backend_obj=self,
            )
        except Exception:
            logger.exception("Failed to register weather widget")

        try:
            self.api.ui.register_settings_page(
                qml_path=self.PATH / "assets" / "qml" / "WeatherSettings.qml",
                title="Better Weather",
                icon="ic_fluent_weather_sunny_20_regular",
            )
        except Exception:
            logger.exception("Failed to register weather settings page")

        self._start_worker()
        if self._should_use_device():
            self._request_device_location()
        self._request_refresh()

    def on_unload(self) -> None:
        logger.info("Better Weather unloading")
        self._alive = False
        try:
            if self._position_source is not None:
                self._position_source.stopUpdates()
        except Exception:
            pass
        self._position_source = None
        self._stop_worker()
        try:
            self.api.ui.unregister_settings_page(
                self.PATH / "assets" / "qml" / "WeatherSettings.qml"
            )
        except Exception:
            logger.debug("Weather settings page was already removed")

    # ------------------------------------------------------------------
    # Worker thread
    # ------------------------------------------------------------------

    def _start_worker(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(
            target=self._worker_loop, name="cw2-weather", daemon=True
        )
        self._worker.start()

    def _stop_worker(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        worker = self._worker
        if worker and worker.is_alive():
            worker.join(timeout=3.0)
        self._worker = None

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._state_lock:
                    next_at = self._next_refresh
                now = time.monotonic()
                if next_at <= now:
                    self._perform_refresh()
                    interval = self._config_int("refresh_interval", 15, 1, 1440)
                    with self._state_lock:
                        self._next_refresh = time.monotonic() + interval * 60.0
                    continue
                self._wake_event.wait(timeout=min(max(0.2, next_at - now), 30.0))
                self._wake_event.clear()
            except Exception:
                logger.exception("Unexpected weather worker error")
                time.sleep(2.0)

    def _perform_refresh(self) -> None:
        config = self._service_config()
        logger.info(
            "Weather refresh started: source=%s auto_location=%s",
            config.get("source"), config.get("auto_location", True),
        )
        with self._state_lock:
            device = dict(self._device_location) if self._device_location else None
            force_ip = self._force_ip_next
            self._force_ip_next = False
        try:
            snapshot, attempts = self.service.refresh(
                config, device_location=device, force_ip=force_ip
            )
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            logger.warning("Weather refresh failed: %s", message)
            if self._alive:
                self._result_ready.emit(
                    {
                        "ok": False,
                        "error": message,
                        "attempts": [],
                        "device_location": device,
                    }
                )
            return
        logger.info(
            "Weather refresh succeeded: provider=%s temp=%s daily=%d hourly=%d alerts=%d precip=%s",
            snapshot.provider_name, snapshot.current_temp_c, len(snapshot.daily),
            len(snapshot.hourly), len(snapshot.alerts),
            bool((snapshot.precipitation or {}).get("active")),
        )
        if self._alive:
            self._result_ready.emit(
                {
                    "ok": True,
                    "snapshot": snapshot,
                    "attempts": attempts,
                    "device_location": device,
                }
            )

    # ------------------------------------------------------------------
    # Result handling (main/QML thread)
    # ------------------------------------------------------------------

    def _on_result_ready(self, result: Dict[str, Any]) -> None:
        self._set_loading(False)
        if not isinstance(result, dict):
            return
        if result.get("ok") and isinstance(result.get("snapshot"), WeatherSnapshot):
            snapshot: WeatherSnapshot = result["snapshot"]
            self._last_snapshot = snapshot
            self._error_text = ""
            self._publish_snapshot(snapshot)
            provider = snapshot.provider_name
            if snapshot.fallback_used:
                self._status_text = f"已使用备用数据源 · {provider}"
            else:
                self._status_text = f"已更新 · {self._last_updated_text or '刚刚'}"
            self.statusChanged.emit()
            return

        error = str(result.get("error") or "获取天气失败")
        self._error_text = error
        self._status_text = "更新失败"
        if self._last_snapshot is not None:
            # Keep old data visible, but mark it as stale so the settings page can
            # explain why the timestamp is not changing.
            self._publish_snapshot(self._last_snapshot, stale=True, error=error)
        else:
            self._payload = self._empty_payload(error)
            self._alerts = []
            self._slides = [self._placeholder_slide("天气获取失败", "打开插件设置检查网络或数据源")]
            self._last_updated_text = ""
            self.weatherChanged.emit()
            self.alertsChanged.emit()
            self.slidesChanged.emit()
        self.statusChanged.emit()

    def _publish_snapshot(
        self, snapshot: WeatherSnapshot, *, stale: bool = False, error: str = ""
    ) -> None:
        unit = str(self.config.temperature_unit or "celsius")
        payload = snapshot.to_payload(unit=unit, stale=stale)
        if error:
            payload["error"] = error
        self._payload = payload
        self._alerts = list(payload.get("alerts") or [])
        self._slides = self._build_slides(snapshot, unit)
        self._last_updated_text = str(payload.get("updated_text") or "")
        self.weatherChanged.emit()
        self.alertsChanged.emit()
        self.slidesChanged.emit()

    def _build_slides(self, snapshot: WeatherSnapshot, unit: str) -> List[Dict[str, Any]]:
        if snapshot.alerts:
            slides = []
            for alert in snapshot.alerts:
                meta_parts = [part for part in (alert.sender, alert_time_text(alert.pub_time)) if part]
                if alert.type and alert.level:
                    concise_title = f"{alert.type} {alert.level_text}".strip()
                elif alert.type:
                    concise_title = f"{alert.type}预警"
                else:
                    concise_title = alert.short_title
                slides.append(
                    {
                        "kind": "alert",
                        "icon": alert.icon,
                        "value": alert.level_text,
                        "title": concise_title,
                        "meta": self._short_meta(meta_parts),
                        "color": alert.color,
                        "severity": alert.severity,
                    }
                )
            return slides

        return [
            {
                "kind": "weather",
                "icon": snapshot.icon,
                "value": temp_text(snapshot.current_temp_c, unit),
                "title": snapshot.condition or "天气",
                "meta": high_low_text(snapshot.high_c, snapshot.low_c, unit),
                "color": "#0078D4",
                "severity": 0,
            }
        ]

    @staticmethod
    def _short_meta(parts: List[str]) -> str:
        clean = []
        for part in parts:
            text = str(part or "").strip()
            if text and text not in clean:
                clean.append(text)
        if len(clean) >= 2:
            return f"{clean[0]} · {clean[1]}"
        return clean[0] if clean else ""

    def _empty_payload(self, message: str = "") -> Dict[str, Any]:
        return {
            "ok": False,
            "available": False,
            "provider": {"id": "", "name": ""},
            "location": {
                "display_name": "",
                "name": "",
                "city": "",
                "region": "",
                "country": "",
                "source": "",
                "latitude": 0,
                "longitude": 0,
                "timezone": "",
            },
            "current": {
                "temp": None,
                "temp_text": "--°",
                "feels_like": None,
                "feels_like_text": "--°",
                "text": message or "暂无数据",
                "icon": "unknown",
                "code": "",
                "is_day": True,
                "humidity": None,
                "wind_dir": "",
                "wind_scale": "",
                "wind_speed": None,
                "wind_text": "",
                "pressure": None,
                "visibility": None,
                "aqi": None,
                "obs_time": "",
            },
            "today": {
                "date": "",
                "high": None,
                "low": None,
                "high_text": "--°",
                "low_text": "--°",
                "text": "",
                "icon": "unknown",
                "sunrise": "",
                "sunset": "",
            },
            "daily": [],
            "hourly": [],
            "alerts": [],
            "precipitation": {},
            "alert_count": 0,
            "unit": unit_symbol(str(getattr(self.config, "temperature_unit", "celsius"))),
            "updated_at": "",
            "updated_text": "",
            "stale": False,
            "fallback_used": False,
            "attempts": [],
            "details": [],
            "error": message,
        }

    @staticmethod
    def _placeholder_slide(
        title: str, meta: str = "请稍候…"
    ) -> Dict[str, Any]:
        return {
            "kind": "weather",
            "icon": "unknown",
            "value": "--°",
            "title": title,
            "meta": meta,
            "color": "#0078D4",
            "severity": 0,
        }

    def _set_loading(self, value: bool) -> None:
        if self._loading != value:
            self._loading = value
            self.loadingChanged.emit()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def _config_snapshot(self, *, redact: bool = True) -> Dict[str, Any]:
        try:
            data = self.config.model_dump()
        except Exception:
            data = dict(getattr(self.config, "__dict__", {}))
        defaults = WeatherConfig()
        try:
            for key, value in defaults.model_dump().items():
                data.setdefault(key, value)
        except Exception:
            pass
        for field in SECRET_FIELDS:
            value = str(data.get(field) or "").strip()
            data[f"{field}_set"] = bool(value)
            if redact:
                data[field] = ""
        return data

    def _service_config(self) -> Dict[str, Any]:
        data = self._config_snapshot(redact=False)
        for field in SECRET_FIELDS:
            try:
                data[field] = secret_store.unprotect(str(data.get(field) or ""))
            except Exception:
                logger.exception(f"Failed to decrypt {field}")
                data[field] = ""
        return data

    def _migrate_secrets(self) -> None:
        changed = 0
        for field in SECRET_FIELDS:
            raw = str(getattr(self.config, field, "") or "").strip()
            if not raw or secret_store.is_protected(raw):
                continue
            try:
                setattr(self.config, field, secret_store.protect(raw))
                changed += 1
            except Exception:
                logger.exception(f"Failed to encrypt {field}; leaving legacy value")
        if changed:
            self._save_config()
            logger.info("Encrypted %d legacy API credential(s) with Windows DPAPI", changed)

    def _config_int(self, key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(getattr(self.config, key, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    @Property("QVariant", notify=configChanged)
    def settings(self) -> Dict[str, Any]:
        return self._config_snapshot()

    @Property(str, constant=True)
    def pluginVersion(self) -> str:
        return str(self.meta.get("version") or "")

    @Property("QVariantList", notify=configChanged)
    def providers(self) -> List[Dict[str, object]]:
        return self._provider_catalog

    @Property(int, notify=configChanged)
    def providerIndex(self) -> int:
        current = str(getattr(self.config, "source", "open-meteo"))
        for index, item in enumerate(self._provider_catalog):
            if item.get("id") == current:
                return index
        return 0

    @Slot(str, "QVariant")
    def setOption(self, key: str, value: Any) -> None:
        if key not in self._field_names or key not in _FIELDS:
            return
        try:
            if key in SECRET_FIELDS:
                text = str(value or "").strip()
                if not text:
                    return
                coerced = secret_store.protect(text)
            else:
                coerced = self._coerce(key, value)
            old_value = getattr(self.config, key, None)
            setattr(self.config, key, coerced)
            if old_value == coerced:
                # Still save once: some QML controls write the same value during
                # initialization and the config manager should be consistent.
                self._save_config()
                return
        except Exception:
            logger.exception(f"Failed to set weather option {key}")
            return

        self._save_config()
        if key in SECRET_FIELDS:
            logger.info("Weather setting updated: %s=<encrypted>", key)
        else:
            logger.info("Weather setting updated: %s=%r", key, coerced)
        self.configChanged.emit()
        self._after_config_change(key)

    def _coerce(self, key: str, value: Any) -> Any:
        if key in _BOOL_FIELDS:
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on", "是")
            return bool(value)
        if key in _INT_FIELDS:
            try:
                number = int(round(float(value)))
            except (TypeError, ValueError):
                number = 0
            if key == "refresh_interval":
                return max(1, min(1440, number))
            if key == "cycle_interval":
                return max(1, min(300, number))
            if key == "timeout":
                return max(5, min(45, number))
            if key == "widget_main_seconds":
                return max(3, min(60, number))
            return number
        if key in _FLOAT_FIELDS:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = 0.0
            if key == "manual_lat":
                return max(-90.0, min(90.0, number))
            if key == "manual_lon":
                return max(-180.0, min(180.0, number))
            return number
        text = str(value or "").strip()
        if key == "source":
            ids = {str(item.get("id")) for item in self._provider_catalog}
            return text if text in ids else "open-meteo"
        if key == "location_strategy":
            return text if text in ("auto", "ip", "device") else "auto"
        if key == "temperature_unit":
            return "fahrenheit" if text.lower().startswith("f") else "celsius"
        if key == "qweather_host":
            return text
        if key in ("widget_tomorrow_start", "widget_tomorrow_end"):
            if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", text):
                return text
            return "20:00" if key == "widget_tomorrow_start" else "23:59"
        return text

    def _after_config_change(self, key: str) -> None:
        if key in (
            "cycle_interval", "animation_enabled", "show_location", "show_provider",
            "widget_content_mode", "widget_show_hourly", "widget_show_precip",
            "widget_carousel", "widget_main_seconds",
            "widget_tomorrow_enabled", "widget_tomorrow_start",
            "widget_tomorrow_end",
        ):
            return
        if key == "temperature_unit":
            if self._last_snapshot is not None:
                self._publish_snapshot(
                    self._last_snapshot,
                    stale=bool(self._payload.get("stale")),
                    error=str(self._payload.get("error") or ""),
                )
            return
        if key == "refresh_interval":
            interval = self._config_int("refresh_interval", 15, 1, 1440)
            with self._state_lock:
                self._next_refresh = time.monotonic() + interval * 60.0
            self._wake_event.set()
            return
        if key in ("auto_location", "location_strategy"):
            if self._should_use_device():
                self._request_device_location()
        self._request_refresh()

    def _set_options(self, values: Dict[str, Any], *, refresh: bool = True) -> None:
        changed = False
        for key, value in values.items():
            if key not in self._field_names or key not in _FIELDS:
                continue
            try:
                coerced = self._coerce(key, value)
                if getattr(self.config, key, None) != coerced:
                    setattr(self.config, key, coerced)
                    changed = True
            except Exception:
                logger.exception(f"Failed to apply weather option {key}")
        self._save_config()
        if changed:
            self.configChanged.emit()
        if refresh:
            self._request_refresh()

    def _save_config(self) -> None:
        try:
            self.api.config.save()
        except Exception:
            logger.debug("Weather config save failed (the config manager may still persist it)")

    # ------------------------------------------------------------------
    # Public QML slots
    # ------------------------------------------------------------------

    @Slot()
    def refreshNow(self) -> None:
        self._request_refresh()

    @Slot()
    def relocate(self) -> None:
        try:
            self.service.locations.invalidate_ip()
        except Exception:
            pass
        with self._state_lock:
            self._force_ip_next = True
        if self._should_use_device():
            self._device_location = None
            self._request_device_location()
        self._request_refresh()

    @Slot(str)
    def searchLocations(self, query: str) -> None:
        query = str(query or "").strip()
        if not query:
            self._search_results = []
            self._search_error = "请输入城市名称"
            self._searching = False
            self.searchingChanged.emit()
            self.searchResultsChanged.emit()
            return
        self._search_token += 1
        token = self._search_token
        self._searching = True
        self._search_error = ""
        self._search_results = []
        self.searchingChanged.emit()
        self.searchResultsChanged.emit()
        thread = threading.Thread(
            target=self._search_worker, args=(token, query), name="cw2-weather-search", daemon=True
        )
        thread.start()

    def _search_worker(self, token: int, query: str) -> None:
        try:
            results = self.service.search(query)
            if self._alive:
                self._search_ready.emit(token, results, "")
        except Exception as exc:
            if self._alive:
                self._search_ready.emit(token, [], str(exc))

    def _on_search_ready(self, token: int, results: object, error: str) -> None:
        if token != self._search_token:
            return
        self._search_results = list(results or []) if isinstance(results, list) else []
        self._search_error = str(error or "")
        self._searching = False
        self.searchingChanged.emit()
        self.searchResultsChanged.emit()

    @Slot(int)
    def chooseSearchResult(self, index: int) -> None:
        if index < 0 or index >= len(self._search_results):
            return
        item = self._search_results[index]
        try:
            latitude = float(item.get("latitude"))
            longitude = float(item.get("longitude"))
        except (TypeError, ValueError):
            return
        self._set_options(
            {
                "auto_location": False,
                "manual_city": str(item.get("name") or ""),
                "manual_lat": latitude,
                "manual_lon": longitude,
                "manual_region": str(item.get("region") or ""),
                "manual_country": str(item.get("country") or ""),
                "manual_timezone": str(item.get("timezone") or "Asia/Shanghai"),
            }
        )
        self._search_results = []
        self.searchResultsChanged.emit()

    @Slot(float, float, str)
    def setManualLocation(self, latitude: float, longitude: float, name: str) -> None:
        self._set_options(
            {
                "auto_location": False,
                "manual_city": str(name or "自定义位置").strip() or "自定义位置",
                "manual_lat": max(-90.0, min(90.0, float(latitude))),
                "manual_lon": max(-180.0, min(180.0, float(longitude))),
            }
        )

    @Slot()
    def clearSearchResults(self) -> None:
        self._search_results = []
        self._search_error = ""
        self.searchResultsChanged.emit()

    def _request_refresh(self) -> None:
        if not self._alive:
            return
        if not self._worker or not self._worker.is_alive():
            self._start_worker()
        self._set_loading(True)
        if not self._status_text.startswith("正在更新"):
            self._status_text = "正在更新…"
            self.statusChanged.emit()
        with self._state_lock:
            self._next_refresh = 0.0
        self._wake_event.set()

    # ------------------------------------------------------------------
    # Device location (Qt Positioning)
    # ------------------------------------------------------------------

    def _should_use_device(self) -> bool:
        try:
            return bool(self.config.auto_location) and str(self.config.location_strategy) in (
                "auto",
                "device",
            )
        except Exception:
            return False

    def _request_device_location(self) -> None:
        self._device_request_id += 1
        request_id = self._device_request_id
        self._device_status = "正在请求设备定位…"
        self.statusChanged.emit()
        try:
            from PySide6.QtPositioning import QGeoPositionInfoSource
        except Exception as exc:
            self._device_status = f"设备定位不可用（{exc.__class__.__name__}），将使用公网 IP"
            self.statusChanged.emit()
            return
        try:
            if self._position_source is not None:
                try:
                    self._position_source.stopUpdates()
                except Exception:
                    pass
            source = QGeoPositionInfoSource.createDefaultSource(self)
            if source is None:
                self._device_status = "系统未提供定位源，将使用公网 IP"
                self.statusChanged.emit()
                return
            self._position_source = source
            source.setUpdateInterval(60000)
            source.positionUpdated.connect(
                lambda info: self._on_device_position(request_id, info)
            )
            source.errorOccurred.connect(
                lambda *args: self._on_device_error(request_id, args)
            )
            started = source.requestUpdate(12000)
            if not started:
                self._device_status = "设备定位请求未能启动，将使用公网 IP"
                self.statusChanged.emit()
        except Exception as exc:
            self._device_status = f"设备定位出错（{exc.__class__.__name__}），将使用公网 IP"
            self.statusChanged.emit()
            return
        QTimer.singleShot(12500, lambda: self._on_device_timeout(request_id))

    def _on_device_position(self, request_id: int, info: Any) -> None:
        if request_id != self._device_request_id:
            return
        try:
            coordinate = info.coordinate()
            if not coordinate.isValid():
                return
            latitude = float(coordinate.latitude())
            longitude = float(coordinate.longitude())
        except Exception:
            return
        with self._state_lock:
            self._device_location = {
                "latitude": latitude,
                "longitude": longitude,
                "source": "device",
            }
        self._device_request_id += 1
        self._device_status = f"设备定位成功（{latitude:.3f}, {longitude:.3f}）"
        self.statusChanged.emit()
        try:
            if self._position_source is not None:
                self._position_source.stopUpdates()
        except Exception:
            pass
        self._request_refresh()

    def _on_device_error(self, request_id: int, args: Any) -> None:
        if request_id != self._device_request_id:
            return
        self._device_request_id += 1
        error = args[0] if args else "未知错误"
        self._device_status = f"设备定位失败（{error}），将使用公网 IP"
        self.statusChanged.emit()
        try:
            if self._position_source is not None:
                self._position_source.stopUpdates()
        except Exception:
            pass
        self._request_refresh()

    def _on_device_timeout(self, request_id: int) -> None:
        if request_id != self._device_request_id:
            return
        if self._device_location is not None:
            return
        self._device_request_id += 1
        self._device_status = "设备定位超时，将使用公网 IP"
        self.statusChanged.emit()
        try:
            if self._position_source is not None:
                self._position_source.stopUpdates()
        except Exception:
            pass
        self._request_refresh()

    # ------------------------------------------------------------------
    # QML properties
    # ------------------------------------------------------------------

    @Property("QVariant", notify=weatherChanged)
    def weather(self) -> Dict[str, Any]:
        return self._payload

    @Property("QVariantList", notify=alertsChanged)
    def alerts(self) -> List[Dict[str, Any]]:
        return self._alerts

    @Property("QVariantList", notify=slidesChanged)
    def slides(self) -> List[Dict[str, Any]]:
        return self._slides

    @Property(bool, notify=weatherChanged)
    def hasWeather(self) -> bool:
        return bool(self._payload.get("available"))

    @Property(bool, notify=alertsChanged)
    def hasAlerts(self) -> bool:
        return bool(self._alerts)

    @Property(int, notify=alertsChanged)
    def alertCount(self) -> int:
        return len(self._alerts)

    @Property(bool, notify=loadingChanged)
    def loading(self) -> bool:
        return self._loading

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(str, notify=statusChanged)
    def errorText(self) -> str:
        return self._error_text

    @Property(str, notify=weatherChanged)
    def locationText(self) -> str:
        location = self._payload.get("location") or {}
        return str(location.get("short_name") or location.get("display_name") or "")

    @Property(str, notify=weatherChanged)
    def locationSourceText(self) -> str:
        source = str((self._payload.get("location") or {}).get("source") or "")
        return {
            "device": "设备定位",
            "ip": "公网 IP",
            "manual": "手动位置",
        }.get(source, "未知来源")

    @Property(str, notify=weatherChanged)
    def lastUpdatedText(self) -> str:
        return self._last_updated_text

    @Property(str, notify=configChanged)
    def temperatureUnit(self) -> str:
        return unit_symbol(str(getattr(self.config, "temperature_unit", "celsius")))

    @Property(str, notify=statusChanged)
    def deviceStatusText(self) -> str:
        return self._device_status

    @Property(bool, notify=searchingChanged)
    def searching(self) -> bool:
        return self._searching

    @Property("QVariantList", notify=searchResultsChanged)
    def searchResults(self) -> List[Dict[str, Any]]:
        return self._search_results

    @Property(str, notify=searchResultsChanged)
    def searchError(self) -> str:
        return self._search_error or ""

    @Property(bool, notify=weatherChanged)
    def stale(self) -> bool:
        return bool(self._payload.get("stale"))


__all__ = ["Plugin"]
