"""Class Widgets 2 weather plugin core.

Qt-free so it can be unit tested outside the Class Widgets runtime.
"""

__version__ = "1.0.0"

from .models import Alert, DailyForecast, HourlyForecast, Location, WeatherSnapshot
from .service import WeatherService

__all__ = [
    "Alert",
    "DailyForecast",
    "HourlyForecast",
    "Location",
    "WeatherSnapshot",
    "WeatherService",
    "__version__",
]
