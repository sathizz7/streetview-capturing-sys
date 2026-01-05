"""
Google Maps API service for Building Detection V2.

Provides async wrappers for Roads API and Street View API.
"""

import asyncio
import logging
from typing import List, Dict, Optional, Any
import requests

from models import RoadPoint, Viewpoint
from config import get_settings

logger = logging.getLogger(__name__)


class GoogleMapsService:
    """Service for interacting with Google Maps APIs."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with API key from settings or parameter."""
        settings = get_settings()
        self.api_key = api_key or settings.google_api_key
        self.roads_api_base = "https://roads.googleapis.com/v1"
        self.streetview_base = "https://maps.googleapis.com/maps/api/streetview"
        self.api_call_counter = 0
    
    async def find_nearest_roads(
        self, 
        points: List[str],
        max_batch_size: int = 10
    ) -> List[RoadPoint]:
        """
        Find nearest road points for a list of coordinate strings.
        
        Args:
            points: List of "lat,lon" strings
            max_batch_size: Maximum points per API call (Roads API limit is 100)
            
        Returns:
            List of RoadPoint objects snapped to roads
        """
        road_points: List[RoadPoint] = []
        
        if not points:
            return road_points
        
        url = f"{self.roads_api_base}/nearestRoads"
        
        # Process in batches
        for i in range(0, len(points), max_batch_size):
            batch = points[i:i + max_batch_size]
            params = {
                "points": "|".join(batch),
                "key": self.api_key
            }
            
            try:
                response = await self._request_async(url, params)
                self.api_call_counter += 1
                
                if response.status_code == 200:
                    data = response.json()
                    for point in data.get("snappedPoints", []):
                        location = point["location"]
                        road_point = RoadPoint(
                            lat=location["latitude"],
                            lon=location["longitude"],
                            road_type="road",
                            road_name=point.get("placeId", "Unknown")
                        )
                        road_points.append(road_point)
                else:
                    logger.warning(f"Roads API returned {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Roads API error: {e}")
                continue
        
        return road_points
    
    async def get_streetview_metadata(
        self, 
        lat: float, 
        lon: float, 
        radius: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Check Street View availability and get metadata.
        
        Args:
            lat, lon: Coordinates to check
            radius: Search radius in meters
            
        Returns:
            Metadata dict with pano_id, location, date if available, else None
        """
        url = f"{self.streetview_base}/metadata"
        params = {
            "location": f"{lat},{lon}",
            "key": self.api_key,
            "source": "outdoor",
            "radius": radius
        }
        
        try:
            response = await self._request_async(url, params)
            self.api_call_counter += 1
            
            if response.status_code == 200:
                metadata = response.json()
                if metadata.get("status") == "OK":
                    return {
                        "pano_id": metadata.get("pano_id"),
                        "location": metadata["location"],
                        "date": metadata.get("date", "unknown"),
                        "status": "OK"
                    }
            return None
            
        except Exception as e:
            logger.error(f"Street View metadata error: {e}")
            return None
    
    def generate_streetview_url(self, viewpoint: Viewpoint) -> str:
        """
        Generate Street View image URL for a viewpoint.
        
        Args:
            viewpoint: Viewpoint with camera parameters
            
        Returns:
            Full Street View API URL
        """
        settings = get_settings()
        params = {
            "size": settings.streetview_image_size,
            "heading": round(viewpoint.heading, 1),
            "pitch": round(viewpoint.pitch, 1),
            "fov": round(viewpoint.fov, 1),
            "key": self.api_key
        }
        
        # Use pano_id if available for stability
        if viewpoint.pano_id:
            params["pano"] = viewpoint.pano_id
        else:
            params["location"] = f"{viewpoint.lat},{viewpoint.lon}"
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.streetview_base}?{query_string}"
    
    async def _request_async(self, url: str, params: dict) -> requests.Response:
        """Run HTTP request in thread pool for async compatibility."""
        def _do_request():
            return requests.get(url, params=params, timeout=10)
        
        return await asyncio.to_thread(_do_request)
