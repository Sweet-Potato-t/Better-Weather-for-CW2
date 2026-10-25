"""Small helpers shared by the weather providers.

The plugin deliberately only uses the Python standard library at runtime so it
can be dropped into Class Widgets 2 without installing extra packages.
"""

from __future__ import annotations

import gzip
import json
import math
import re
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

try:  # certifi is commonly shipped with Qt/Python distributions
    import certifi  # type: ignore
except Exception:  # pragma: no cover - optional
    certifi = None


USER_AGENT = (
    "ClassWidgets-Weather/1.2.0 "
    "(Class Widgets 2 plugin; +https://github.com/Class-Widgets/plugin-template-v2)"
)


class WeatherError(Exception):
    """Base error for all weather failures."""


class ProviderError(WeatherError):
    """A single provider could not return usable data."""


class NetworkError(WeatherError):
    """Network/HTTP failure."""


def _ssl_context() -> ssl.SSLContext:
    try:
        if certifi is not None:
            return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    return ssl.create_default_context()


_SSL_CONTEXT = None


def _get_ssl_context() -> ssl.SSLContext:
    global _SSL_CONTEXT
    if _SSL_CONTEXT is None:
        _SSL_CONTEXT = _ssl_context()
    return _SSL_CONTEXT


def quote(value: Any) -> str:
    return urllib.parse.quote(str(value), safe=",")


def build_url(base: str, params: Optional[Dict[str, Any]] = None) -> str:
    if not params:
        return base
    clean = {key: value for key, value in params.items() if value is not None}
    joiner = "&" if "?" in base else "?"
    return base + joiner + urllib.parse.urlencode(clean, doseq=True)


def http_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 12.0,
    retries: int = 2,
) -> Any:
    """GET a JSON document with a small, predictable retry policy.

    A retry only happens for transport errors and 5xx responses. 4xx responses
    are returned to the caller immediately because retrying an invalid API key
    or an unsupported coordinate only wastes the user's time.
    """

    full_url = build_url(url, params)
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain;q=0.8, */*;q=0.5",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        request_headers.update({key: value for key, value in headers.items() if value})

    last_error: Optional[BaseException] = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(full_url, headers=request_headers, method="GET")
        try:
            with urllib.request.urlopen(
                request, timeout=timeout, context=_get_ssl_context()
            ) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read()
                encoding = (response.headers.get("Content-Encoding") or "").lower()
                if "gzip" in encoding:
                    raw = gzip.decompress(raw)
                elif "deflate" in encoding:
                    try:
                        raw = zlib.decompress(raw)
                    except zlib.error:
                        raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            text = raw.decode(charset, errors="replace").strip()
            if not text:
                raise NetworkError("服务器返回了空响应")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                snippet = text[:180].replace("\n", " ")
                raise NetworkError(f"服务器返回的内容不是 JSON：{snippet}") from exc
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            detail = f"HTTP {exc.code}"
            if body:
                detail += f"：{body.strip()}"
            if exc.code >= 500 and attempt < retries:
                last_error = NetworkError(detail)
                time.sleep(0.5 * (attempt + 1))
                continue
            raise NetworkError(detail) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
            last_error = NetworkError(f"网络请求失败：{getattr(exc, 'reason', exc)}")
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise last_error from exc
        except OSError as exc:
            last_error = NetworkError(f"网络请求失败：{exc}")
            if attempt < retries:
                time.sleep(0.5 * (attempt + 1))
                continue
            raise last_error from exc
    raise last_error or NetworkError("网络请求失败")


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return default
    try:
        result = float(str(value).strip().replace("°C", "").replace("°F", ""))
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    number = as_float(value)
    if number is None:
        return default
    try:
        return int(round(number))
    except (TypeError, ValueError):
        return default


def first(value: Any, default: Any = None) -> Any:
    if isinstance(value, (list, tuple)) and value:
        return value[0]
    return default


def dig(value: Any, *path: Any, default: Any = None) -> Any:
    current = value
    for key in path:
        if current is None:
            return default
        if isinstance(key, int):
            if not isinstance(current, (list, tuple)) or key >= len(current):
                return default
            current = current[key]
        elif isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return default if current is None else current


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        number = int(text)
        if number > 10**12:
            number /= 1000.0
        try:
            return datetime.fromtimestamp(number, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = text.replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(text)
    except ValueError:
        for pattern in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%I:%M %p",
            "%I:%M:%S %p",
            "%H:%M",
        ):
            try:
                result = datetime.strptime(text, pattern)
                break
            except ValueError:
                result = None
        if result is None:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def alert_time_text(value: Any) -> str:
    """Month/day + time for compact alert timestamps."""
    parsed = parse_datetime(value)
    if parsed is None:
        text = str(value or "").strip()
        return text
    return f"{parsed.month}月{parsed.day}日 {parsed.strftime('%H:%M')}"


def short_time(value: Any) -> str:
    dt = parse_datetime(value)
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


def iso_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def compact_text(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        return text[: max(0, limit - 1)] + "…"
    return text


def weekday_cn(date_text: str) -> str:
    labels = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
    try:
        date = datetime.strptime(date_text[:10], "%Y-%m-%d")
        return labels[date.weekday()]
    except ValueError:
        return ""


def today_text(timezone_name: str = "") -> str:
    try:
        from zoneinfo import ZoneInfo

        zone = ZoneInfo(timezone_name) if timezone_name else None
        return datetime.now(zone).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
