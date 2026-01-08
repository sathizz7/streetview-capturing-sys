"""JSON input and validation component."""

import streamlit as st
import json
from typing import Optional, Dict, Any
import sys
import os

# Add parent directory to path to access lat_long_point_v2 modules
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from app.utils.geojson_helpers import validate_geojson, get_sample_geojson


def render_json_input() -> Optional[Dict]:
    """
    Render JSON input component with validation.
    
    Returns:
        Validated GeoJSON dict or None
    """
    st.markdown("### 📝 Manual JSON Input")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("📋 Load Sample", use_container_width=True):
            st.session_state.json_input = json.dumps(get_sample_geojson(), indent=2)
    
    # Text area for JSON input
    json_text = st.text_area(
        "Paste GeoJSON here:",
        value=st.session_state.get('json_input', ''),
        height=300,
        key='json_textarea',
        help="Paste a valid GeoJSON Feature or FeatureCollection"
    )
    
    if not json_text.strip():
        return None
    
    # Try to parse JSON
    try:
        data = json.loads(json_text)
        
        # Validate GeoJSON structure
        is_valid, error = validate_geojson(data)
        
        if is_valid:
            st.success("✅ Valid GeoJSON")
            return data
        else:
            st.error(f"❌ Validation Error: {error}")
            return None
            
    except json.JSONDecodeError as e:
        st.error(f"❌ JSON Syntax Error: {e}")
        return None


def render_file_uploader() -> Optional[Dict]:
    """
    Render file uploader for GeoJSON files.
    
    Returns:
        Parsed GeoJSON dict or None
    """
    st.markdown("### 📤 Upload GeoJSON File")
    
    uploaded_file = st.file_uploader(
        "Choose a GeoJSON file",
        type=['geojson', 'json'],
        help="Upload a .geojson or .json file containing building data"
    )
    
    if uploaded_file is not None:
        try:
            # Read and parse
            content = uploaded_file.read().decode('utf-8')
            data = json.loads(content)
            
            # Validate
            is_valid, error = validate_geojson(data)
            
            if is_valid:
                # Count features
                feature_count = len(data.get('features', [data]))
                st.success(f"✅ Loaded {feature_count} building(s)")
                return data
            else:
                st.error(f"❌ Validation Error: {error}")
                return None
                
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")
            return None
    
    return None


def render_validation_status(geojson: Optional[Dict]) -> None:
    """
    Display validation status indicator.
    
    Args:
        geojson: GeoJSON data to validate
    """
    if not geojson:
        st.info("ℹ️ No data loaded")
        return
    
    is_valid, error = validate_geojson(geojson)
    
    if is_valid:
        feature_count = len(geojson.get('features', [geojson]))
        st.success(f"✅ Valid GeoJSON with {feature_count} feature(s)")
    else:
        st.error(f"❌ {error}")
