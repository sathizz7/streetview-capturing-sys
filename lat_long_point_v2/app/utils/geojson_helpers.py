"""
GeoJSON helper utilities for validation and manipulation.
"""

import json
from typing import Dict, Any, List, Optional


def validate_geojson(data: dict) -> tuple[bool, Optional[str]]:
    """
    Validate GeoJSON structure.
    
    Args:
        data: Parsed JSON data
        
    Returns:
        (is_valid, error_message) tuple
    """
    # Check type
    geojson_type = data.get('type')
    if geojson_type not in ['Feature', 'FeatureCollection']:
        return False, f"Invalid type: '{geojson_type}'. Must be 'Feature' or 'FeatureCollection'"
    
    # Validate features
    features = data.get('features', [data]) if geojson_type == 'FeatureCollection' else [data]
    
    for idx, feature in enumerate(features):
        if feature.get('type') != 'Feature':
            return False, f"Feature {idx}: type must be 'Feature'"
        
        # Check properties
        props = feature.get('properties', {})
        if not props:
            return False, f"Feature {idx}: missing 'properties'"
        
        # Check required fields (flexible - latitude/longitude can be computed from geometry)
        has_coords = 'latitude' in props and 'longitude' in props
        has_geometry = 'geometry' in feature and feature['geometry'] is not None
        
        if not has_coords and not has_geometry:
            return False, f"Feature {idx}: must have either (latitude, longitude) in properties OR valid geometry"
        
        # Validate geometry if present
        if has_geometry:
            geometry = feature['geometry']
            geom_type = geometry.get('type')
            
            if geom_type not in ['Polygon', 'MultiPolygon']:
                return False, f"Feature {idx}: geometry type '{geom_type}' not supported. Use Polygon or MultiPolygon"
            
            if 'coordinates' not in geometry:
                return False, f"Feature {idx}: geometry missing 'coordinates'"
    
    return True, None


def enhance_geojson_with_results(geojson: dict, pipeline_results: dict) -> dict:
    """
    Add pipeline results to GeoJSON properties (simplified format).
    
    Args:
        geojson: Original GeoJSON Feature
        pipeline_results: Pipeline output dict
        
    Returns:
        Enhanced GeoJSON Feature
    """
    enhanced = geojson.copy()
    
    # Extract only image URLs (user requested simple format)
    image_urls = []
    if pipeline_results.get('status') == 'success':
        captures = pipeline_results.get('data', {}).get('captures', [])
        image_urls = [c.get('image_url') for c in captures if c.get('image_url')]
    
    # Add to properties
    if 'properties' not in enhanced:
        enhanced['properties'] = {}
    
    enhanced['properties']['pipeline_results'] = {
        'status': pipeline_results.get('status'),
        'execution_time': pipeline_results.get('execution_time'),
        'image_urls': image_urls,
        'analysis': pipeline_results.get('data', {}).get('analysis', {})
    }
    
    return enhanced


def load_geojson_file(filepath: str) -> Optional[dict]:
    """
    Load and parse GeoJSON file.
    
    Args:
        filepath: Path to GeoJSON file
        
    Returns:
        Parsed GeoJSON dict or None
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading GeoJSON: {e}")
        return None


def save_geojson_file(data: dict, filepath: str) -> bool:
    """
    Save GeoJSON to file.
    
    Args:
        data: GeoJSON dict
        filepath: Output path
        
    Returns:
        Success boolean
    """
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving GeoJSON: {e}")
        return False


def get_sample_geojson() -> dict:
    """Return a sample GeoJSON for testing."""
    return {
        "type": "Feature",
        "properties": {
            "latitude": 17.408,
            "longitude": 78.451,
            "area_in_me": 250,
            "confidence": 0.95
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [78.4509, 17.4079],
                [78.4511, 17.4079],
                [78.4511, 17.4081],
                [78.4509, 17.4081],
                [78.4509, 17.4079]
            ]]
        }
    }
