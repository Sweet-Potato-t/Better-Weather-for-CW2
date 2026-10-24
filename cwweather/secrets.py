"""Windows DPAPI helpers for API credentials at rest.

Class Widgets 2 runs on Windows, so credentials are encrypted with the current
user's DPAPI key instead of being written to configs.json as plain text.  The
prefix makes legacy plain-text values readable and lets them be migrated on the
next load.
"""

from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes

PREFIX = "dpapi:"
CRYPTPROTECT_UI_FORBIDDEN = 0x01


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def available() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def is_protected(value: str) -> bool:
    return str(value or "").startswith(PREFIX)


def protect(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if is_protected(text):
        return text
    if not available():
        raise RuntimeError("当前系统不支持 Windows DPAPI")
    raw = text.encode("utf-8")
    in_blob = _Blob(len(raw), ctypes.cast(ctypes.create_string_buffer(raw), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _Blob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return PREFIX + base64.urlsafe_b64encode(encrypted).decode("ascii")


def unprotect(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if not is_protected(text):
        return text
    if not available():
        raise RuntimeError("当前系统不支持 Windows DPAPI")
    try:
        encrypted = base64.urlsafe_b64decode(text[len(PREFIX):].encode("ascii"))
    except Exception:
        return ""
    in_blob = _Blob(len(encrypted), ctypes.cast(ctypes.create_string_buffer(encrypted), ctypes.POINTER(ctypes.c_byte)))
    out_blob = _Blob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob),
    )
    if not ok:
        return ""
    try:
        raw = ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
    return raw.decode("utf-8", "replace")
