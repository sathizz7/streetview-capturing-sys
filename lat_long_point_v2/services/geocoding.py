"""
Geocoding service for Building Detection V2.

Provides reverse geocoding to convert coordinates to addresses.
"""

import logging
from typing import Optional
import googlemaps

from config import get_settings

logger = logging.getLogger(__name__)

# Global client instance
_gmaps_client: Optional[googlemaps.Client] = None


def _get_client() -> googlemaps.Client:
    """Get or create Google Maps client."""
    global _gmaps_client
    if _gmaps_client is None:
        settings = get_settings()
        _gmaps_client = googlemaps.Client(key=settings.google_api_key)
    return _gmaps_client


def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """
    Convert coordinates to a human-readable address.
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        Formatted address string, or None if not found
    """
    try:
        client = _get_client()
        results = client.reverse_geocode((lat, lon))
        
        if results:
            address = results[0]["formatted_address"]
            logger.info(f"Geocoded ({lat}, {lon}) -> {address}")
            return address
        else:
            logger.warning(f"No address found for ({lat}, {lon})")
            return None
            
    except Exception as e:
        logger.error(f"Reverse geocoding error: {e}")
        return None
