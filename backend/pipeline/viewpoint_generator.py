"""
Viewpoint Generator - Pipeline Step 2

Generates camera viewpoints from road points, oriented toward the building.
"""

import logging
from typing import List, Generator

from models import RoadPoint, Viewpoint
from utils import calculate_bearing, calculate_distance, calculate_optimal_pitch, calculate_optimal_fov
from config import get_settings

logger = logging.getLogger(__name__)


class ViewpointGenerator:
    """
    Generates camera viewpoints facing the building from road points.
    
    Key V2 innovation: Since we don't have polygon faces, we calculate
    the bearing from each road point toward the building coordinates.
    """
    
    def __init__(self):
        self.settings = get_settings()
    
    def generate_viewpoints(
        self, 
        building_lat: float, 
        building_lon: float,
        road_points: List[RoadPoint]
    ) -> List[Viewpoint]:
        """
        Generate viewpoints for each road point, facing the building.
        
        Args:
            building_lat: Building latitude
            building_lon: Building longitude
            road_points: List of road points to generate viewpoints from
            
        Returns:
            List of Viewpoint objects with camera parameters
        """
        viewpoints: List[Viewpoint] = []
        
        for road_point in road_points:
            viewpoint = self._create_viewpoint(
                road_point, building_lat, building_lon
            )
            viewpoints.append(viewpoint)
        
        logger.info(f"Generated {len(viewpoints)} viewpoints")
        return viewpoints
    
    def _create_viewpoint(
        self, 
        road_point: RoadPoint, 
        building_lat: float, 
        building_lon: float
    ) -> Viewpoint:
        """
        Create a single viewpoint from a road point.
        
        The camera is positioned at the road point and oriented
        to face the building coordinates.
        """
        # Calculate heading: bearing from road point to building
        heading = calculate_bearing(
            road_point.lat, road_point.lon,
            building_lat, building_lon
        )
        
        # Calculate distance to building
        distance = calculate_distance(
            road_point.lat, road_point.lon,
            building_lat, building_lon
        )
        
        # Calculate optimal pitch based on distance
        pitch = calculate_optimal_pitch(distance)
        
        # Calculate optimal FOV based on distance
        fov = calculate_optimal_fov(distance)
        
        # Constrain to bounds
        pitch = max(self.settings.min_pitch, min(pitch, self.settings.max_pitch))
        fov = max(self.settings.min_fov, min(fov, self.settings.max_fov))
        
        return Viewpoint(
            lat=road_point.lat,
            lon=road_point.lon,
            heading=heading,
            pitch=pitch,
            fov=fov,
            distance_to_building=distance,
            road_type=road_point.road_type
        )
