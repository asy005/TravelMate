# app/services/weather_service.py
import os, time, requests
from dotenv import load_dotenv

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Global in-memory cache
weather_cache = {}
CACHE_TTL = 900  # 15 minutes

def cached_weather(lat: float, lon: float, units: str = "metric"):
    """
    Weather caching layer:
    - Cache expires after 15 minutes
    - Cache key: "lat,lon"
    """
    key = f"{lat},{lon}"
    now = time.time()

    # return cached result if exists & usable
    if key in weather_cache:
        data, timestamp = weather_cache[key]
        if (now - timestamp) <= CACHE_TTL:
            return data  # fresh cached data

    # Otherwise fetch live
    data = get_weather_for_coords(lat, lon, units)
    weather_cache[key] = (data, now)
    return data


def get_weather_for_coords(lat: float, lon: float, units: str = "metric"):
    """
    Fetch live weather from OpenWeather API.
    Wrapped by cached_weather() for caching.
    """
    if not OPENWEATHER_API_KEY:
        return None

    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": units}

        r = requests.get(url, params=params, timeout=5)
        r.raise_for_status()

        j = r.json()
        return {
            "temp": j["main"]["temp"],
            "feels_like": j["main"]["feels_like"],
            "humidity": j["main"]["humidity"],
            "description": j["weather"][0]["description"],
            "wind_speed": j["wind"]["speed"],
        }
    except Exception as e:
        print(f"[Weather] Error fetching data: {e}")
        return None
