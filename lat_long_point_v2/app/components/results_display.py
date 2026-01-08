"""Enhanced results display component with quality summary and image gallery."""

import streamlit as st
import json
from typing import Dict, Any, Optional, List
import sys
import os

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

from app.utils.geojson_helpers import enhance_geojson_with_results


def render_quality_summary(pipeline_results: Dict) -> None:
    """
    Render quality summary cards matching reference UI.
    
    Args:
        pipeline_results: Pipeline output dict
    """
    st.markdown("### Quality Summary")
    
    # Calculate metrics
    captures = pipeline_results.get('captures', [])
    data = pipeline_results.get('data', {})
    
    # Try different result structures
    if not captures and data:
        captures = data.get('captures', [])
    
    # Calculate average quality score
    quality_scores = []
    for capture in captures:
        # Try different score locations
        score = capture.get('final_quality_score', 0)
        if not score:
            screening = capture.get('screening_result', {})
            if screening:
                score = screening.get('building_coverage_pct', 0)
        quality_scores.append(score)
    
    avg_score = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    ready_captures = len([c for c in captures if c.get('image_url')])
    
    # Render metric cards
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        ">
            <span style="color: #28a745; font-size: 14px; font-weight: 500;">Average Score</span>
            <h2 style="color: #155724; margin: 10px 0 0 0; font-size: 36px;">{:.1f}</h2>
        </div>
        """.format(avg_score), unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        ">
            <span style="color: #28a745; font-size: 14px; font-weight: 500;">Ready Captures</span>
            <h2 style="color: #155724; margin: 10px 0 0 0; font-size: 36px;">{}</h2>
        </div>
        """.format(ready_captures), unsafe_allow_html=True)


def render_image_gallery(captures: list) -> None:
    """
    Display Street View images in an enhanced grid layout.
    
    Args:
        captures: List of CaptureResult dicts
    """
    if not captures:
        st.warning("No images captured")
        return
    
    # Get valid captures with images
    valid_captures = [c for c in captures if c.get('image_url')]
    
    if not valid_captures:
        st.warning("No valid images found")
        return
    
    st.markdown(f"### Street View Captures ({len(valid_captures)})")
    
    # Display images in 2-column grid
    cols_per_row = 2
    
    for i in range(0, len(valid_captures), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(valid_captures):
                break
            
            capture = valid_captures[idx]
            image_url = capture.get('image_url')
            
            with col:
                # Image container with styling
                st.markdown("""
                <div style="
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                    margin-bottom: 20px;
                ">
                """, unsafe_allow_html=True)
                
                st.image(image_url, use_container_width=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
                
                # Quality badge and details
                viewpoint = capture.get('viewpoint', {})
                quality_score = capture.get('final_quality_score', 0)
                
                # Show compact details
                detail_cols = st.columns(3)
                
                with detail_cols[0]:
                    distance = viewpoint.get('distance_to_building', 0)
                    st.caption(f"📏 {distance:.0f}m")
                
                with detail_cols[1]:
                    heading = viewpoint.get('heading', 0)
                    st.caption(f"🧭 {heading:.0f}°")
                
                with detail_cols[2]:
                    if quality_score > 0:
                        st.caption(f"⭐ {quality_score:.0f}")
                
                # Expandable URL
                with st.expander("🔗 Image URL"):
                    st.code(image_url, language="text")


def render_analysis(analysis: Optional[Dict]) -> None:
    """
    Display building analysis results.
    
    Args:
        analysis: BuildingAnalysis dict
    """
    if not analysis:
        return
    
    st.markdown("### 🏢 Building Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Building Type:**")
        st.write(analysis.get('building_usage_summary', analysis.get('building_type', 'N/A')))
        
        st.markdown("**Visual Description:**")
        st.write(analysis.get('visual_description', analysis.get('description', 'N/A')))
    
    with col2:
        establishments = analysis.get('establishments', [])
        if establishments:
            st.markdown("**Visible Establishments:**")
            for est in establishments:
                name = est.get('name', est) if isinstance(est, dict) else str(est)
                st.write(f"- {name}")
        else:
            st.info("No establishments identified")
    
    # Address if available
    address = analysis.get('address', analysis.get('formatted_address'))
    if address:
        st.markdown("**Address:**")
        st.write(address)
    
    # Full analysis in expander
    with st.expander("📋 View Full Analysis JSON"):
        st.json(analysis)


def render_export_controls(pipeline_results: Dict, building_data: Optional[Dict]) -> None:
    """
    Render export controls for results.
    
    Args:
        pipeline_results: Pipeline output
        building_data: Original GeoJSON Feature
    """
    st.markdown("### 💾 Export Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Full JSON export
        full_json = json.dumps(pipeline_results, indent=2)
        st.download_button(
            label="📥 Full Results (JSON)",
            data=full_json,
            file_name="pipeline_results.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col2:
        # Enhanced GeoJSON export
        if building_data:
            enhanced = enhance_geojson_with_results(building_data, pipeline_results)
            enhanced_json = json.dumps(enhanced, indent=2)
            
            st.download_button(
                label="📥 Enhanced GeoJSON",
                data=enhanced_json,
                file_name="building_with_results.geojson",
                mime="application/json",
                use_container_width=True
            )
    
    with col3:
        # Image URLs as simple list
        captures = pipeline_results.get('captures', [])
        if not captures:
            captures = pipeline_results.get('data', {}).get('captures', [])
        
        image_urls = [c.get('image_url') for c in captures if c.get('image_url')]
        
        if image_urls:
            urls_text = '\n'.join(image_urls)
            
            st.download_button(
                label="📥 Image URLs (TXT)",
                data=urls_text,
                file_name="image_urls.txt",
                mime="text/plain",
                use_container_width=True
            )


def render_results_display(
    pipeline_results: Optional[Dict], 
    building_data: Optional[Dict],
    on_new_analysis: callable = None
) -> None:
    """
    Display pipeline results with quality summary, images and analysis.
    
    Args:
        pipeline_results: Pipeline output dict
        building_data: Original GeoJSON Feature
        on_new_analysis: Callback for "New Analysis" button
    """
    if not pipeline_results:
        return
    
    # Header with New Analysis button
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("## Step 3: Analysis Results")
    
    with col2:
        if on_new_analysis:
            if st.button("🔄 New Analysis", use_container_width=True):
                on_new_analysis()
    
    # Status check
    status = pipeline_results.get('status')
    
    if status == 'error':
        st.error(f"❌ Pipeline Error: {pipeline_results.get('message', 'Unknown error')}")
        return
    
    if status == 'success':
        # Container for styled content
        with st.container():
            # Quality Summary Cards
            render_quality_summary(pipeline_results)
            
            st.markdown("---")
            
            # Image Gallery
            captures = pipeline_results.get('captures', [])
            if not captures:
                captures = pipeline_results.get('data', {}).get('captures', [])
            render_image_gallery(captures)
            
            st.markdown("---")
            
            # Building Analysis
            analysis = pipeline_results.get('building_analysis')
            if not analysis:
                analysis = pipeline_results.get('data', {}).get('analysis')
            render_analysis(analysis)
            
            st.markdown("---")
            
            # Export Controls
            render_export_controls(pipeline_results, building_data)
    
    else:
        # Handle other result structures (e.g., no_llm mode)
        st.markdown("### Pipeline Output")
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            exec_time = pipeline_results.get('execution_time_seconds', 0)
            st.metric("⏱️ Execution Time", f"{exec_time:.1f}s")
        
        with col2:
            viewpoint_count = pipeline_results.get('viewpoints_count', 0)
            st.metric("📍 Viewpoints", viewpoint_count)
        
        with col3:
            mode = pipeline_results.get('mode', 'standard')
            st.metric("🔧 Mode", mode)
        
        # Show viewpoints if available
        viewpoints = pipeline_results.get('viewpoints', [])
        if viewpoints:
            st.markdown("### 📍 Viewpoints")
            for i, vp in enumerate(viewpoints[:5]):  # Show max 5
                with st.expander(f"Viewpoint {i+1}"):
                    st.json(vp)
        
        # Full JSON
        with st.expander("📋 View Full Results"):
            st.json(pipeline_results)
