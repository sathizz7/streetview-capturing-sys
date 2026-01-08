"""3-Step Wizard UI Component using Streamlit native components."""

import streamlit as st
from typing import Literal

# Step definitions
STEPS = [
    {"id": 1, "name": "Selection", "icon": "🎯"},
    {"id": 2, "name": "Analysis", "icon": "⚙️"},
    {"id": 3, "name": "Results", "icon": "📊"},
]


def render_wizard_stepper(current_step: int = 1) -> None:
    """
    Render horizontal stepper showing progress through wizard using Streamlit columns.
    
    Args:
        current_step: Current step number (1, 2, or 3)
    """
    # Custom CSS for wizard styling
    st.markdown("""
    <style>
    .wizard-circle-completed {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, #28a745, #20c997);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 16px;
        margin: 0 auto;
        box-shadow: 0 4px 15px rgba(40, 167, 69, 0.4);
    }
    .wizard-circle-active {
        width: 45px;
        height: 45px;
        border-radius: 50%;
        background: linear-gradient(135deg, #9b59b6, #8e44ad);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 18px;
        margin: 0 auto;
        box-shadow: 0 4px 20px rgba(155, 89, 182, 0.5);
    }
    .wizard-circle-pending {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: #e9ecef;
        color: #6c757d;
        border: 2px solid #dee2e6;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        font-size: 16px;
        margin: 0 auto;
    }
    .wizard-label {
        text-align: center;
        margin-top: 8px;
        font-size: 14px;
        font-weight: 500;
        color: #495057;
    }
    .wizard-label-active {
        text-align: center;
        margin-top: 8px;
        font-size: 14px;
        font-weight: 600;
        color: #8e44ad;
    }
    .wizard-connector {
        height: 3px;
        background: #dee2e6;
        margin-top: 20px;
    }
    .wizard-connector-completed {
        height: 3px;
        background: linear-gradient(90deg, #28a745, #20c997);
        margin-top: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create columns for wizard steps with connectors
    cols = st.columns([1, 0.5, 1, 0.5, 1])
    
    for i, step in enumerate(STEPS):
        step_id = step["id"]
        col_idx = i * 2  # 0, 2, 4
        
        # Determine step state
        if step_id < current_step:
            state = "completed"
            circle_content = "✓"
            circle_class = "wizard-circle-completed"
            label_class = "wizard-label"
        elif step_id == current_step:
            state = "active"
            circle_content = str(step_id)
            circle_class = "wizard-circle-active"
            label_class = "wizard-label-active"
        else:
            state = "pending"
            circle_content = str(step_id)
            circle_class = "wizard-circle-pending"
            label_class = "wizard-label"
        
        with cols[col_idx]:
            st.markdown(f'<div class="{circle_class}">{circle_content}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="{label_class}">{step["name"]}</div>', unsafe_allow_html=True)
        
        # Add connector between steps (not after last)
        if i < len(STEPS) - 1:
            connector_col_idx = col_idx + 1
            connector_class = "wizard-connector-completed" if step_id < current_step else "wizard-connector"
            with cols[connector_col_idx]:
                st.markdown(f'<div class="{connector_class}"></div>', unsafe_allow_html=True)


def render_step_content_header(
    step: int,
    title: str,
    description: str = "",
    show_new_analysis: bool = False,
    on_new_analysis: callable = None
) -> None:
    """
    Render step content header with title and optional action button.
    
    Args:
        step: Current step number
        title: Step title
        description: Optional description
        show_new_analysis: Whether to show "New Analysis" button
        on_new_analysis: Callback for new analysis button
    """
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"### Step {step}: {title}")
        if description:
            st.caption(description)
    
    with col2:
        if show_new_analysis:
            if st.button("🔄 New Analysis", key="new_analysis_btn", use_container_width=True):
                if on_new_analysis:
                    on_new_analysis()
