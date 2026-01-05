"""
Road Finder - Pipeline Step 1

Finds nearby road points around a building for camera placement.
Since we only have lat/long (no polygon), we sample in a 360° pattern.
"""

import logging
from typing import List

from models import RoadPoint
from services import GoogleMapsService
from utils import calculate_position_offset, calculate_distance
from config import get_settings

logger = logging.getLogger(__name__)


class RoadFinder:
    """
    Finds road points around a building using 360° sampling.
    
    Since V2 doesn't have polygon data, we can't determine building faces.
    Instead, we sample points in all directions and snap them to roads.
    """
    
    def __init__(self, maps_service: GoogleMapsService):
        self.maps_service = maps_service
        self.settings = get_settings()
    
    async def find_candidate_roads(
        self, 
        building_lat: float, 
        building_lon: float
    ) -> List[RoadPoint]:
        """
        Find road points around the building in a 360° pattern.
        
        Strategy:
        1. Generate sample points at multiple distances
        2. For each distance, sample N directions (360° / N)
        3. Snap each sample to nearest road using Roads API
        4. Deduplicate and return road points sorted by distance
        
        Args:
            building_lat: Building latitude
            building_lon: Building longitude
            
        Returns:
            List of RoadPoint objects representing nearby road positions
        """
        logger.info(f"Finding roads near ({building_lat}, {building_lon})")
        
        # Generate sample points
        sample_points: List[str] = []
        distances = self.settings.road_sample_distances
        num_directions = self.settings.road_sample_directions
        
        for distance in distances:
            for i in range(num_directions):
                bearing = (360 / num_directions) * i  # 0°, 45°, 90°, 135°, etc.
                
                lat, lon = calculate_position_offset(
                    building_lat, building_lon, 
                    distance, bearing
                )
                sample_points.append(f"{lat},{lon}")
        
        logger.info(f"Generated {len(sample_points)} sample points for road snapping")
        
        # Snap to roads using Roads API
        road_points = await self.maps_service.find_nearest_roads(sample_points)
        logger.info(f"Roads API returned {len(road_points)} snapped points")
        
        # Calculate distance to building for each road point
        for point in road_points:
            point.distance_to_building = calculate_distance(
                point.lat, point.lon,
                building_lat, building_lon
            )
        
        # Deduplicate (remove points too close to each other)
        unique_points = self._deduplicate(road_points)
        logger.info(f"After deduplication: {len(unique_points)} unique road points")
        
        # Sort by distance (closest first)
        unique_points.sort(key=lambda p: p.distance_to_building)
        
        # Limit to max candidates
        max_candidates = self.settings.max_candidates_per_building
        return unique_points[:max_candidates]
    
    def _deduplicate(self, points: List[RoadPoint], tolerance: float = 5.0) -> List[RoadPoint]:
        """
        Remove duplicate road points within tolerance distance.
        
        Args:
            points: List of road points
            tolerance: Minimum distance between unique points (meters)
            
        Returns:
            Deduplicated list
        """
        unique: List[RoadPoint] = []
        
        for point in points:
            is_duplicate = False
            for existing in unique:
                dist = calculate_distance(
                    point.lat, point.lon,
                    existing.lat, existing.lon
                )
                if dist < tolerance:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(point)
        
        return unique
