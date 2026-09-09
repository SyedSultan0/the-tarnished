"""
weather.py - Open-Meteo Weather Integration for THE TARNISHED

This module handles all weather data retrieval using the Open-Meteo API.
Weather is used as CONTEXT for the advisory engine, not for disease diagnosis.

Features:
- Get current weather from latitude/longitude
- Get forecast for next 7 days
- Structured weather context for advisory engine
- Error handling for API failures
- Caching to reduce API calls
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import time

# ------------------------------------------------------------------
# DATA CLASSES FOR STRUCTURED WEATHER
# ------------------------------------------------------------------

@dataclass
class WeatherContext:
    """
    Structured weather data for the advisory engine.
    Only includes relevant fields - not raw API dumps.
    """
    temperature: float          # Current temperature in °C
    humidity: float             # Relative humidity in %
    rain_mm: float              # Rain in last 24 hours (mm)
    precipitation_probability: float  # Probability of rain today (%)
    weather_code: int           # WMO weather code
    weather_description: str    # Human-readable weather description
    wind_speed: float           # Wind speed in km/h
    soil_moisture: Optional[float]  # Soil moisture if available
    timestamp: str              # When this data was fetched
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON responses"""
        return asdict(self)

@dataclass
class WeatherForecast:
    """7-day weather forecast"""
    dates: List[str]
    temperatures: List[float]
    humidities: List[float]
    rain_probabilities: List[float]
    weather_codes: List[int]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON responses"""
        return asdict(self)


# ------------------------------------------------------------------
# WEATHER CODE MAPPINGS
# ------------------------------------------------------------------

# WMO Weather Interpretation Codes (WW)
# Source: https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail"
}

# Weather conditions that affect crop disease risk
HIGH_RISK_WEATHER_CODES = {
    61, 63, 65, 66, 67, 80, 81, 82  # Rain codes
}

MODERATE_RISK_WEATHER_CODES = {
    51, 53, 55, 56, 57, 71, 73, 75  # Drizzle or snow
}


# ------------------------------------------------------------------
# OPEN-METEO API CLIENT
# ------------------------------------------------------------------

class OpenMeteoClient:
    """
    Client for Open-Meteo weather API.
    
    Open-Meteo is free and does NOT require an API key.
    Documentation: https://open-meteo.com/en/docs
    
    We use latitude/longitude instead of city names for accuracy.
    """
    
    BASE_URL = "https://api.open-meteo.com/v1/forecast"
    
    def __init__(self, cache_duration_seconds: int = 300):
        """
        Initialize the weather client.
        
        Args:
            cache_duration_seconds: How long to cache weather data (default: 5 minutes)
        """
        self.cache_duration = cache_duration_seconds
        self._cache = {}  # Simple in-memory cache
        self._last_request_time = 0
        self._min_request_interval = 1.0  # 1 second between requests (rate limiting)
        
    def _get_cache_key(self, lat: float, lon: float) -> str:
        """Generate cache key for coordinates"""
        return f"{lat:.4f}_{lon:.4f}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid"""
        if cache_key not in self._cache:
            return False
        cached_time = self._cache[cache_key]["timestamp"]
        return (time.time() - cached_time) < self.cache_duration
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Retrieve data from cache if valid"""
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        return None
    
    def _set_cache(self, cache_key: str, data: Dict):
        """Store data in cache"""
        self._cache[cache_key] = {
            "data": data,
            "timestamp": time.time()
        }
    
    def _rate_limit(self):
        """Enforce rate limiting to avoid API abuse"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    def get_weather_context(
        self, 
        latitude: float, 
        longitude: float,
        force_refresh: bool = False
    ) -> Tuple[Optional[WeatherContext], Optional[str]]:
        """
        Get current weather context for a location.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            force_refresh: If True, bypass cache
            
        Returns:
            Tuple of (WeatherContext or None, error_message or None)
        """
        cache_key = self._get_cache_key(latitude, longitude)
        
        # Check cache first
        if not force_refresh:
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                try:
                    context = WeatherContext(**cached_data["context"])
                    return context, None
                except Exception as e:
                    print(f"Cache parse error: {e}")
        
        try:
            # Make API request
            self._rate_limit()
            
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m"
                ],
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max"
                ],
                "timezone": "auto",
                "forecast_days": 7
            }
            
            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse current weather
            current = data.get("current", {})
            daily = data.get("daily", {})
            
            # Extract values
            temperature = current.get("temperature_2m", 0.0)
            humidity = current.get("relative_humidity_2m", 0.0)
            rain_mm = current.get("precipitation", 0.0)
            weather_code = current.get("weather_code", 0)
            wind_speed = current.get("wind_speed_10m", 0.0)
            
            # Get today's precipitation probability
            rain_prob = 0.0
            if daily.get("precipitation_probability_max"):
                rain_prob = daily["precipitation_probability_max"][0] if daily["precipitation_probability_max"] else 0.0
            
            # Get weather description
            weather_desc = WEATHER_CODES.get(weather_code, "Unknown weather condition")
            
            # Create context
            context = WeatherContext(
                temperature=round(temperature, 1),
                humidity=round(humidity, 1),
                rain_mm=round(rain_mm, 2),
                precipitation_probability=round(rain_prob, 1),
                weather_code=weather_code,
                weather_description=weather_desc,
                wind_speed=round(wind_speed, 1),
                soil_moisture=None,  # Open-Meteo doesn't provide this in free tier
                timestamp=datetime.now().isoformat()
            )
            
            # Cache the result
            self._set_cache(cache_key, {"context": context.to_dict()})
            
            return context, None
            
        except requests.exceptions.Timeout:
            return None, "Weather API timeout. Please try again."
        except requests.exceptions.ConnectionError:
            return None, "Network error. Please check your internet connection."
        except requests.exceptions.HTTPError as e:
            return None, f"Weather API error: {str(e)}"
        except json.JSONDecodeError:
            return None, "Invalid response from weather API."
        except Exception as e:
            return None, f"Unexpected weather error: {str(e)}"
    
    def get_forecast(
        self, 
        latitude: float, 
        longitude: float,
        days: int = 7
    ) -> Tuple[Optional[WeatherForecast], Optional[str]]:
        """
        Get 7-day weather forecast.
        
        Args:
            latitude: Latitude in degrees
            longitude: Longitude in degrees
            days: Number of days forecast (1-7)
            
        Returns:
            Tuple of (WeatherForecast or None, error_message or None)
        """
        cache_key = f"forecast_{self._get_cache_key(latitude, longitude)}"
        
        # Check cache
        if self._is_cache_valid(cache_key):
            cached_data = self._get_from_cache(cache_key)
            if cached_data:
                try:
                    forecast = WeatherForecast(**cached_data["forecast"])
                    return forecast, None
                except Exception as e:
                    print(f"Cache parse error: {e}")
        
        try:
            self._rate_limit()
            
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max"
                ],
                "timezone": "auto",
                "forecast_days": min(days, 7)
            }
            
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            daily = data.get("daily", {})
            
            if not daily:
                return None, "No forecast data available"
            
            forecast = WeatherForecast(
                dates=daily.get("time", []),
                temperatures=daily.get("temperature_2m_max", []),
                humidities=[0] * len(daily.get("time", [])),  # Not directly available
                rain_probabilities=daily.get("precipitation_probability_max", []),
                weather_codes=daily.get("weather_code", [])
            )
            
            # Cache
            self._set_cache(cache_key, {"forecast": forecast.to_dict()})
            
            return forecast, None
            
        except Exception as e:
            return None, f"Forecast error: {str(e)}"
    
    def get_weather_summary(self, context: WeatherContext) -> str:
        """
        Generate a human-readable weather summary for the advisory.
        
        Args:
            context: WeatherContext object
            
        Returns:
            A concise weather summary string
        """
        conditions = []
        
        # Temperature
        temp = context.temperature
        if temp > 35:
            conditions.append(f"Very hot ({temp}°C)")
        elif temp > 30:
            conditions.append(f"Hot ({temp}°C)")
        elif temp < 15:
            conditions.append(f"Cool ({temp}°C)")
        else:
            conditions.append(f"Moderate ({temp}°C)")
        
        # Humidity
        hum = context.humidity
        if hum > 80:
            conditions.append("very humid")
        elif hum > 60:
            conditions.append("humid")
        elif hum < 30:
            conditions.append("dry")
        
        # Rain
        if context.rain_mm > 10:
            conditions.append(f"heavy rain ({context.rain_mm}mm)")
        elif context.rain_mm > 2:
            conditions.append(f"light rain ({context.rain_mm}mm)")
        elif context.rain_mm > 0:
            conditions.append(f"trace rain ({context.rain_mm}mm)")
        else:
            conditions.append("no rain")
        
        # Wind
        wind = context.wind_speed
        if wind > 40:
            conditions.append("high winds")
        elif wind > 25:
            conditions.append("moderate winds")
        
        return f"Current weather: {', '.join(conditions)}. {context.weather_description}."


# ------------------------------------------------------------------
# RISK ASSESSMENT FUNCTIONS
# ------------------------------------------------------------------

def assess_weather_risk(context: WeatherContext) -> Dict[str, any]:
    """
    Assess weather-related disease risk for crops.
    
    Args:
        context: WeatherContext object
        
    Returns:
        Dictionary with risk assessment
    """
    risk_level = "low"
    risk_factors = []
    risk_score = 0
    
    # Temperature risk
    temp = context.temperature
    if temp > 30:
        risk_score += 2
        risk_factors.append("High temperature stress")
    elif temp < 10:
        risk_score += 1
        risk_factors.append("Low temperature stress")
    
    # Humidity risk (high humidity favors fungal diseases)
    humidity = context.humidity
    if humidity > 80:
        risk_score += 3
        risk_factors.append("Very high humidity (fungal disease risk)")
    elif humidity > 65:
        risk_score += 2
        risk_factors.append("High humidity")
    elif humidity > 50:
        risk_score += 1
    
    # Rain risk
    if context.rain_mm > 10:
        risk_score += 3
        risk_factors.append("Heavy rain (splashing/spreading disease)")
    elif context.rain_mm > 2:
        risk_score += 2
        risk_factors.append("Moderate rain")
    elif context.rain_mm > 0:
        risk_score += 1
        risk_factors.append("Light rain")
    
    # Weather code risk
    if context.weather_code in HIGH_RISK_WEATHER_CODES:
        risk_score += 3
        risk_factors.append("Rainy weather")
    elif context.weather_code in MODERATE_RISK_WEATHER_CODES:
        risk_score += 1
    
    # Determine overall risk level
    if risk_score >= 8:
        risk_level = "high"
    elif risk_score >= 4:
        risk_level = "moderate"
    else:
        risk_level = "low"
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "summary": f"Weather risk is {risk_level} (score: {risk_score}). {', '.join(risk_factors[:3])}" if risk_factors else "No significant weather risks detected."
    }


# ------------------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------------------

def validate_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """
    Validate latitude and longitude values.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not (-90 <= lat <= 90):
        return False, f"Invalid latitude: {lat}. Must be between -90 and 90."
    if not (-180 <= lon <= 180):
        return False, f"Invalid longitude: {lon}. Must be between -180 and 180."
    return True, None


def get_telangana_coordinates(district: str) -> Optional[Tuple[float, float]]:
    """
    Get approximate coordinates for Telangana districts.
    Used as fallback when GPS not available.
    
    Args:
        district: District name in Telangana
        
    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    # Major Telangana districts and their approximate centers
    DISTRICT_COORDS = {
        "hyderabad": (17.3850, 78.4867),
        "warangal": (18.0000, 79.5833),
        "nizamabad": (18.6713, 78.1019),
        "khammam": (17.2473, 80.1514),
        "karimnagar": (18.4392, 79.1286),
        "mahabubnagar": (16.7422, 77.9856),
        "adilabad": (19.6667, 78.5333),
        "nalgonda": (17.0575, 79.2672),
        "sangareddy": (17.6220, 78.1006),
        "medak": (18.0417, 78.2640),
        "siddipet": (18.1010, 78.8470),
        "jagtial": (18.7954, 78.9167),
        "mancherial": (18.8709, 79.4253),
        "peddapalli": (18.6081, 79.3764),
        "kamareddy": (18.3200, 78.3400),
        "bhongir": (17.5150, 78.8900),
        "suryapet": (17.1406, 79.6244),
        "jangaon": (17.7247, 79.1680),
        "gadwal": (16.2357, 77.7959),
        "nagarkurnool": (16.4820, 78.3250),
        "vikarabad": (17.3380, 77.9040),
        "yadadri": (17.5885, 79.0280),
    }
    
    district_lower = district.lower().strip()
    
    # Try exact match
    if district_lower in DISTRICT_COORDS:
        return DISTRICT_COORDS[district_lower]
    
    # Try partial match
    for key, coords in DISTRICT_COORDS.items():
        if key in district_lower or district_lower in key:
            return coords
    
    return None


# ------------------------------------------------------------------
# CONVENIENCE FUNCTION (to be used by main.py)
# ------------------------------------------------------------------

# Global client instance
_weather_client = None

def get_weather_client() -> OpenMeteoClient:
    """Get or create a global weather client instance."""
    global _weather_client
    if _weather_client is None:
        _weather_client = OpenMeteoClient()
    return _weather_client


# ------------------------------------------------------------------
# TEST CODE (runs only when script is executed directly)
# ------------------------------------------------------------------

if __name__ == "__main__":
    print("🧪 Testing Weather Module...")
    print("-" * 50)
    
    # Test with Hyderabad coordinates
    lat, lon = 17.3850, 78.4867
    
    print(f"\n📍 Testing with Hyderabad (lat: {lat}, lon: {lon})")
    
    client = get_weather_client()
    
    # Test get_weather_context
    print("\n🌤️ Fetching current weather...")
    weather, error = client.get_weather_context(lat, lon)
    
    if weather:
        print(f"✅ Weather data retrieved!")
        print(f"   Temperature: {weather.temperature}°C")
        print(f"   Humidity: {weather.humidity}%")
        print(f"   Rain (24h): {weather.rain_mm}mm")
        print(f"   Condition: {weather.weather_description}")
        print(f"   Wind: {weather.wind_speed} km/h")
        print(f"   Rain probability: {weather.precipitation_probability}%")
        
        # Test summary
        print(f"\n📝 Weather Summary:")
        print(f"   {client.get_weather_summary(weather)}")
        
        # Test risk assessment
        print(f"\n⚠️ Risk Assessment:")
        risk = assess_weather_risk(weather)
        print(f"   Risk Level: {risk['risk_level']}")
        print(f"   Risk Score: {risk['risk_score']}")
        print(f"   Factors: {', '.join(risk['risk_factors'])}")
        
    else:
        print(f"❌ Error: {error}")
    
    # Test forecast
    print(f"\n📅 Fetching 7-day forecast...")
    forecast, error = client.get_forecast(lat, lon)
    
    if forecast:
        print(f"✅ Forecast retrieved!")
        print(f"   Days: {len(forecast.dates)}")
        if forecast.dates:
            print(f"   Today: {forecast.dates[0]} - {forecast.temperatures[0]}°C, Rain: {forecast.rain_probabilities[0]}%")
            if len(forecast.dates) > 3:
                print(f"   Day 4: {forecast.dates[3]} - {forecast.temperatures[3]}°C, Rain: {forecast.rain_probabilities[3]}%")
    else:
        print(f"❌ Forecast error: {error}")
    
    # Test Telangana district lookup
    print(f"\n🗺️ Testing district lookup:")
    for district in ["Hyderabad", "Warangal", "Karimnagar", "Unknown"]:
        coords = get_telangana_coordinates(district)
        if coords:
            print(f"   {district}: lat={coords[0]:.4f}, lon={coords[1]:.4f}")
        else:
            print(f"   {district}: Not found")
    
    print("\n" + "-" * 50)
    print("✅ Weather module test complete!")