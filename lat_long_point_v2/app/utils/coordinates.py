"""
Coordinate and spatial calculation utilities for Streamlit UI.
"""

import sys
import os

# Add parent directory to path to import from lat_long_point_v2
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from utils.geo import calculate_distance, calculate_bearing

def find_nearest_building(click_lat: float, click_lon: float, geojson: dict, radius: float = 50.0):
    """
    Find the nearest building within a given radius from clicked coordinates.
    
    Args:
        click_lat: Latitude of click
        click_lon: Longitude of click
        geojson: GeoJSON FeatureCollection
        radius: Search radius in meters (default: 50m)
        
    Returns:
        Nearest feature within radius, or None
    """
    candidates = []
    
    # Handle both Feature and FeatureCollection
    features = geojson.get('features', [geojson]) if geojson.get('type') == 'FeatureCollection' else [geojson]
    
    for feature in features:
        if feature.get('type') != 'Feature':
            continue
            
        props = feature.get('properties', {})
        
        # Get building centroid
        building_lat = props.get('latitude')
        building_lon = props.get('longitude')
        
        if building_lat is None or building_lon is None:
            continue
        
        # Convert to float (coordinates might be strings in GeoJSON)
        try:
            building_lat = float(building_lat)
            building_lon = float(building_lon)
        except (ValueError, TypeError):
            continue
        
        # Calculate distance
        dist = calculate_distance(
            click_lat, click_lon,
            building_lat, building_lon
        )
        
        if dist <= radius:
            candidates.append((dist, feature))
    
    if candidates:
        # Sort by distance and return closest
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    
    return None


def extract_centroid_from_geometry(geometry: dict):
    """
    Extract approximate centroid from polygon geometry.
    
    Args:
        geometry: GeoJSON geometry object
        
    Returns:
        (lat, lon) tuple or None
    """
    if not geometry:
        return None
    
    geom_type = geometry.get('type')
    coords = geometry.get('coordinates', [])
    
    if not coords:
        return None
    
    # For Polygon: coords = [[[lon, lat], ...]]
    # For MultiPolygon: coords = [[[[lon, lat], ...]]]
    
    if geom_type == 'Polygon':
        ring = coords[0]  # Exterior ring
    elif geom_type == 'MultiPolygon':
        ring = coords[0][0]  # First polygon, exterior ring
    else:
        return None
    
    if not ring:
        return None
    
    # Simple centroid calculation (average of coordinates)
    lats = [point[1] for point in ring]
    lons = [point[0] for point in ring]
    
    centroid_lat = sum(lats) / len(lats)
    centroid_lon = sum(lons) / len(lons)
    
    return centroid_lat, centroid_lon
