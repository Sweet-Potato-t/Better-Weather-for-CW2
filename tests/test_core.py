from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwweather.formatting import convert_temp, temp_text
from cwweather.mappings import (
    alert_icon_key,
    normalize_alert_color,
    normalize_alert_level,
    qweather_info,
    wmo_info,
    xiaomi_info,
)
from cwweather.models import Alert, DailyForecast, HourlyForecast, Location, WeatherSnapshot, normalize_alerts
from cwweather.providers.caiyun import CaiyunProvider
from cwweather.providers.open_meteo import OpenMeteoProvider
from cwweather.providers.openweathermap import OpenWeatherMapProvider
from cwweather.providers.weatherapi import WeatherApiProvider
from cwweather.providers.qweather import QWeatherProvider
from cwweather.providers.xiaomi import XiaomiProvider
from cwweather import secrets
from cwweather.service import WeatherService


class MappingTests(unittest.TestCase):
    def test_wmo(self):
        self.assertEqual(wmo_info(0), ("sunny", "晴"))
        self.assertEqual(wmo_info(95)[0], "thunder")
        self.assertEqual(wmo_info(999)[0], "unknown")

    def test_provider_mappings(self):
        self.assertEqual(qweather_info("305")[0], "rain_light")
        self.assertEqual(qweather_info("150")[0], "sunny_night")
        self.assertEqual(xiaomi_info("7")[0], "thunder")

    def test_alert_presentation(self):
        self.assertEqual(normalize_alert_level("Orange"), "橙色")
        self.assertEqual(normalize_alert_color("红色"), "#E81123")
        self.assertEqual(alert_icon_key("暴雨", "暴雨橙色预警"), "alert_rain")
        self.assertEqual(alert_icon_key("大风"), "alert_wind")
        self.assertEqual(alert_icon_key("未知"), "alert_generic")


class IconAssetTests(unittest.TestCase):
    def test_every_mapped_icon_exists(self):
        icon_keys = {
            "sunny_day", "sunny_night", "partly_cloudy_day", "partly_cloudy_night",
            "cloudy", "overcast", "rain_light", "rain", "rain_heavy", "thunder",
            "snow", "sleet", "fog", "haze", "wind", "dust", "typhoon", "unknown",
            "alert_generic", "alert_rain", "alert_wind", "alert_snow", "alert_temp",
            "alert_fog", "alert_thunder", "alert_dust", "alert_typhoon", "alert_drought",
        }
        icon_dir = ROOT / "assets" / "icons"
        for key in icon_keys:
            self.assertTrue((icon_dir / f"{key}.png").is_file(), key)


class ModelTests(unittest.TestCase):
    def test_temperature_conversion(self):
        self.assertEqual(convert_temp(0, "fahrenheit"), 32)
        self.assertEqual(convert_temp(100, "fahrenheit"), 212)
        self.assertEqual(temp_text(18.4, "celsius"), "18°")
        self.assertEqual(temp_text(18.4, "fahrenheit"), "65°")

    def test_location_display_name(self):
        location = Location(39.9, 116.4, name="北京市", city="北京市", region="北京市", country="中国")
        self.assertEqual(location.display_name, "北京市 · 中国")
    def test_location_short_name_uses_smallest_unit(self):
        beijing = Location(39.9, 116.4, name="北京市", city="北京市", district="东城区", region="北京市", country="中国")
        self.assertEqual(beijing.short_name, "东城区")
        town = Location(30.7, 120.5, name="乌镇", city="嘉兴市", district="桐乡市", region="浙江省", country="中国")
        self.assertEqual(town.short_name, "乌镇")
        manual = Location(40.5, 81.2, name="阿拉尔", region="新疆", country="中国")
        self.assertEqual(manual.short_name, "阿拉尔")

    def test_dedupe_and_sort_alerts(self):
        raw = [
            {"id": "2", "title": "大风蓝色预警", "type": "大风", "level": "蓝色", "severity": 1},
            {"id": "1", "title": "暴雨橙色预警", "type": "暴雨", "level": "橙色", "severity": 3},
            {"id": "2", "title": "大风蓝色预警", "type": "大风", "level": "蓝色", "severity": 1},
        ]
        alerts = normalize_alerts(raw, "qweather")
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0].type, "暴雨")
        self.assertEqual(alerts[0].icon, "alert_rain")

    def test_snapshot_payload(self):
        snapshot = WeatherSnapshot(
            provider_id="test",
            provider_name="Test",
            location=Location(39.9, 116.4, name="北京市", timezone="Asia/Shanghai"),
            current_temp_c=20,
            condition="晴",
            icon="sunny_day",
            high_c=25,
            low_c=12,
            daily=[DailyForecast("2026-10-18", 25, 12, "晴", "sunny_day", True)],
            hourly=[HourlyForecast("2026-10-18T19:00", 20, "rain", "小雨", 60)],
            alerts=[
                Alert(
                    id="1",
                    title="暴雨橙色预警",
                    type="暴雨",
                    level="橙色",
                    color="#FF8C00",
                    severity=3,
                    source="qweather",
                    icon="alert_rain",
                )
            ],
        )
        payload = snapshot.to_payload("fahrenheit")
        self.assertEqual(payload["current"]["temp"], 68)
        self.assertEqual(payload["today"]["high"], 77)
        self.assertEqual(payload["hourly"][0]["hour"], "19:00")
        self.assertEqual(payload["hourly"][0]["temp"], 68)
        self.assertEqual(payload["alert_count"], 1)
        self.assertEqual(payload["alerts"][0]["source_name"], "和风天气")
        self.assertEqual(payload["current"]["text"], "晴")


class ServiceTests(unittest.TestCase):
    def test_provider_chain_uses_selected_first_and_caps_attempts(self):
        service = WeatherService()
        chain = service._provider_chain(
            "qweather",
            {"qweather_api_key": "test", "weatherapi_api_key": "test"},
        )
        self.assertEqual(chain[0], "qweather")
        self.assertLessEqual(len(chain), 4)
        self.assertIn("open-meteo", chain)


class OpenMeteoParserTests(unittest.TestCase):
    def test_parse(self):
        payload = {
            "timezone": "Asia/Shanghai",
            "current": {
                "time": "2026-10-18T17:00",
                "temperature_2m": 18.4,
                "relative_humidity_2m": 45,
                "apparent_temperature": 17.1,
                "is_day": 1,
                "weather_code": 2,
                "pressure_msl": 1015,
                "wind_speed_10m": 8.2,
                "wind_direction_10m": 350,
            },
            "daily": {
                "time": ["2026-10-18", "2026-10-19"],
                "weather_code": [2, 61],
                "temperature_2m_max": [22.2, 19.1],
                "temperature_2m_min": [11.1, 10.2],
                "sunrise": ["2026-10-18T06:27", "2026-10-19T06:28"],
                "sunset": ["2026-10-18T17:31", "2026-10-19T17:30"],
            },
            "hourly": {
                "time": ["2026-10-18T18:00", "2026-10-18T19:00", "2026-10-18T20:00"],
                "temperature_2m": [18.0, 17.0, 16.0],
                "weather_code": [2, 61, 61],
                "is_day": [1, 0, 0],
                "precipitation_probability": [10, 50, 60],
            },
        }

        class Provider(OpenMeteoProvider):
            def _get_json(self, *args, **kwargs):
                return payload

        snapshot = Provider().fetch(Location(39.9, 116.4, name="北京市"), {})
        self.assertEqual(snapshot.current_temp_c, 18.4)
        self.assertEqual(snapshot.icon, "partly_cloudy_day")
        self.assertEqual(snapshot.high_c, 22.2)
        self.assertEqual(snapshot.low_c, 11.1)
        self.assertEqual(len(snapshot.daily), 2)
        self.assertEqual(len(snapshot.hourly), 3)
        self.assertEqual(snapshot.hourly[0].icon, "partly_cloudy_day")
        self.assertEqual(snapshot.hourly[1].pop, 50)
        self.assertEqual(snapshot.location.timezone, "Asia/Shanghai")


class XiaomiParserTests(unittest.TestCase):
    def test_alert_parsing(self):
        payload = {
            "current": {
                "temperature": {"value": "17"},
                "weather": "7",
                "pubTime": "2026-10-18T16:00:00+08:00",
                "humidity": {"value": "60"},
            },
            "forecastDaily": {
                "temperature": {
                    "value": [
                        {"from": "20", "to": "12"},
                        {"from": "21", "to": "13"},
                    ]
                },
                "weather": {"value": [{"from": "7", "to": "0"}, {"from": "0", "to": "0"}]},
                "sunRiseSet": {"value": [{"from": "2026-10-18T06:00:00+08:00", "to": "2026-10-18T18:00:00+08:00"}]},
            },
            "alerts": [
                {
                    "alertId": "a1",
                    "title": "暴雨橙色预警",
                    "type": "暴雨",
                    "level": "橙色",
                    "detail": "注意防范",
                    "pubTime": "2026-10-18T16:00:00+08:00",
                }
            ],
        }

        class Provider(XiaomiProvider):
            def _locate(self, location):
                return "weathercn:101010100", "东城区"

            def _get_json(self, *args, **kwargs):
                return payload

        snapshot = Provider().fetch(Location(39.9, 116.4, name="北京市"), {})
        self.assertEqual(snapshot.icon, "thunder")
        self.assertEqual(len(snapshot.alerts), 1)
        self.assertEqual(snapshot.alerts[0].icon, "alert_rain")
        self.assertEqual(snapshot.daily[0].high_c, 20)
        self.assertEqual(snapshot.daily[0].low_c, 12)


if __name__ == "__main__":
    unittest.main()


class ApiRequestTests(unittest.TestCase):
    def test_qweather_uses_api_host_and_key_header(self):
        calls = []

        def fake_get(url, params=None, *, headers=None, config=None):
            calls.append((url, params or {}, headers or {}))
            if url.endswith("/v7/weather/now"):
                return {"code": "200", "now": {
                    "temp": "15", "icon": "101", "text": "晴",
                    "obsTime": "2026-10-23T18:00+08:00", "windScale": "2",
                    "windSpeed": "3", "humidity": "40",
                }}
            if url.endswith("/v7/weather/3d"):
                return {"code": "200", "daily": [{
                    "fxDate": "2026-10-23", "tempMax": "20", "tempMin": "10",
                    "iconDay": "101", "textDay": "晴", "sunrise": "07:00", "sunset": "18:00",
                }]}
            if url.endswith("/v7/weather/24h"):
                return {"code": "200", "hourly": [{
                    "fxTime": "2026-10-23T19:00+08:00", "temp": "14", "icon": "101",
                    "text": "晴", "pop": "10",
                }]}
            if url.endswith("/v7/warning/now"):
                return {"code": "200", "warning": []}
            raise AssertionError(url)

        provider = QWeatherProvider()
        provider._get_json = fake_get
        location = Location(39.9, 116.4, name="北京市", timezone="Asia/Shanghai")
        snapshot = provider.fetch(location, {
            "qweather_api_key": "test-key", "qweather_host": "abcxyz.qweatherapi.com",
        })
        self.assertEqual(snapshot.current_temp_c, 15)
        self.assertTrue(calls[0][0].startswith("https://abcxyz.qweatherapi.com/"))
        self.assertEqual(calls[0][2].get("X-QW-Api-Key"), "test-key")
        self.assertNotIn("key", calls[0][1])

    def test_caiyun_v26_endpoints_and_fields(self):
        calls = []

        def fake_get(url, params=None, *, headers=None, config=None):
            calls.append((url, params or {}))
            if url.endswith("/realtime"):
                return {"status": "ok", "result": {"realtime": {
                    "temperature": 18, "skycon": "PARTLY_CLOUDY_DAY",
                    "humidity": 0.5, "pressure": 100000, "visibility": 12,
                    "wind": {"speed": 8, "direction": 90},
                    "air_quality": {"aqi": {"chn": 63, "usa": 124}},
                    "server_time": 1761200000,
                }}}
            if url.endswith("/daily"):
                return {"status": "ok", "result": {
                    "daily": {
                        "temperature": [{"date": "2026-10-23", "max": 22, "min": 11}],
                        "skycon": [{"date": "2026-10-23", "value": "PARTLY_CLOUDY_DAY"}],
                        "astro": [{"sunrise": {"time": "07:00"}, "sunset": {"time": "18:00"}}],
                    },
                    "alert": {"content": []},
                }}
            raise AssertionError(url)

        provider = CaiyunProvider()
        provider._get_json = fake_get
        location = Location(39.9, 116.4, name="北京市", timezone="Asia/Shanghai")
        snapshot = provider.fetch(location, {"caiyun_api_key": "test-token"})
        self.assertEqual(snapshot.current_temp_c, 18)
        self.assertEqual(snapshot.pressure_hpa, 1000)
        self.assertEqual(snapshot.aqi, 63)
        self.assertEqual(snapshot.sunrise, "07:00")
        self.assertTrue(calls[0][0].endswith("/realtime"))
        self.assertTrue(calls[1][0].endswith("/daily"))
        self.assertNotIn(".json", calls[0][0])


class PaidProviderRequestTests(unittest.TestCase):
    def test_openweather_onecall_appid(self):
        calls = []
        def fake_get(url, params=None, *, headers=None, config=None):
            calls.append((url, params or {}))
            return {
                "current": {"temp": 18, "weather": [{"id": 801, "description": "多云"}],
                            "dt": 1761200000, "sunrise": 1761170000, "sunset": 1761210000},
                "daily": [{"dt": 1761200000, "temp": {"max": 22, "min": 11},
                           "weather": [{"id": 801, "description": "多云"}]}],
                "hourly": [{"dt": 1761200000, "temp": 18, "pop": 0.2,
                            "weather": [{"id": 801, "description": "多云"}]}],
                "alerts": [],
            }
        provider = OpenWeatherMapProvider(); provider._get_json = fake_get
        provider.fetch(Location(39.9, 116.4), {"openweathermap_api_key": "owm-key"})
        url, params = calls[0]
        self.assertEqual(url, "https://api.openweathermap.org/data/3.0/onecall")
        self.assertEqual(params["appid"], "owm-key")
        self.assertEqual(params["units"], "metric")
        self.assertEqual(params["lang"], "zh_cn")
        self.assertEqual(params["exclude"], "minutely")

    def test_weatherapi_forecast_key(self):
        calls = []
        def fake_get(url, params=None, *, headers=None, config=None):
            calls.append((url, params or {}))
            return {
                "current": {"temp_c": 18, "is_day": 1, "last_updated": "2026-10-23 18:00",
                            "condition": {"code": 1000, "text": "晴"}},
                "forecast": {"forecastday": [{
                    "date": "2026-10-23", "day": {"maxtemp_c": 22, "mintemp_c": 11,
                    "condition": {"code": 1000, "text": "晴"}},
                    "astro": {"sunrise": "07:00", "sunset": "18:00"},
                    "hour": [{"time": "2026-10-23 19:00", "temp_c": 17, "is_day": 0,
                              "chance_of_rain": 10, "condition": {"code": 1000, "text": "晴"}}],
                }]},
                "alerts": {"alert": []},
            }
        provider = WeatherApiProvider(); provider._get_json = fake_get
        provider.fetch(Location(39.9, 116.4), {"weatherapi_api_key": "wa-key"})
        url, params = calls[0]
        self.assertEqual(url, "https://api.weatherapi.com/v1/forecast.json")
        self.assertEqual(params["key"], "wa-key")
        self.assertEqual(params["q"], "39.9000,116.4000")
        self.assertEqual(params["aqi"], "yes")
        self.assertEqual(params["alerts"], "yes")
        self.assertEqual(params["lang"], "zh")


class SecretStorageTests(unittest.TestCase):
    @unittest.skipUnless(secrets.available(), "DPAPI is only available on Windows")
    def test_dpapi_round_trip(self):
        ciphertext = secrets.protect("test-api-key")
        self.assertTrue(ciphertext.startswith(secrets.PREFIX))
        self.assertNotIn("test-api-key", ciphertext)
        self.assertEqual(secrets.unprotect(ciphertext), "test-api-key")

    def test_legacy_plaintext_is_still_readable(self):
        self.assertEqual(secrets.unprotect("legacy-key"), "legacy-key")
