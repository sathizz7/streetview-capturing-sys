"""
Building Capture System - Streamlit UI

Interactive web interface for the Building Detection V2 Pipeline.
Features 3-step wizard flow with async batch processing.
"""

import streamlit as st
import os
import glob
import sys

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from app.components.map_viewer import render_map_viewer, display_building_info, get_building_id
from app.components.json_validator import render_file_uploader, render_json_input
from app.components.pipeline_runner import render_pipeline_controls, render_analysis_in_progress
from app.components.results_display import render_results_display
from app.components.wizard_ui import render_wizard_stepper, render_step_content_header
from app.utils.coordinates import find_nearest_building, extract_centroid_from_geometry
from app.utils.geojson_helpers import load_geojson_file


# Page configuration
st.set_page_config(
    page_title="Building Analyser",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for overall styling
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .main-header h1 {
        color: white;
        margin: 0;
    }
    .main-header p {
        color: rgba(255,255,255,0.8);
        margin: 5px 0 0 0;
    }
    
    /* Card styling */
    .stMetric {
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    
    /* Button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #5a6fd6 0%, #6a4190 100%);
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        'selected_building': None,
        'batch_queue': [],
        'pipeline_results': None,
        'geojson_data': None,
        'current_step': 1,  # 1=Selection, 2=Analysis, 3=Results
        'processing_status': {},  # building_id -> status
        'max_concurrent': 3,
        'current_file_path': None,  # Track loaded file path for persistence
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_analysis():
    """Reset to initial state for new analysis."""
    st.session_state.selected_building = None
    st.session_state.batch_queue = []
    st.session_state.pipeline_results = None
    st.session_state.current_step = 1
    st.session_state.processing_status = {}
    st.rerun()


def set_step(step: int):
    """Set current wizard step."""
    st.session_state.current_step = step


def render_sidebar():
    """Render sidebar with data source and settings."""
    with st.sidebar:
        # App branding
        st.markdown("## 🏢 Building Analyser")
        st.caption("Analyze building information from map selection")
        
        st.divider()
        
        # --- Pipeline Settings ---
        with st.expander("⚙️ Pipeline Settings", expanded=False):
            st.session_state.max_concurrent = st.slider(
                "Max Concurrent Buildings",
                min_value=1,
                max_value=3,
                value=st.session_state.max_concurrent,
                help="Number of buildings to process simultaneously in batch mode"
            )
        
        st.divider()
        
        # --- Data Source Selection ---
        st.header("📁 Data Source")
        
        data_source = st.radio(
            "Choose data source:",
            options=["Upload New GeoJSON", "Load Existing Data", "Manual JSON Input"],
            index=0,
            label_visibility="collapsed"
        )
        
        # Handle data source selection
        if data_source == "Upload New GeoJSON":
            uploaded_data = render_file_uploader()
            if uploaded_data:
                st.session_state.geojson_data = uploaded_data
        
        elif data_source == "Load Existing Data":
            data_dir = os.path.join(parent_dir, "data", "buildings")
            os.makedirs(data_dir, exist_ok=True)
            
            geojson_files = glob.glob(os.path.join(data_dir, "*.geojson")) + \
                          glob.glob(os.path.join(data_dir, "*.json"))
            
            if geojson_files:
                selected_file = st.selectbox(
                    "Select file:",
                    options=[os.path.basename(f) for f in geojson_files]
                )
                
                if st.button("📂 Load File", use_container_width=True):
                    filepath = os.path.join(data_dir, selected_file)
                    loaded_data = load_geojson_file(filepath)
                    if loaded_data:
                        st.session_state.geojson_data = loaded_data
                        st.session_state.current_file_path = filepath
                        
                        # Populate processing status from existing results
                        features = loaded_data.get('features', [loaded_data])
                        processed_count = 0
                        for f in features:
                            props = f.get('properties', {})
                            if 'pipeline_results' in props:
                                f_id = get_building_id(f)
                                st.session_state.processing_status[f_id] = 'completed'
                                processed_count += 1
                        
                        st.success(f"Loaded: {selected_file} ({processed_count} previously analyzed)")
            else:
                st.info("No files found in data/buildings/")
        
        elif data_source == "Manual JSON Input":
            manual_data = render_json_input()
            if manual_data:
                st.session_state.geojson_data = manual_data
        
        st.divider()
        
        # --- Selected Building Info ---
        st.header("🏢 Selected Building")
        display_building_info(st.session_state.selected_building)
        
        # --- Batch Queue Display ---
        if st.session_state.batch_queue:
            st.divider()
            st.subheader(f"📋 Batch Queue ({len(st.session_state.batch_queue)})")
            
            # Color legend
            st.markdown("""
            <div style="font-size: 12px; margin-bottom: 10px;">
                <span style="color: #fd7e14;">● Queued</span> | 
                <span style="color: #9b59b6;">● Processing</span> | 
                <span style="color: #28a745;">● Done</span>
            </div>
            """, unsafe_allow_html=True)
            
            with st.expander("View Queue", expanded=True):
                for i, b in enumerate(st.session_state.batch_queue):
                    props = b.get('properties', {})
                    b_id = get_building_id(b)
                    status = st.session_state.processing_status.get(b_id, 'queued')
                    
                    # Status indicator
                    status_colors = {
                        'queued': '🟠',
                        'processing': '🟣',
                        'completed': '🟢',
                        'error': '🔴'
                    }
                    indicator = status_colors.get(status, '⚪')
                    
                    lat_val = props.get('latitude')
                    lon_val = props.get('longitude')
                    
                    try:
                        lat_str = f"{float(lat_val):.4f}" if lat_val is not None else "N/A"
                        lon_str = f"{float(lon_val):.4f}" if lon_val is not None else "N/A"
                    except (ValueError, TypeError):
                        lat_str = str(lat_val) if lat_val is not None else "N/A"
                        lon_str = str(lon_val) if lon_val is not None else "N/A"

                    st.text(f"{indicator} {i+1}. ({lat_str}, {lon_str})")
            
            if st.button("🗑️ Clear Queue", use_container_width=True):
                st.session_state.batch_queue = []
                st.session_state.processing_status = {}
                st.rerun()



def render_map_section():
    """Render the shared map section and handle selection."""
    if st.session_state.geojson_data:
        # Determine map center
        features = st.session_state.geojson_data.get('features', [st.session_state.geojson_data])
        if features:
            first_feature = features[0]
            props = first_feature.get('properties', {})
            center_lat = props.get('latitude')
            center_lon = props.get('longitude')
            
            # If not in properties, compute from geometry
            if center_lat is None or center_lon is None:
                centroid = extract_centroid_from_geometry(first_feature.get('geometry'))
                if centroid:
                    center_lat, center_lon = centroid
                else:
                    center_lat, center_lon = 17.408, 78.451
        else:
            center_lat, center_lon = 17.408, 78.451
        
        map_data = render_map_viewer(
            st.session_state.geojson_data,
            center=(center_lat, center_lon),
            zoom=16,
            queued_buildings=st.session_state.batch_queue,
            processing_status=st.session_state.processing_status,
            selected_building=st.session_state.selected_building
        )
        
        # Handle map clicks
        if map_data and map_data.get('last_clicked'):
            clicked_lat = map_data['last_clicked']['lat']
            clicked_lon = map_data['last_clicked']['lng']
            
            # Find nearest building within 50m
            selected = find_nearest_building(
                clicked_lat,
                clicked_lon,
                st.session_state.geojson_data,
                radius=50.0
            )
            
            if selected:
                # Only rerun if selection actually changed
                current_id = get_building_id(st.session_state.selected_building) if st.session_state.selected_building else None
                new_id = get_building_id(selected)
                
                if current_id != new_id:
                    st.session_state.selected_building = selected
                    st.rerun()
            else:
                st.warning("⚠️ No building found within 50m of click")
    else:
        st.info("📍 Load or upload GeoJSON data to display buildings on the map")


def render_step_content():
    """Render content based on current step, maintaining map visibility."""
    
    # --- Layout Strategy ---
    # We want the map to be visible in all steps.
    # Step 1 & 2: Map on Left (2/3), Controls/Status on Right (1/3)
    # Step 3: Map on Left (1/2) or Top, Results on Right/Bottom?
    # Let's stick to 2-column layout for consistency for now.
    
    col_map, col_content = st.columns([2, 1])
    
    with col_map:
        render_map_section()
        
    with col_content:
        # --- Step 1: Selection & Controls ---
        if st.session_state.current_step == 1:
            st.markdown("### Step 1: Building Selection")
            st.caption("Select a building on the map.")
            
            pipeline_result = render_pipeline_controls(
                st.session_state.selected_building,
                batch_queue=st.session_state.batch_queue,
                max_concurrent=st.session_state.max_concurrent,
                on_step_change=set_step
            )
            
            if pipeline_result:
                st.session_state.pipeline_results = pipeline_result
                st.session_state.current_step = 3
                st.rerun()
        
        # --- Step 2: Analysis Progress ---
        elif st.session_state.current_step == 2:
            render_analysis_in_progress(
                st.session_state.processing_status,
                st.session_state.batch_queue or [st.session_state.selected_building]
            )
            
        # --- Step 3: Results Summary (Side) ---
        elif st.session_state.current_step == 3:
            st.markdown("### ✅ Analysis Complete")
            if st.button("🔄 Start New Analysis", type="primary"):
                 reset_analysis()
            
            # Show mini summary
            if st.session_state.pipeline_results:
                 res_type = st.session_state.pipeline_results.get('type')
                 if res_type == 'batch':
                     total = len(st.session_state.pipeline_results.get('results', {}))
                     st.metric("Processed Buildings", total)
                 else:
                     st.success("Building processed successfully.")

    # --- Full Width Results Section (Below Map) ---
    if st.session_state.current_step == 3:
        st.divider()
        render_step_3_results()  # This renders the full results UI below


def render_step_3_results():
    """Render Step 3: Analysis Results."""
    if not st.session_state.pipeline_results:
        st.warning("No results available.")
        return
    
    # Handle Batch vs Single results
    res_type = st.session_state.pipeline_results.get('type')
    results_data = st.session_state.pipeline_results.get('results')
    
    if res_type == 'batch':
        st.markdown("## 📊 Batch Analysis Results")
        
        # Summary
        total = len(results_data)
        success_count = sum(1 for r in results_data.values() if r.get('status') == 'success')
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Buildings", total)
        with col2:
            st.metric("Successful", success_count)
        with col3:
            st.metric("Failed", total - success_count)
        
        st.divider()
        
        # Individual results
        for b_id, res in results_data.items():
            status_emoji = "✅" if res.get('status') == 'success' else "❌"
            with st.expander(f"{status_emoji} Building: {b_id}", expanded=True):
                render_results_display(res, None, on_new_analysis=reset_analysis)
                
    elif res_type == 'single':
        render_results_display(
            results_data,
            st.session_state.selected_building,
            on_new_analysis=reset_analysis
        )
    
    # Fallback
    elif 'status' in st.session_state.pipeline_results:
        render_results_display(
            st.session_state.pipeline_results,
            st.session_state.selected_building,
            on_new_analysis=reset_analysis
        )


def main():
    """Main application entry point."""
    # Initialize session state
    init_session_state()
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🏢 Building Analyser</h1>
        <p>Analyze building information from map selection</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Render sidebar
    render_sidebar()
    
    # Wizard Stepper
    render_wizard_stepper(st.session_state.current_step)
    
    st.divider()
    
    # Main content based on current step
    render_step_content()


if __name__ == "__main__":
    main()
