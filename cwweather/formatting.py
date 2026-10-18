"""Temperature-unit conversion and display formatting."""

from __future__ import annotations

from typing import Optional


def unit_symbol(unit: str) -> str:
    return "°F" if str(unit).lower().startswith("f") else "°C"


def convert_temp(value: Optional[float], unit: str = "celsius") -> Optional[int]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if str(unit).lower().startswith("f"):
        number = number * 9.0 / 5.0 + 32.0
    return int(round(number))


def temp_text(
    value: Optional[float],
    unit: str = "celsius",
    *,
    already_converted: bool = False,
) -> str:
    if value is None:
        return "--°"
    number = int(round(float(value))) if already_converted else convert_temp(value, unit)
    if number is None:
        return "--°"
    return f"{number}°"


def high_low_text(high: Optional[float], low: Optional[float], unit: str = "celsius") -> str:
    return f"最高 {temp_text(high, unit)}   最低 {temp_text(low, unit)}"
