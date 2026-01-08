"""
Viewpoint Generator - Pipeline Step 2

Generates camera viewpoints from road points, oriented toward the building.
"""

import logging
from typing import List, Generator

from models import RoadPoint, Viewpoint
from utils import calculate_bearing, calculate_distance, calculate_optimal_pitch, calculate_optimal_fov
from config import get_settings
from typing import Optional,List
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
        road_points: List[RoadPoint],
        polygon: List[List[float]] = None
    ) -> List[Viewpoint]:
        """
        Generate viewpoints for each road point, facing the building.
        If polygon provided, uses strict frontage validation.
        """
        viewpoints: List[Viewpoint] = []
        
        # If polygon provided, identify the front face
        target_edge = None
        if polygon and len(road_points) > 0 and road_points[0].road_heading is not None:
             # Use the closest road point's heading as reference
             ref_road_heading = road_points[0].road_heading
             target_edge = self._identify_front_face(polygon, ref_road_heading)
             if target_edge:
                 logger.info(f" Identified Front Face Edge: {target_edge}")
        
        for road_point in road_points:
            viewpoint = self._create_viewpoint(
                road_point, building_lat, building_lon
            )
            
            # --- POLYGON VALIDATION ---
            if target_edge:
                # 1. STRICT FRONTAGE: Camera must look Perpendicular to the edge
                # Edge bearing is e.g. 0 deg (North-South wall). 
                # Camera Looking West (270) or East (90).
                # Normal is Edge +/- 90.
                edge_bearing = calculate_bearing(
                    target_edge[0][0], target_edge[0][1],
                    target_edge[1][0], target_edge[1][1]
                )
                
                # Check angle between Camera Heading and Edge
                # Ideally, difference is ~90 degrees.
                # abs(Heading - Edge) % 180 should be approx 90.
                angle_to_edge = abs(viewpoint.heading - edge_bearing) % 180
                if angle_to_edge > 90:
                    angle_to_edge = 180 - angle_to_edge
                
                # Deviation from perfect perpendicular (90 deg)
                deviation = abs(90 - angle_to_edge)
                
                if deviation > 45: # Tolerant range (45-135 deg relative to wall)
                     logger.info(f"Rejected Polygon View: Not facing Front Edge (Deviation {deviation:.1f}°)")
                     continue
                     
                # 2. OPTIONAL: Position Check (Must be "in front" of edge)
                # Omitted for simplicity unless requested, bearing check is strong proxy.

            # --- ANGLE VALIDATION (Fallback if no polygon or complementary) ---
            # Reject if camera looks DOWN the road (Parallel)
            # We want Side Views (~90 deg to road)
            elif road_point.road_heading is not None:
                # Calculate angle difference modulo 180 (bidirectional road)
                diff = abs(viewpoint.heading - road_point.road_heading) % 180
                if diff > 90:
                    diff = 180 - diff
                
                # Rule: Must be > 30 degrees (Road View is < 30)
                if diff < 30:
                    logger.info(f"Rejected viewpoint at {viewpoint.lat},{viewpoint.lon}: Parallel to road (angle_diff={diff:.1f}°)")
                    continue
                
                # Store valid angle difference
                viewpoint.angle_from_road = diff
            
            viewpoints.append(viewpoint)
        
        logger.info(f"Generated {len(viewpoints)} viewpoints (filtered)")
        return viewpoints

    def _identify_front_face(self, polygon: List[List[float]], road_heading: float) -> Optional[tuple]:
        """
        Identify the polygon edge that corresponds to the 'Front Face'.
        Strategy: Find edge most PARALLEL to the road heading.
        Returns: (start_point, end_point) labels.
        """
        best_edge = None
        min_angle_diff = 999.0
        
        # Iterate edges
        for i in range(len(polygon)):
            p1 = polygon[i]
            p2 = polygon[(i + 1) % len(polygon)]
            
            # Edge bearing
            edge_bearing = calculate_bearing(p1[0], p1[1], p2[0], p2[1])
            
            # Parallel check: Difference should be close to 0 or 180
            diff = abs(edge_bearing - road_heading) % 180
            if diff > 90:
                diff = 180 - diff
            
            # Minimize difference (Closest to 0)
            if diff < min_angle_diff:
                min_angle_diff = diff
                best_edge = (p1, p2)
        
        # Threshold: If best edge is not parallel enough (> 30 deg off), maybe invalid
        if min_angle_diff > 45:
             logger.warning(f"No clear parallel front face found (Best diff: {min_angle_diff}°)")
             return None
             
        return best_edge
    
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
