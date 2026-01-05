"""
Geographic utility functions for Building Detection V2.

Provides geodesic calculations for distance, bearing, and position offsets.
Uses the Haversine formula for accuracy.
"""

import math
from typing import Tuple


# Earth radius in meters
EARTH_RADIUS_M = 6371000


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in meters using Haversine formula.
    
    Args:
        lat1, lon1: First point coordinates (degrees)
        lat2, lon2: Second point coordinates (degrees)
        
    Returns:
        Distance in meters
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_M * c


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate bearing from point 1 to point 2.
    
    This is the direction (in degrees, 0-360) that point 2 is from point 1.
    Used to calculate the heading for a camera at point 1 to face point 2.
    
    Args:
        lat1, lon1: Starting point (camera position)
        lat2, lon2: Target point (building location)
        
    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon_diff = math.radians(lon2 - lon1)
    
    x = math.sin(lon_diff) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(lon_diff)
    
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def calculate_position_offset(
    lat: float, 
    lon: float, 
    distance_meters: float, 
    bearing_degrees: float
) -> Tuple[float, float]:
    """
    Calculate new position given distance and bearing from a starting point.
    
    Used to generate sample points around the building for road discovery.
    
    Args:
        lat, lon: Starting point coordinates (degrees)
        distance_meters: Distance to move
        bearing_degrees: Direction to move (0=North, 90=East)
        
    Returns:
        Tuple of (new_lat, new_lon) in degrees
    """
    R = 6378137  # Earth radius in meters (WGS84)
    bearing = math.radians(bearing_degrees)
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    lat2 = math.asin(
        math.sin(lat_rad) * math.cos(distance_meters / R) +
        math.cos(lat_rad) * math.sin(distance_meters / R) * math.cos(bearing)
    )
    
    lon2 = lon_rad + math.atan2(
        math.sin(bearing) * math.sin(distance_meters / R) * math.cos(lat_rad),
        math.cos(distance_meters / R) - math.sin(lat_rad) * math.sin(lat2)
    )
    
    return math.degrees(lat2), math.degrees(lon2)


def calculate_optimal_pitch(distance: float, building_height: float = 12.0) -> float:
    """
    Calculate optimal camera pitch based on distance and estimated building height.
    
    Args:
        distance: Distance from camera to building (meters)
        building_height: Estimated building height (meters, default ~3-4 floors)
        
    Returns:
        Pitch angle in degrees
    """
    EYE_LEVEL_HEIGHT = 1.6  # Street View camera height
    VERTICAL_TARGET_RATIO = 0.5  # Aim at middle of building
    
    # Calculate vertical offset to center of building
    target_height = (building_height * VERTICAL_TARGET_RATIO) - EYE_LEVEL_HEIGHT
    
    if distance > 0 and target_height > 0:
        pitch_radians = math.atan(target_height / distance)
        pitch_degrees = math.degrees(pitch_radians)
    else:
        pitch_degrees = 0
    
    # Apply damping for distant shots
    if distance >= 20:
        pitch_degrees *= 0.85
    
    # Constrain to practical range
    min_pitch = 0 if distance < 20 else -10
    max_pitch = 30
    
    return min(max(pitch_degrees, min_pitch), max_pitch)


def calculate_optimal_fov(distance: float, target_width: float = 15.0) -> float:
    """
    Calculate optimal field of view based on distance and target width.
    
    Args:
        distance: Distance from camera to building (meters)
        target_width: Estimated width to capture (meters)
        
    Returns:
        FOV in degrees
    """
    MARGIN_FACTOR = 1.25  # 25% extra space around building
    
    effective_width = target_width * MARGIN_FACTOR
    required_fov = 2 * math.degrees(math.atan(effective_width / (2 * max(distance, 1))))
    
    MIN_FOV = 40
    MAX_FOV = 90
    
    return min(max(required_fov, MIN_FOV), MAX_FOV)
