"""Map viewer component with Folium integration."""

import streamlit as st
import folium
from streamlit_folium import st_folium
from typing import Optional, Dict, Any, List


# Color palette for building states
BUILDING_COLORS = {
    'default': {'fill': '#3388ff', 'stroke': '#2c5aa0'},      # Blue
    'selected': {'fill': '#ffc107', 'stroke': '#d39e00'},     # Yellow
    'queued': {'fill': '#fd7e14', 'stroke': '#dc6a12'},       # Orange
    'processing': {'fill': '#9b59b6', 'stroke': '#8e44ad'},   # Purple
    'completed': {'fill': '#28a745', 'stroke': '#1e7e34'},    # Green
    'error': {'fill': '#dc3545', 'stroke': '#c82333'},        # Red
}


def get_building_id(feature: Dict) -> str:
    """Generate unique ID for a building feature."""
    props = feature.get('properties', {})
    lat = props.get('latitude', 0)
    lon = props.get('longitude', 0)
    return f"{lat}_{lon}"


def render_map_viewer(
    geojson_data: Optional[Dict[Any, Any]] = None,
    center: tuple = (17.408, 78.451),
    zoom: int = 15,
    queued_buildings: Optional[List[Dict]] = None,
    processing_status: Optional[Dict[str, str]] = None,
    selected_building: Optional[Dict] = None
) -> Optional[Dict]:
    """
    Render interactive Folium map with GeoJSON overlay.
    
    Args:
        geojson_data: GeoJSON FeatureCollection or Feature
        center: (lat, lon) tuple for map center
        zoom: Initial zoom level
        queued_buildings: List of buildings in queue
        processing_status: Dict mapping building_id -> status (processing/completed/error)
        selected_building: Currently selected building feature
        
    Returns:
        Map interaction data
    """
    # Create base map
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles='OpenStreetMap'
    )
    
    # Build lookup sets for quick status checking
    queued_ids = set()
    if queued_buildings:
        for b in queued_buildings:
            queued_ids.add(get_building_id(b))
    
    selected_id = None
    if selected_building:
        selected_id = get_building_id(selected_building)
    
    # Add GeoJSON layer if data provided
    if geojson_data:
        def get_feature_style(feature):
            feature_id = get_building_id(feature)
            
            # Priority: processing_status > selected > queued > default
            if processing_status and feature_id in processing_status:
                status = processing_status[feature_id]
                colors = BUILDING_COLORS.get(status, BUILDING_COLORS['default'])
                weight = 3 if status == 'processing' else 2
                opacity = 0.7 if status in ('processing', 'completed') else 0.5
                return {
                    'fillColor': colors['fill'],
                    'color': colors['stroke'],
                    'weight': weight,
                    'fillOpacity': opacity
                }
            
            if feature_id == selected_id:
                colors = BUILDING_COLORS['selected']
                return {
                    'fillColor': colors['fill'],
                    'color': colors['stroke'],
                    'weight': 3,
                    'fillOpacity': 0.6
                }
            
            if feature_id in queued_ids:
                colors = BUILDING_COLORS['queued']
                return {
                    'fillColor': colors['fill'],
                    'color': colors['stroke'],
                    'weight': 2,
                    'fillOpacity': 0.5
                }
            
            # Default style
            colors = BUILDING_COLORS['default']
            return {
                'fillColor': colors['fill'],
                'color': colors['stroke'],
                'weight': 2,
                'fillOpacity': 0.4
            }

        # Determine available fields for tooltip from actual data
        tooltip_fields = []
        tooltip_aliases = []
        
        # Check first feature for available properties
        if geojson_data and hasattr(geojson_data, 'get'):
            features = geojson_data.get('features', [geojson_data])
            if features:
                first_props = features[0].get('properties', {})
                all_keys = list(first_props.keys())
                
                # prioritized keys to show first if they exist
                priority_keys = [
                    'latitude', 'lat', 'Lat', 
                    'longitude', 'lon', 'long', 'Long', 
                    'area_in_me', 'area_in_meter_sq', 'Area', 'Shape_Area', 'Polyg_Area',
                    'confidence', 'Confidence', 'score',
                    'id', 'ID', 'Building_U', 'RoadName'
                ]
                
                # Add found priority keys first
                for key in priority_keys:
                    if key in all_keys and key not in tooltip_fields:
                        tooltip_fields.append(key)
                        tooltip_aliases.append(key.replace('_', ' ').title())
                        
                # Add other keys up to a limit
                for key in all_keys:
                    if len(tooltip_fields) >= 6:  # Limit tooltip to 6 fields to prevent clutter
                        break
                    if key not in tooltip_fields and not isinstance(first_props[key], (dict, list)):
                        tooltip_fields.append(key)
                        tooltip_aliases.append(key.replace('_', ' ').title())
        
        # Fallback if no fields found (prevent empty tooltip crash)
        if not tooltip_fields:
            tooltip = None
        else:
            tooltip = folium.GeoJsonTooltip(
                fields=tooltip_fields,
                aliases=tooltip_aliases,
                sticky=False
            )

        folium.GeoJson(
            geojson_data,
            name='Buildings',
            tooltip=tooltip,
            style_function=get_feature_style,
            highlight_function=lambda x: {
                'fillColor': '#ffaa00',
                'color': '#ff6600',
                'weight': 3,
                'fillOpacity': 0.7
            }
        ).add_to(m)


    
    # Render map
    map_data = st_folium(
        m,
        width=900,
        height=600,
        returned_objects=['last_clicked']
    )
    
    return map_data



def display_building_info(building: Optional[Dict]) -> None:
    """
    Display building information in sidebar.
    
    Args:
        building: GeoJSON Feature
    """
    if not building:
        st.sidebar.info("👆 Click on the map to select a building")
        return
    
    st.sidebar.success("✅ Building Selected")
    
    props = building.get('properties', {})
    
    # Function to safely format float values
    def safe_format(val):
        try:
            return f"{float(val):.6f}"
        except (ValueError, TypeError):
             return str(val)

    # Display properties
    st.sidebar.metric("Latitude", safe_format(props.get('latitude', 'N/A')))
    st.sidebar.metric("Longitude", safe_format(props.get('longitude', 'N/A')))
    
    if 'area_in_me' in props:
        try:
            area = float(props['area_in_me'])
            st.sidebar.metric("Area", f"{area:.2f} m²")
        except (ValueError, TypeError):
             st.sidebar.metric("Area", str(props['area_in_me']))
    
    if 'confidence' in props:
        try:
           conf = float(props['confidence'])
           st.sidebar.metric("Confidence", f"{conf:.2%}")
        except (ValueError, TypeError):
           st.sidebar.metric("Confidence", str(props['confidence']))
    
    # Show other properties
    with st.sidebar.expander("📋 All Properties"):
        st.json(props)
