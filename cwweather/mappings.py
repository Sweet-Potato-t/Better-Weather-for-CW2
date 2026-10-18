"""Weather-code, condition and alert mappings.

The icon names returned here correspond to PNG files in ``assets/icons``.
Keeping the mapping in one module makes provider parsers small and consistent.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


# ---------------------------------------------------------------------------
# WMO weather interpretation codes (Open-Meteo)
# ---------------------------------------------------------------------------

WMO: Dict[int, Tuple[str, str]] = {
    0: ("sunny", "晴"),
    1: ("sunny", "大部晴朗"),
    2: ("partly_cloudy", "多云"),
    3: ("overcast", "阴"),
    45: ("fog", "雾"),
    48: ("fog", "雾凇"),
    51: ("rain_light", "小毛毛雨"),
    53: ("rain_light", "毛毛雨"),
    55: ("rain", "强毛毛雨"),
    56: ("sleet", "冻毛毛雨"),
    57: ("sleet", "强冻毛毛雨"),
    61: ("rain_light", "小雨"),
    63: ("rain", "中雨"),
    65: ("rain_heavy", "大雨"),
    66: ("sleet", "冻雨"),
    67: ("sleet", "强冻雨"),
    71: ("snow", "小雪"),
    73: ("snow", "中雪"),
    75: ("snow", "大雪"),
    77: ("snow", "米雪"),
    80: ("rain_light", "阵雨"),
    81: ("rain", "强阵雨"),
    82: ("rain_heavy", "暴雨"),
    85: ("snow", "阵雪"),
    86: ("snow", "强阵雪"),
    95: ("thunder", "雷阵雨"),
    96: ("thunder", "雷阵雨伴冰雹"),
    99: ("thunder", "强雷暴伴冰雹"),
}


def wmo_info(code: Any) -> Tuple[str, str]:
    try:
        value = int(float(code))
    except (TypeError, ValueError):
        return "unknown", "未知天气"
    return WMO.get(value, ("unknown", "未知天气"))


def wmo_icon(code: Any, is_day: bool = True) -> str:
    icon, _ = wmo_info(code)
    return _day_night_icon(icon, is_day)


# ---------------------------------------------------------------------------
# WWO / wttr.in weather codes
# ---------------------------------------------------------------------------

WWO: Dict[int, Tuple[str, str]] = {
    113: ("sunny", "晴"),
    116: ("partly_cloudy", "多云"),
    119: ("cloudy", "阴"),
    122: ("overcast", "阴"),
    143: ("fog", "薄雾"),
    176: ("rain_light", "阵雨"),
    179: ("snow", "阵雪"),
    182: ("sleet", "雨夹雪"),
    185: ("sleet", "冻毛毛雨"),
    200: ("thunder", "雷阵雨"),
    227: ("snow", "吹雪"),
    230: ("snow", "暴雪"),
    248: ("fog", "雾"),
    260: ("fog", "冻雾"),
    263: ("rain_light", "小毛毛雨"),
    266: ("rain_light", "毛毛雨"),
    281: ("sleet", "冻毛毛雨"),
    284: ("sleet", "强冻毛毛雨"),
    293: ("rain_light", "局部小雨"),
    296: ("rain_light", "小雨"),
    299: ("rain", "间歇中雨"),
    302: ("rain", "中雨"),
    305: ("rain_heavy", "间歇大雨"),
    308: ("rain_heavy", "大雨"),
    311: ("sleet", "冻雨"),
    314: ("sleet", "强冻雨"),
    317: ("sleet", "小雨夹雪"),
    320: ("sleet", "中雨夹雪"),
    323: ("snow", "局部小雪"),
    326: ("snow", "小雪"),
    329: ("snow", "局部中雪"),
    332: ("snow", "中雪"),
    335: ("snow", "局部大雪"),
    338: ("snow", "大雪"),
    350: ("sleet", "冰粒"),
    353: ("rain_light", "阵雨"),
    356: ("rain", "强阵雨"),
    359: ("rain_heavy", "暴雨"),
    362: ("sleet", "阵性雨夹雪"),
    365: ("sleet", "强阵性雨夹雪"),
    368: ("snow", "阵雪"),
    371: ("snow", "强阵雪"),
    374: ("sleet", "冰粒阵"),
    377: ("sleet", "强冰粒阵"),
    386: ("thunder", "雷阵雨"),
    389: ("thunder", "强雷阵雨"),
    392: ("thunder", "雷阵雪"),
    395: ("thunder", "强雷阵雪"),
}


def wwo_info(code: Any, text: str = "") -> Tuple[str, str]:
    try:
        value = int(float(code))
    except (TypeError, ValueError):
        return "unknown", text or "未知天气"
    icon, fallback = WWO.get(value, ("unknown", text or "未知天气"))
    # wttr.in's zh translation is inconsistent; prefer our Chinese label unless
    # the provider returned an actual Chinese description.
    if text and any("\u4e00" <= char <= "\u9fff" for char in text):
        return icon, text
    return icon, fallback


def wwo_icon(code: Any, is_day: bool = True) -> str:
    icon, _ = wwo_info(code)
    return _day_night_icon(icon, is_day)


# ---------------------------------------------------------------------------
# QWeather icon ids
# ---------------------------------------------------------------------------

QWEATHER: Dict[str, Tuple[str, str]] = {
    "100": ("sunny", "晴"),
    "101": ("partly_cloudy", "多云"),
    "102": ("partly_cloudy", "少云"),
    "103": ("partly_cloudy", "晴间多云"),
    "104": ("overcast", "阴"),
    "150": ("sunny", "晴"),
    "151": ("partly_cloudy", "多云"),
    "152": ("partly_cloudy", "少云"),
    "153": ("partly_cloudy", "晴间多云"),
    "300": ("rain_light", "阵雨"),
    "301": ("rain_heavy", "强阵雨"),
    "302": ("thunder", "雷阵雨"),
    "303": ("thunder", "强雷阵雨"),
    "304": ("thunder", "雷阵雨伴冰雹"),
    "305": ("rain_light", "小雨"),
    "306": ("rain", "中雨"),
    "307": ("rain_heavy", "大雨"),
    "308": ("rain_heavy", "极端降雨"),
    "309": ("rain_light", "毛毛雨"),
    "310": ("rain_heavy", "暴雨"),
    "311": ("rain_heavy", "大暴雨"),
    "312": ("rain_heavy", "特大暴雨"),
    "313": ("sleet", "冻雨"),
    "314": ("rain_light", "小到中雨"),
    "315": ("rain", "中到大雨"),
    "316": ("rain_heavy", "大到暴雨"),
    "317": ("rain_heavy", "暴雨到大暴雨"),
    "318": ("rain_heavy", "大暴雨到特大暴雨"),
    "350": ("rain_light", "阵雨"),
    "351": ("rain", "强阵雨"),
    "399": ("rain", "雨"),
    "400": ("snow", "小雪"),
    "401": ("snow", "中雪"),
    "402": ("snow", "大雪"),
    "403": ("snow", "暴雪"),
    "404": ("sleet", "雨夹雪"),
    "405": ("sleet", "雨雪天气"),
    "406": ("rain_light", "阵雨夹雪"),
    "407": ("snow", "阵雪"),
    "408": ("snow", "小到中雪"),
    "409": ("snow", "中到大雪"),
    "410": ("snow", "大到暴雪"),
    "411": ("snow", "暴雪到大暴雪"),
    "412": ("snow", "大暴雪到特大暴雪"),
    "413": ("sleet", "冻雨"),
    "414": ("sleet", "冻雨"),
    "450": ("sleet", "雨夹雪"),
    "456": ("sleet", "阵性雨夹雪"),
    "457": ("sleet", "阵性雨夹雪"),
    "499": ("snow", "雪"),
    "500": ("fog", "薄雾"),
    "501": ("fog", "雾"),
    "502": ("haze", "霾"),
    "503": ("dust", "扬沙"),
    "504": ("dust", "浮尘"),
    "507": ("dust", "沙尘暴"),
    "508": ("dust", "强沙尘暴"),
    "509": ("fog", "浓雾"),
    "510": ("fog", "强浓雾"),
    "511": ("haze", "中度霾"),
    "512": ("haze", "重度霾"),
    "513": ("haze", "严重霾"),
    "514": ("fog", "大雾"),
    "515": ("fog", "特强浓雾"),
    "900": ("sunny", "热"),
    "901": ("snow", "冷"),
    "999": ("unknown", "未知天气"),
}


def qweather_info(code: Any, text: str = "", is_day: bool = True) -> Tuple[str, str]:
    code_text = str(code)
    icon, fallback = QWEATHER.get(code_text, ("unknown", text or "未知天气"))
    if code_text.startswith("15"):
        is_day = False
    return _day_night_icon(icon, is_day), text or fallback


# ---------------------------------------------------------------------------
# Xiaomi weather codes
# ---------------------------------------------------------------------------

XIAOMI: Dict[str, Tuple[str, str]] = {
    "0": ("sunny", "晴"),
    "1": ("partly_cloudy", "多云"),
    "2": ("overcast", "阴"),
    "3": ("fog", "雾"),
    "4": ("haze", "霾"),
    "5": ("dust", "沙尘"),
    "6": ("dust", "浮尘"),
    "7": ("thunder", "雷阵雨"),
    "8": ("rain_light", "阵雨"),
    "9": ("rain_heavy", "大雨"),
    "10": ("rain", "中雨"),
    "11": ("rain_light", "小雨"),
    "12": ("rain_heavy", "暴雨"),
    "13": ("rain_heavy", "大暴雨"),
    "14": ("snow", "阵雪"),
    "15": ("snow", "小雪"),
    "16": ("snow", "中雪"),
    "17": ("snow", "大雪"),
    "18": ("snow", "暴雪"),
    "19": ("sleet", "雨夹雪"),
    "20": ("sleet", "冻雨"),
    "21": ("thunder", "冰雹"),
    "22": ("snow", "霜冻"),
    "23": ("typhoon", "台风"),
    "24": ("dust", "沙尘暴"),
    "25": ("dust", "强沙尘暴"),
    "26": ("typhoon", "龙卷风"),
    "27": ("typhoon", "热带风暴"),
    "28": ("wind", "大风"),
    "29": ("typhoon", "飓风"),
    "30": ("unknown", "未知天气"),
    "31": ("rain_heavy", "特大暴雨"),
    "32": ("snow", "特大暴雪"),
    "49": ("haze", "霾"),
    "53": ("fog", "雾"),
    "54": ("fog", "浓雾"),
    "99": ("unknown", "未知天气"),
}


def xiaomi_info(code: Any, is_day: bool = True) -> Tuple[str, str]:
    icon, text = XIAOMI.get(str(code), ("unknown", "未知天气"))
    return _day_night_icon(icon, is_day), text


# ---------------------------------------------------------------------------
# OpenWeatherMap condition ids
# ---------------------------------------------------------------------------


def owm_info(code: Any, description: str = "") -> Tuple[str, str]:
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "unknown", description or "未知天气"
    if value == 800:
        return "sunny", description or "晴"
    if value in (801,):
        return "partly_cloudy", description or "少云"
    if value in (802, 803):
        return "cloudy", description or "多云"
    if value == 804:
        return "overcast", description or "阴"
    if 200 <= value < 300:
        return "thunder", description or "雷雨"
    if 300 <= value < 400:
        return "rain_light", description or "毛毛雨"
    if 500 <= value < 600:
        if value in (502, 503, 504, 522):
            return "rain_heavy", description or "大雨"
        return "rain", description or "雨"
    if 600 <= value < 700:
        return "snow", description or "雪"
    if value in (701, 741):
        return "fog", description or "雾"
    if value in (711, 721, 731, 751, 761, 762):
        return "haze", description or "霾"
    if value == 771:
        return "wind", description or "大风"
    if value == 781:
        return "typhoon", description or "龙卷风"
    return "unknown", description or "未知天气"


def owm_icon(code: Any, description: str = "", is_day: bool = True) -> Tuple[str, str]:
    icon, text = owm_info(code, description)
    return _day_night_icon(icon, is_day), text


# ---------------------------------------------------------------------------
# WeatherAPI condition codes
# ---------------------------------------------------------------------------


def weatherapi_info(code: Any, text: str = "", is_day: bool = True) -> Tuple[str, str]:
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "unknown", text or "未知天气"
    if value == 1000:
        icon = "sunny"
    elif value in (1003,):
        icon = "partly_cloudy"
    elif value in (1006, 1009):
        icon = "overcast" if value == 1009 else "cloudy"
    elif value in (1030, 1135, 1147):
        icon = "fog"
    elif 1066 <= value <= 1237:
        icon = "sleet" if value in (1069, 1204, 1207, 1237) else "snow"
    elif 1063 <= value <= 1201:
        icon = "rain_heavy" if value in (1192, 1195, 1201) else "rain"
    elif 1240 <= value <= 1264:
        icon = "rain" if value < 1255 else "snow"
    elif 1273 <= value <= 1282:
        icon = "thunder"
    elif value in (1087,):
        icon = "thunder"
    elif value in (1114, 1117):
        icon = "snow"
    else:
        icon = "unknown"
    return _day_night_icon(icon, is_day), text or "未知天气"


# ---------------------------------------------------------------------------
# Caiyun skycon values
# ---------------------------------------------------------------------------

CAIYUN: Dict[str, Tuple[str, str]] = {
    "CLEAR_DAY": ("sunny", "晴"),
    "CLEAR_NIGHT": ("sunny", "晴"),
    "PARTLY_CLOUDY_DAY": ("partly_cloudy", "多云"),
    "PARTLY_CLOUDY_NIGHT": ("partly_cloudy", "多云"),
    "CLOUDY": ("cloudy", "阴"),
    "LIGHT_HAZE": ("haze", "轻度霾"),
    "MODERATE_HAZE": ("haze", "中度霾"),
    "HEAVY_HAZE": ("haze", "重度霾"),
    "LIGHT_RAIN": ("rain_light", "小雨"),
    "MODERATE_RAIN": ("rain", "中雨"),
    "HEAVY_RAIN": ("rain_heavy", "大雨"),
    "STORM_RAIN": ("rain_heavy", "暴雨"),
    "FOG": ("fog", "雾"),
    "LIGHT_SNOW": ("snow", "小雪"),
    "MODERATE_SNOW": ("snow", "中雪"),
    "HEAVY_SNOW": ("snow", "大雪"),
    "STORM_SNOW": ("snow", "暴雪"),
    "DUST": ("dust", "浮尘"),
    "SAND": ("dust", "扬沙"),
    "WIND": ("wind", "大风"),
}


def caiyun_info(skycon: Any, is_day: bool = True) -> Tuple[str, str]:
    icon, text = CAIYUN.get(str(skycon), ("unknown", "未知天气"))
    return _day_night_icon(icon, is_day), text


# ---------------------------------------------------------------------------
# MET Norway symbol codes
# ---------------------------------------------------------------------------


def metno_info(symbol: Any, is_day: bool = True) -> Tuple[str, str]:
    text = str(symbol or "").lower()
    if "thunder" in text:
        icon, label = "thunder", "雷雨"
    elif "sleet" in text:
        icon, label = "sleet", "雨夹雪"
    elif "snow" in text:
        icon, label = "snow", "雪"
    elif "rain" in text or "drizzle" in text:
        if "heavy" in text:
            icon, label = "rain_heavy", "大雨"
        elif "light" in text:
            icon, label = "rain_light", "小雨"
        else:
            icon, label = "rain", "雨"
    elif "fog" in text:
        icon, label = "fog", "雾"
    elif "cloudy" in text:
        if "partly" in text:
            icon, label = "partly_cloudy", "多云"
        elif "fair" in text:
            icon, label = "partly_cloudy", "晴间多云"
        else:
            icon, label = "overcast", "阴"
    elif "clear" in text or "fair" in text:
        icon, label = "sunny", "晴"
    else:
        icon, label = "unknown", "未知天气"
    if "night" in text:
        is_day = False
    return _day_night_icon(icon, is_day), label


def _day_night_icon(icon: str, is_day: bool) -> str:
    if icon == "sunny":
        return "sunny_day" if is_day else "sunny_night"
    if icon == "partly_cloudy":
        return "partly_cloudy_day" if is_day else "partly_cloudy_night"
    return icon


# ---------------------------------------------------------------------------
# Alert presentation
# ---------------------------------------------------------------------------


def normalize_alert_level(level: Any) -> str:
    text = str(level or "").strip()
    lowered = text.lower()
    table = {
        "blue": "蓝色",
        "yellow": "黄色",
        "orange": "橙色",
        "red": "红色",
        "white": "白色",
        "black": "黑色",
        "green": "绿色",
        "minor": "蓝色",
        "moderate": "黄色",
        "major": "橙色",
        "severe": "红色",
        "extreme": "红色",
        "standard": "",
        "unknown": "",
    }
    if lowered in table:
        return table[lowered]
    for key, value in table.items():
        if key and key in lowered and lowered not in ("unknown",):
            return value
    for color in ("蓝", "黄", "橙", "红", "白", "黑", "绿"):
        if color in text:
            return f"{color}色"
    return ""


def normalize_alert_color(value: Any) -> str:
    text = str(value or "").strip().lower()
    table = {
        "blue": "#237BFF",
        "蓝": "#237BFF",
        "蓝色": "#237BFF",
        "yellow": "#E6B800",
        "黄": "#E6B800",
        "黄色": "#E6B800",
        "orange": "#FF8C00",
        "橙": "#FF8C00",
        "橙色": "#FF8C00",
        "red": "#E81123",
        "红": "#E81123",
        "红色": "#E81123",
        "white": "#A6A6A6",
        "白": "#A6A6A6",
        "白色": "#A6A6A6",
        "black": "#4D4D4D",
        "黑": "#4D4D4D",
        "黑色": "#4D4D4D",
        "green": "#16A34A",
        "绿": "#16A34A",
        "绿色": "#16A34A",
    }
    for key, color in table.items():
        if key in text:
            return color
    if str(value or "").startswith("#"):
        return str(value)
    return "#0078D4"


def alert_icon_key(alert_type: Any, title: Any = "") -> str:
    text = f"{alert_type or ''} {title or ''}".lower()
    mapping = (
        ("台风", "alert_typhoon"),
        ("typhoon", "alert_typhoon"),
        ("飓风", "alert_typhoon"),
        ("暴雨", "alert_rain"),
        ("rain", "alert_rain"),
        ("洪涝", "alert_rain"),
        ("洪水", "alert_rain"),
        ("雷电", "alert_thunder"),
        ("雷暴", "alert_thunder"),
        ("thunder", "alert_thunder"),
        ("冰雹", "alert_thunder"),
        ("雪", "alert_snow"),
        ("snow", "alert_snow"),
        ("道路结冰", "alert_snow"),
        ("霜冻", "alert_snow"),
        ("寒潮", "alert_temp"),
        ("低温", "alert_temp"),
        ("高温", "alert_temp"),
        ("热", "alert_temp"),
        ("cold", "alert_temp"),
        ("heat", "alert_temp"),
        ("大风", "alert_wind"),
        ("wind", "alert_wind"),
        ("沙尘", "alert_dust"),
        ("dust", "alert_dust"),
        ("霾", "alert_dust"),
        ("haze", "alert_dust"),
        ("雾", "alert_fog"),
        ("fog", "alert_fog"),
        ("干旱", "alert_drought"),
        ("drought", "alert_drought"),
    )
    for key, icon in mapping:
        if key in text:
            return icon
    return "alert_generic"


def alert_level_short(level: Any) -> str:
    label = normalize_alert_level(level)
    return label or "预警"
