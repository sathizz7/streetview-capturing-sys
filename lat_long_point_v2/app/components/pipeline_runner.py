"""Pipeline execution component with async batch processing."""

import streamlit as st
import asyncio
import sys
import os
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from main import BuildingCapturePipeline
from app.components.map_viewer import get_building_id
from app.utils.geojson_helpers import update_feature_properties, update_geojson_collection, save_geojson_file


def extract_polygon_from_geometry(geometry: dict) -> Optional[List[List[float]]]:
    """
    Extract polygon coordinates from GeoJSON geometry.
    Handles both Polygon and MultiPolygon, converts [lon, lat] to [lat, lon].
    
    Args:
        geometry: GeoJSON geometry object
        
    Returns:
        List of [lat, lon] points or None
    """
    if not geometry:
        return None
    
    geom_type = geometry.get('type')
    coords = geometry.get('coordinates', [])
    
    if not coords:
        return None
    
    # Extract exterior ring
    if geom_type == 'Polygon':
        ring = coords[0]  # First ring (exterior)
    elif geom_type == 'MultiPolygon':
        ring = coords[0][0]  # First polygon, first ring
    else:
        return None
    
    # Convert [lon, lat] to [lat, lon]
    return [[point[1], point[0]] for point in ring]


async def run_pipeline_async(building_data: Dict) -> Dict[str, Any]:
    """
    Run the building capture pipeline asynchronously.
    
    Args:
        building_data: GeoJSON Feature
        
    Returns:
        Pipeline results dict
    """
    props = building_data.get('properties', {})
    geometry = building_data.get('geometry')
    
    # Extract coordinates
    lat = props.get('latitude')
    lon = props.get('longitude')
    
    # Ensure they are floats
    try:
        if lat is not None:
            lat = float(lat)
        if lon is not None:
            lon = float(lon)
    except (ValueError, TypeError):
        # If conversion fails, set to None so fallback logic can run
        lat = None
        lon = None
    
    # If not in properties, try to compute from geometry
    if lat is None or lon is None:
        if geometry:
            polygon = extract_polygon_from_geometry(geometry)
            if polygon:
                # Use centroid
                lats = [p[0] for p in polygon]
                lons = [p[1] for p in polygon]
                lat = sum(lats) / len(lats)
                lon = sum(lons) / len(lons)
    
    if lat is None or lon is None:
        return {
            'status': 'error',
            'message': 'Could not extract latitude/longitude from building data'
        }
    
    # Extract polygon
    polygon = extract_polygon_from_geometry(geometry) if geometry else None
    
    # Initialize pipeline
    pipeline = BuildingCapturePipeline()
    
    # Run pipeline
    result = await pipeline.capture_building(
        lat=lat,
        lon=lon,
        skip_llm=False,
        polygon=polygon
    )
    
    return result


async def run_single_building_with_status(
    building: Dict,
    status_callback: callable = None,
    result_callback: callable = None
) -> tuple:
    """
    Run pipeline for a single building with status updates.
    
    Args:
        building: GeoJSON Feature
        status_callback: Async callback for status updates
        result_callback: Async callback for result handling (persistence)
        
    Returns:
        Tuple of (building_id, result)
    """
    building_id = get_building_id(building)
    
    try:
        if status_callback:
            await status_callback(building_id, 'processing')
        
        result = await run_pipeline_async(building)
        
        status = 'completed' if result.get('status') == 'success' else 'error'
        if status_callback:
            await status_callback(building_id, status)
            
        if result_callback:
            await result_callback(building_id, building, result)
        
        return (building_id, result)
        
    except Exception as e:
        error_res = {'status': 'error', 'message': str(e)}
        if status_callback:
            await status_callback(building_id, 'error')
        if result_callback:
             await result_callback(building_id, building, error_res)
        return (building_id, error_res)


async def run_batch_pipeline_async(
    buildings: List[Dict], 
    max_concurrent: int = 3,
    progress_callback: callable = None,
    status_callback: callable = None,
    result_callback: callable = None
) -> Dict[str, Any]:
    """
    Run the pipeline for a batch of buildings with concurrency control.
    
    Args:
        buildings: List of GeoJSON Features
        max_concurrent: Maximum number of concurrent pipelines (1-3)
        progress_callback: Optional async callback for progress updates (current, total, msg)
        status_callback: Optional async callback for per-building status updates (building_id, status)
        result_callback: Optional async callback for result persistence
        
    Returns:
        Dict mapping building ID to results
    """
    batch_results = {}
    total = len(buildings)
    
    # Ensure max_concurrent is within bounds
    max_concurrent = min(max(1, max_concurrent), 3)
    
    # Process in chunks based on max_concurrent
    for chunk_start in range(0, total, max_concurrent):
        chunk_end = min(chunk_start + max_concurrent, total)
        chunk = buildings[chunk_start:chunk_end]
        
        if progress_callback:
            await progress_callback(
                chunk_start + 1, 
                total, 
                f"Processing buildings {chunk_start + 1}-{chunk_end} of {total}..."
            )
        
        # Run chunk concurrently
        tasks = [
            run_single_building_with_status(b, status_callback, result_callback)
            for b in chunk
        ]
        
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect results
        for result in chunk_results:
            if isinstance(result, Exception):
                # Handle unexpected exceptions
                continue
            building_id, pipeline_result = result
            batch_results[building_id] = pipeline_result
    
    if progress_callback:
        await progress_callback(total, total, "Batch processing complete!")
    
    return batch_results


def render_pipeline_controls(
    building_data: Optional[Dict], 
    batch_queue: Optional[List[Dict]] = None,
    max_concurrent: int = 3,
    on_step_change: callable = None
) -> Optional[Dict]:
    """
    Render pipeline execution controls and handle execution (Single or Batch).
    
    Args:
        building_data: Currently selected building GeoJSON Feature
        batch_queue: List of buildings in the batch queue
        max_concurrent: Max concurrent pipelines for batch processing
        on_step_change: Callback to change wizard step
        
    Returns:
        Pipeline results dict or None
    """
    st.markdown("### 🚀 Analysis Controls")
    
    # Persistence callback
    async def on_building_complete(b_id, building, result):
        """Save result to session state and disk."""
        if result.get('status') == 'success':
            # Update feature properties
            updated_building = update_feature_properties(building, result)
            
            # Update in global GeoJSON collection
            if st.session_state.geojson_data:
                update_geojson_collection(st.session_state.geojson_data, updated_building)
                
            # Auto-save to disk if file path exists
            file_path = st.session_state.get('current_file_path')
            if file_path and st.session_state.geojson_data:
                save_geojson_file(st.session_state.geojson_data, file_path)
    
    # --- Batch Mode ---
    if batch_queue and len(batch_queue) > 0:
        st.info(f"📋 Batch Queue: {len(batch_queue)} buildings ready")
        
        # Show queued buildings with colors
        with st.expander("View Queued Buildings", expanded=False):
            for i, b in enumerate(batch_queue):
                props = b.get('properties', {})
                st.markdown(f"**{i+1}.** ({props.get('latitude', 'N/A')}, {props.get('longitude', 'N/A')})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 Run Batch Analysis", type="primary", use_container_width=True):
                # Transition to Analysis step
                if on_step_change:
                    on_step_change(2)
                
                # Initialize processing status
                if 'processing_status' not in st.session_state:
                    st.session_state.processing_status = {}
                
                # Mark all as queued initially
                for b in batch_queue:
                    b_id = get_building_id(b)
                    st.session_state.processing_status[b_id] = 'queued'
                
                with st.spinner("Running batch analysis..."):
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()
                    
                    async def update_progress(current, total, msg):
                        progress_bar.progress(current / total)
                        status_text.text(msg)
                    
                    async def update_status(building_id, status):
                        st.session_state.processing_status[building_id] = status
                    
                    # Run batch
                    results = asyncio.run(run_batch_pipeline_async(
                        batch_queue, 
                        max_concurrent=max_concurrent,
                        progress_callback=update_progress,
                        status_callback=update_status,
                        result_callback=on_building_complete
                    ))
                    
                    # Clear progress
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Transition to Results step
                    if on_step_change:
                        on_step_change(3)
                    
                    st.success(f"✅ Batch Analysis Completed! Results saved to {st.session_state.get('current_file_path', 'unknown')}")
                    return {'type': 'batch', 'results': results}
        
        with col2:
            if st.button("🗑️ Clear Queue", use_container_width=True):
                st.session_state.batch_queue = []
                st.session_state.processing_status = {}
                st.rerun()
        
        return None

    # --- Single Mode ---
    if not building_data:
        st.warning("⚠️ No building selected. Click on the map to select a building.")
        return None
    
    # Display building info
    props = building_data.get('properties', {})
    lat = props.get('latitude', 'N/A')
    lon = props.get('longitude', 'N/A')
    
    st.info(f"📍 Target: {lat}, {lon}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Single execution button
        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            # Transition to Analysis step
            if on_step_change:
                on_step_change(2)
            
            building_id = get_building_id(building_data)
            
            # Initialize processing status
            if 'processing_status' not in st.session_state:
                st.session_state.processing_status = {}
            st.session_state.processing_status[building_id] = 'processing'
            
            with st.spinner("Running pipeline..."):
                progress_placeholder = st.empty()
                progress_placeholder.info("🔍 Processing building analysis...")
                
                try:

                    # Run single pipeline using the wrapper to handle persistence
                    result = asyncio.run(run_single_building_with_status(
                        building_data, 
                        result_callback=on_building_complete
                    ))
                    # Result is tuple (id, result)
                    result = result[1]
                    
                    progress_placeholder.empty()
                    
                    # Update status
                    status = 'completed' if result.get('status') == 'success' else 'error'
                    st.session_state.processing_status[building_id] = status
                    
                    # Transition to Results step
                    if on_step_change:
                        on_step_change(3)
                    
                    if result.get('status') == 'success':
                        st.success("✅ Analysis completed and saved!")
                        return {'type': 'single', 'results': result}
                    else:
                        st.error(f"❌ Pipeline failed: {result.get('message', 'Unknown error')}")
                        return {'type': 'single', 'results': result}
                        
                except Exception as e:
                    progress_placeholder.empty()
                    st.session_state.processing_status[building_id] = 'error'
                    st.error(f"❌ Error running pipeline: {e}")
                    return {'type': 'single', 'results': {'status': 'error', 'message': str(e)}}
    
    with col2:
        # Add to batch button
        if st.button("➕ Add to Batch", use_container_width=True):
            if 'batch_queue' not in st.session_state:
                st.session_state.batch_queue = []
            
            # Check if already in queue
            building_id = get_building_id(building_data)
            existing_ids = [get_building_id(b) for b in st.session_state.batch_queue]
            
            if building_id not in existing_ids:
                if len(st.session_state.batch_queue) < 10:  # Max 10 in queue
                    st.session_state.batch_queue.append(building_data)
                    st.success("Added to queue!")
                    st.rerun()
                else:
                    st.warning("Queue is full (max 10 buildings)")
            else:
                st.info("Already in queue")
    
    return None


def render_analysis_in_progress(
    processing_status: Dict[str, str],
    batch_queue: List[Dict]
) -> None:
    """
    Render the analysis in progress view (Step 2).
    
    Args:
        processing_status: Dict mapping building_id -> status
        batch_queue: List of buildings being processed
    """
    st.markdown("### Step 2: Analysis in Progress")
    st.caption("Processing your building analysis request...")
    
    # Spinner animation
    st.markdown("""
    <div style="display: flex; justify-content: center; padding: 40px;">
        <div class="lds-ring"><div></div><div></div><div></div><div></div></div>
    </div>
    <style>
    .lds-ring {
        display: inline-block;
        position: relative;
        width: 80px;
        height: 80px;
    }
    .lds-ring div {
        box-sizing: border-box;
        display: block;
        position: absolute;
        width: 64px;
        height: 64px;
        margin: 8px;
        border: 8px solid #9b59b6;
        border-radius: 50%;
        animation: lds-ring 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
        border-color: #9b59b6 transparent transparent transparent;
    }
    .lds-ring div:nth-child(1) { animation-delay: -0.45s; }
    .lds-ring div:nth-child(2) { animation-delay: -0.3s; }
    .lds-ring div:nth-child(3) { animation-delay: -0.15s; }
    @keyframes lds-ring {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Status summary
    if processing_status:
        processing_count = sum(1 for s in processing_status.values() if s == 'processing')
        completed_count = sum(1 for s in processing_status.values() if s == 'completed')
        total = len(processing_status)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", "IN_PROGRESS" if processing_count > 0 else "COMPLETE")
        with col2:
            st.metric("Progress", f"{completed_count}/{total}")
