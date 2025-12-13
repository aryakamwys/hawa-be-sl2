"""
Open-Meteo Service
Free weather API service - no API key required
Supports Indonesia/Bandung
"""
from typing import Dict, Any, Optional
import httpx


class OpenMeteoService:
    """Service to fetch weather data from Open-Meteo API (free, no API key)"""

    def __init__(self):
        self.base_url = "https://api.open-meteo.com/v1"
        self.timeout = 10.0
        self.bandung_lat = -6.9175
        self.bandung_lon = 107.6191

    def _get_city_coordinates(self, city: str) -> tuple:
        """
        Get coordinates for a city.
        Returns Bandung coordinates as default.
        Can be extended with geocoding if needed.
        """
        city_coords = {
            "bandung": (self.bandung_lat, self.bandung_lon),
            "jakarta": (-6.2088, 106.8456),
            "surabaya": (-7.2575, 112.7521),
            "yogyakarta": (-7.7956, 110.3695),
            "medan": (3.5952, 98.6722),
            "semarang": (-6.9667, 110.4167),
        }
        
        city_lower = city.lower().strip()
        return city_coords.get(city_lower, (self.bandung_lat, self.bandung_lon))

    def get_current_weather(self, city: str = "Bandung", country_code: str = "ID") -> Dict[str, Any]:
        """
        Get current weather data for a city
        
        Args:
            city: City name (default: Bandung)
            country_code: Country code (default: ID for Indonesia)
        
        Returns:
            Dictionary with current weather data
        """
        try:
            lat, lon = self._get_city_coordinates(city)
            
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,pressure_msl,is_day",
                "timezone": "Asia/Jakarta",
                "forecast_days": 1
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            return self._normalize_current_weather(data, city)
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {str(e)}", "data": None}
        except Exception as e:
            return {"error": f"Error fetching weather: {str(e)}", "data": None}

    def get_forecast(self, city: str = "Bandung", country_code: str = "ID", days: int = 5) -> Dict[str, Any]:
        """
        Get weather forecast for a city
        
        Args:
            city: City name (default: Bandung)
            country_code: Country code (default: ID)
            days: Number of days to forecast (default: 5, max: 16 for free tier)
        
        Returns:
            Dictionary with forecast data
        """
        try:
            lat, lon = self._get_city_coordinates(city)
            
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weather_code,wind_speed_10m_max,relative_humidity_2m_max",
                "timezone": "Asia/Jakarta",
                "forecast_days": min(days, 16)
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            return self._normalize_forecast(data, city)
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {str(e)}", "data": None}
        except Exception as e:
            return {"error": f"Error fetching forecast: {str(e)}", "data": None}

    def get_hourly_forecast(self, city: str = "Bandung", country_code: str = "ID", hours: int = 24) -> Dict[str, Any]:
        """
        Get hourly weather forecast for a city
        
        Args:
            city: City name (default: Bandung)
            country_code: Country code (default: ID)
            hours: Number of hours to forecast (default: 24, max: 240 for free tier)
        
        Returns:
            Dictionary with hourly forecast data
        """
        try:
            lat, lon = self._get_city_coordinates(city)
            
            url = f"{self.base_url}/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,precipitation_probability,precipitation",
                "timezone": "Asia/Jakarta",
                "forecast_days": min((hours // 24) + 1, 16)
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            
            return self._normalize_hourly_forecast(data, city)
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {str(e)}", "data": None}
        except Exception as e:
            return {"error": f"Error fetching hourly forecast: {str(e)}", "data": None}

    def get_air_quality_history(self, city: str = "Bandung", hours: int = 72) -> Dict[str, Any]:
        """
        Get historical air quality (PM2.5 & PM10) using Open-Meteo Air Quality API.

        Args:
            city: City name (default: Bandung)
            hours: Number of hours to retrieve (default: 72, max: 168)

        Returns:
            Dictionary with normalized air quality series
        """
        try:
            lat, lon = self._get_city_coordinates(city)

            url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            total_days = max(1, min((hours // 24) + 1, 7))
            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "pm10,pm2_5",
                "timezone": "Asia/Jakarta",
                "past_days": total_days,
                "forecast_days": 1,
                # Open-Meteo expects iso8601 or unix; use iso8601 for consistency
                "timeformat": "iso8601"
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            return self._normalize_air_quality_history(data, city, hours)
        except httpx.HTTPError as e:
            return {"error": f"HTTP error: {str(e)}", "data": None}
        except Exception as e:
            return {"error": f"Error fetching air quality: {str(e)}", "data": None}

    def _normalize_current_weather(self, data: Dict[str, Any], city: str) -> Dict[str, Any]:
        """Normalize Open-Meteo current weather response"""
        if "error" in data:
            return {"error": data.get("error"), "data": None}
        
        current = data.get("current", {})
        weather_code = current.get("weather_code", 0)
        weather_desc = self._get_weather_description(weather_code)
        
        normalized = {
            "location": {
                "name": city,
                "country": "ID",
                "lat": data.get("latitude"),
                "lon": data.get("longitude")
            },
            "current": {
                "temperature": current.get("temperature_2m"),
                "feels_like": current.get("temperature_2m"),
                "humidity": current.get("relative_humidity_2m"),
                "pressure": current.get("pressure_msl"),
                "temp_min": current.get("temperature_2m"),
                "temp_max": current.get("temperature_2m"),
                "visibility": None,
                "wind_speed": current.get("wind_speed_10m"),
                "wind_direction": None,
                "clouds": None,
                "weather": {
                    "main": weather_desc.get("main", ""),
                    "description": weather_desc.get("description", ""),
                    "icon": weather_desc.get("icon", "")
                },
                "sunrise": None,
                "sunset": None,
                "timestamp": current.get("time"),
                "is_day": current.get("is_day", 1)
            }
        }
        
        return {"data": normalized, "error": None}

    def _normalize_forecast(self, data: Dict[str, Any], city: str) -> Dict[str, Any]:
        """Normalize Open-Meteo forecast response"""
        if "error" in data:
            return {"error": data.get("error"), "data": None}
        
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        temp_max = daily.get("temperature_2m_max", [])
        temp_min = daily.get("temperature_2m_min", [])
        weather_codes = daily.get("weather_code", [])
        wind_speed = daily.get("wind_speed_10m_max", [])
        humidity = daily.get("relative_humidity_2m_max", [])
        
        forecasts = []
        for i in range(len(dates)):
            weather_code = weather_codes[i] if i < len(weather_codes) else 0
            weather_desc = self._get_weather_description(weather_code)
            
            forecasts.append({
                "datetime": dates[i],
                "temperature": (temp_max[i] + temp_min[i]) / 2 if i < len(temp_max) and i < len(temp_min) else temp_max[i] if i < len(temp_max) else 0,
                "feels_like": (temp_max[i] + temp_min[i]) / 2 if i < len(temp_max) and i < len(temp_min) else temp_max[i] if i < len(temp_max) else 0,
                "humidity": humidity[i] if i < len(humidity) else None,
                "pressure": None,  # Not in daily forecast
                "temp_min": temp_min[i] if i < len(temp_min) else None,
                "temp_max": temp_max[i] if i < len(temp_max) else None,
                "wind_speed": wind_speed[i] if i < len(wind_speed) else None,
                "wind_direction": None,
                "clouds": None,
                "weather": {
                    "main": weather_desc.get("main", ""),
                    "description": weather_desc.get("description", ""),
                    "icon": weather_desc.get("icon", "")
                },
                "rain": None,
                "snow": None
            })
        
        normalized = {
            "location": {
                "name": city,
                "country": "ID",
                "lat": data.get("latitude"),
                "lon": data.get("longitude")
            },
            "forecasts": forecasts
        }
        
        return {"data": normalized, "error": None}

    def _normalize_hourly_forecast(self, data: Dict[str, Any], city: str) -> Dict[str, Any]:
        """Normalize Open-Meteo hourly forecast response."""
        if "error" in data:
            return {"error": data.get("error"), "data": None}
        
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        humidity = hourly.get("relative_humidity_2m", [])
        weather_codes = hourly.get("weather_code", [])
        wind_speed = hourly.get("wind_speed_10m", [])
        precipitation_prob = hourly.get("precipitation_probability", [])
        precipitation = hourly.get("precipitation", [])
        
        hourly_forecasts = []
        for i in range(len(times)):
            weather_code = weather_codes[i] if i < len(weather_codes) else 0
            weather_desc = self._get_weather_description(weather_code)
            
            hourly_forecasts.append({
                "datetime": times[i],
                "temperature": temperatures[i] if i < len(temperatures) else None,
                "humidity": humidity[i] if i < len(humidity) else None,
                "wind_speed": wind_speed[i] if i < len(wind_speed) else None,
                "precipitation_probability": precipitation_prob[i] if i < len(precipitation_prob) else None,
                "precipitation": precipitation[i] if i < len(precipitation) else None,
                "weather": {
                    "main": weather_desc.get("main", ""),
                    "description": weather_desc.get("description", ""),
                    "icon": weather_desc.get("icon", "")
                }
            })
        
        normalized = {
            "location": {
                "name": city,
                "country": "ID",
                "lat": data.get("latitude"),
                "lon": data.get("longitude")
            },
            "hourly": hourly_forecasts
        }
        
        return {"data": normalized, "error": None}

    def _normalize_air_quality_history(self, data: Dict[str, Any], city: str, hours: int) -> Dict[str, Any]:
        """Normalize Open-Meteo air quality history response."""
        if "error" in data:
            return {"error": data.get("error"), "data": None}

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        pm25 = hourly.get("pm2_5", [])
        pm10 = hourly.get("pm10", [])

        series = []
        for idx, time_val in enumerate(times):
            if len(series) >= hours:
                break
            series.append({
                "time": time_val,
                "pm25": pm25[idx] if idx < len(pm25) else None,
                "pm10": pm10[idx] if idx < len(pm10) else None
            })

        normalized = {
            "city": city,
            "series": series,
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "timezone": data.get("timezone")
        }

        return {"data": normalized, "error": None}

    def _get_weather_description(self, code: int) -> Dict[str, str]:
        """
        Convert WMO Weather interpretation codes to descriptions.
        Returns main, description, and icon.
        """
        code_map = {
            0: {"main": "Clear", "description": "Cerah", "icon": "☀️"},
            1: {"main": "Clear", "description": "Sebagian besar cerah", "icon": "🌤️"},
            2: {"main": "Clouds", "description": "Sebagian berawan", "icon": "⛅"},
            3: {"main": "Clouds", "description": "Mendung", "icon": "☁️"},
            45: {"main": "Fog", "description": "Kabut", "icon": "🌫️"},
            48: {"main": "Fog", "description": "Kabut beku", "icon": "🌫️"},
            51: {"main": "Drizzle", "description": "Gerimis ringan", "icon": "🌦️"},
            53: {"main": "Drizzle", "description": "Gerimis sedang", "icon": "🌦️"},
            55: {"main": "Drizzle", "description": "Gerimis lebat", "icon": "🌦️"},
            56: {"main": "Drizzle", "description": "Gerimis beku ringan", "icon": "🌦️"},
            57: {"main": "Drizzle", "description": "Gerimis beku lebat", "icon": "🌦️"},
            61: {"main": "Rain", "description": "Hujan ringan", "icon": "🌧️"},
            63: {"main": "Rain", "description": "Hujan sedang", "icon": "🌧️"},
            65: {"main": "Rain", "description": "Hujan lebat", "icon": "🌧️"},
            66: {"main": "Rain", "description": "Hujan beku ringan", "icon": "🌧️"},
            67: {"main": "Rain", "description": "Hujan beku lebat", "icon": "🌧️"},
            71: {"main": "Snow", "description": "Salju ringan", "icon": "❄️"},
            73: {"main": "Snow", "description": "Salju sedang", "icon": "❄️"},
            75: {"main": "Snow", "description": "Salju lebat", "icon": "❄️"},
            77: {"main": "Snow", "description": "Butiran salju", "icon": "❄️"},
            80: {"main": "Rain", "description": "Hujan deras ringan", "icon": "🌧️"},
            81: {"main": "Rain", "description": "Hujan deras sedang", "icon": "🌧️"},
            82: {"main": "Rain", "description": "Hujan deras lebat", "icon": "🌧️"},
            85: {"main": "Snow", "description": "Hujan salju ringan", "icon": "❄️"},
            86: {"main": "Snow", "description": "Hujan salju lebat", "icon": "❄️"},
            95: {"main": "Thunderstorm", "description": "Badai petir", "icon": "⛈️"},
            96: {"main": "Thunderstorm", "description": "Badai petir dengan hujan es", "icon": "⛈️"},
            99: {"main": "Thunderstorm", "description": "Badai petir parah dengan hujan es", "icon": "⛈️"},
        }
        
        return code_map.get(code, {"main": "Unknown", "description": "Tidak diketahui", "icon": "❓"})

