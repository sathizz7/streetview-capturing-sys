"""
Refinement Agent - Pipeline Step 4

LLM-powered agent to iteratively refine camera parameters for optimal capture.
"""

import logging
from typing import Dict, Optional, List, Any

from .base_agent import BaseAgent
from models import Viewpoint, RefinementStep
from services import GoogleMapsService
from prompts import REFINEMENT_PROMPT
from config import get_settings

logger = logging.getLogger(__name__)


class RefinementAgent(BaseAgent):
    """
    Agent to refine building capture parameters using LLM feedback.
    
    Iteratively adjusts distance, pitch, and FOV to achieve optimal 
    building capture with full vertical view.
    """
    
    def __init__(self, maps_service: GoogleMapsService, **kwargs):
        super().__init__(**kwargs)
        self.maps_service = maps_service
        self.settings = get_settings()
    
    async def refine_capture(
        self, 
        viewpoint: Viewpoint,
        building_lat: float,
        building_lon: float
    ) -> Dict[str, Any]:
        """
        Iteratively refine camera parameters for a viewpoint.
        
        Args:
            viewpoint: Initial viewpoint to refine
            building_lat, building_lon: Building coordinates
            
        Returns:
            Dict with final_image_url, final_viewpoint, refinement_history, is_refined
        """
        if not self.enabled:
            return self._fallback_result(viewpoint)
        
        logger.info(f"Starting refinement for viewpoint at ({viewpoint.lat}, {viewpoint.lon})")
        
        history: List[RefinementStep] = []
        best_result: Optional[Dict] = None
        best_score = -1
        
        current_params = {
            "lat": viewpoint.lat,
            "lon": viewpoint.lon,
            "heading": viewpoint.heading,
            "pitch": viewpoint.pitch,
            "fov": viewpoint.fov,
            "distance": viewpoint.distance_to_building,
        }
        
        max_iterations = self.settings.max_refinement_iterations
        
        for iteration in range(max_iterations):
            logger.info(f"Refinement iteration {iteration + 1}/{max_iterations}")
            
            # Generate image URL with current params
            temp_viewpoint = self._create_temp_viewpoint(current_params, viewpoint)
            image_url = self.maps_service.generate_streetview_url(temp_viewpoint)
            
            # Build history text for context
            history_text = self._format_history(history)
            
            # Analyze image with LLM
            analysis = await self._analyze_image(image_url, current_params, history_text)
            
            if analysis is None:
                logger.error("LLM analysis failed, stopping refinement")
                break
            
            # Extract results
            view_assessment = analysis.get("view_assessment", {})
            adjustments = analysis.get("parameter_adjustments", {})
            
            is_full_view = bool(view_assessment.get("is_full_view", False))
            confidence = float(view_assessment.get("view_confidence", 0))
            quality = int(view_assessment.get("overall_quality", 5))
            
            # Record step
            step = RefinementStep(
                iteration=iteration + 1,
                image_url=image_url,
                params=current_params.copy(),
                confidence_score=confidence,
                is_full_view=is_full_view,
                overall_quality=quality,
                changes={
                    "distance_change": float(adjustments.get("distance_change", 0) or 0),
                    "pitch_change": float(adjustments.get("pitch_change", 0) or 0),
                    "fov_change": float(adjustments.get("fov_change", 0) or 0),
                }
            )
            history.append(step)
            
            # Track best result (prioritize: full_view, quality, closer distance)
            score = (1 if is_full_view else 0) * 1000 + quality * 10 - current_params["distance"]
            if score > best_score:
                best_score = score
                best_result = {
                    "image_url": image_url,
                    "params": current_params.copy(),
                    "quality": quality,
                    "confidence": confidence,
                }
            
            # Early stopping if target met
            if is_full_view and quality >= 8:
                logger.info("Target quality achieved, stopping early")
                break
            
            # Check if refinement converged
            if self._should_stop(adjustments, iteration, max_iterations):
                break
            
            # Apply adjustments for next iteration
            current_params = self._apply_adjustments(
                current_params, adjustments, 
                building_lat, building_lon
            )
        
        # Return best result
        if best_result:
            final_viewpoint = self._create_temp_viewpoint(best_result["params"], viewpoint)
            return {
                "image_url": best_result["image_url"],
                "viewpoint": final_viewpoint,
                "refinement_history": history,
                "is_refined": True,
                "final_quality": best_result["quality"],
            }
        
        return self._fallback_result(viewpoint, history)
    
    async def _analyze_image(
        self, 
        image_url: str, 
        params: Dict, 
        history_text: str
    ) -> Optional[Dict]:
        """Analyze an image with LLM and get parameter adjustments."""
        prompt_text = f"""image_url: {image_url}
lat: {params['lat']}
lon: {params['lon']}
heading: {params['heading']:.1f}
pitch: {params['pitch']:.1f}
fov: {params['fov']:.1f}
distance: {params['distance']:.1f}

{history_text}"""
        
        content = [
            {"type": "text", "text": prompt_text},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
        
        return await self._call_llm(REFINEMENT_PROMPT, content)
    
    def _create_temp_viewpoint(self, params: Dict, original: Viewpoint) -> Viewpoint:
        """Create a temporary viewpoint from params."""
        return Viewpoint(
            lat=params["lat"],
            lon=params["lon"],
            heading=params["heading"],
            pitch=params["pitch"],
            fov=params["fov"],
            distance_to_building=params["distance"],
            pano_id=original.pano_id,
            road_type=original.road_type,
        )
    
    def _format_history(self, history: List[RefinementStep]) -> str:
        """Format history for LLM context."""
        if not history:
            return "HISTORY: No previous attempts."
        
        lines = ["HISTORY OF PREVIOUS ATTEMPTS:"]
        for step in history:
            result = "Invalid" if step.confidence_score < 0.5 else f"Quality={step.overall_quality}"
            line = (
                f"- Iteration {step.iteration}: "
                f"Dist={step.params['distance']:.1f}m, "
                f"Pitch={step.params['pitch']:.1f}°, "
                f"FOV={step.params['fov']:.1f}° "
                f"-> {result}"
            )
            lines.append(line)
        
        return "\n".join(lines)
    
    def _should_stop(self, adjustments: Dict, iteration: int, max_iter: int) -> bool:
        """Check if refinement should stop."""
        if iteration >= max_iter - 1:
            logger.info("Max iterations reached")
            return True
        
        # Check for minimal changes
        dist_change = abs(float(adjustments.get("distance_change", 0) or 0))
        pitch_change = abs(float(adjustments.get("pitch_change", 0) or 0))
        fov_change = abs(float(adjustments.get("fov_change", 0) or 0))
        
        if dist_change < 0.1 and pitch_change < 0.1 and fov_change < 0.1:
            logger.info("LLM indicates framing is acceptable")
            return True
        
        return False
    
    def _apply_adjustments(
        self, 
        params: Dict, 
        adjustments: Dict,
        building_lat: float,
        building_lon: float
    ) -> Dict:
        """Apply adjustments and constrain to bounds."""
        from utils import calculate_position_offset, calculate_bearing
        
        new_params = params.copy()
        
        # Apply changes
        new_params["distance"] += float(adjustments.get("distance_change", 0) or 0)
        new_params["pitch"] += float(adjustments.get("pitch_change", 0) or 0)
        new_params["fov"] += float(adjustments.get("fov_change", 0) or 0)
        
        # Constrain to bounds
        new_params["distance"] = max(
            self.settings.min_distance,
            min(new_params["distance"], self.settings.max_distance)
        )
        new_params["pitch"] = max(
            self.settings.min_pitch,
            min(new_params["pitch"], self.settings.max_pitch)
        )
        new_params["fov"] = max(
            self.settings.min_fov,
            min(new_params["fov"], self.settings.max_fov)
        )
        
        # Recalculate position if distance changed
        if new_params["distance"] != params["distance"]:
            # Calculate bearing from building to camera (opposite of heading)
            reverse_bearing = (new_params["heading"] + 180) % 360
            new_lat, new_lon = calculate_position_offset(
                building_lat, building_lon,
                new_params["distance"],
                reverse_bearing
            )
            new_params["lat"] = new_lat
            new_params["lon"] = new_lon
        
        return new_params
    
    def _fallback_result(
        self, 
        viewpoint: Viewpoint, 
        history: List[RefinementStep] = None
    ) -> Dict[str, Any]:
        """Return fallback result without refinement."""
        return {
            "image_url": self.maps_service.generate_streetview_url(viewpoint),
            "viewpoint": viewpoint,
            "refinement_history": history or [],
            "is_refined": False,
        }
