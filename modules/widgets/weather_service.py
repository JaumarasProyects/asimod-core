import requests
import json
from datetime import datetime

class WeatherService:
    """
    Servicio para obtener datos meteorológicos y de ubicación sin necesidad de API Keys.
    Usa IP-API para geolocalización y Open-Meteo para el clima.
    """
    
    @staticmethod
    def get_location():
        """Obtiene la ubicación aproximada basada en la IP."""
        try:
            response = requests.get("http://ip-api.com/json/", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    return {
                        "city": data.get("city"),
                        "lat": data.get("lat"),
                        "lon": data.get("lon"),
                        "timezone": data.get("timezone")
                    }
        except Exception as e:
            print(f"[WeatherService] Error getting location: {e}")
        return None

    @staticmethod
    def get_weather(lat=None, lon=None, timezone="auto"):
        """Obtiene el clima actual para unas coordenadas dadas."""
        if lat is None or lon is None:
            loc = WeatherService.get_location()
            if loc:
                lat, lon, timezone = loc["lat"], loc["lon"], loc["timezone"]
            else:
                # Default a Madrid si todo falla
                lat, lon, timezone = 40.4168, -3.7038, "Europe/Madrid"

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": ["temperature_2m", "weather_code", "relative_humidity_2m"],
            "timezone": timezone
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})
                
                # Mapeo simple de códigos WMO a texto/unidades
                code = current.get("weather_code", 0)
                condition = WeatherService._map_weather_code(code)
                
                return {
                    "temp": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "condition": condition,
                    "code": code,
                    "time": current.get("time")
                }
        except Exception as e:
            print(f"[WeatherService] Error getting weather: {e}")
        return None

    @staticmethod
    def _map_weather_code(code):
        """Mapea los códigos WMO a descripciones en español."""
        wmo_codes = {
            0: "Despejado",
            1: "Principalmente despejado", 2: "Parcialmente nublado", 3: "Nublado",
            45: "Niebla", 48: "Escarcha",
            51: "Llovizna ligera", 53: "Llovizna moderada", 55: "Llovizna densa",
            61: "Lluvia débil", 63: "Lluvia moderada", 65: "Lluvia fuerte",
            71: "Nieve débil", 73: "Nieve moderada", 75: "Nieve fuerte",
            80: "Chubascos ligeros", 81: "Chubascos moderados", 82: "Chubascos violentos",
            95: "Tormenta débil/moderada", 96: "Tormenta con granizo"
        }
        return wmo_codes.get(code, "Desconocido")
