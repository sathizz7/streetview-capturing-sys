"""
Building Detection V2 - Main Pipeline Orchestrator

This module provides the main entry point for the building capture pipeline.
It orchestrates all pipeline stages from road discovery to final analysis.

Usage:
    python main.py --lat 17.408 --lon 78.450
"""

import asyncio
import argparse
import json
import logging
import time
from typing import Dict, List, Optional, Any

from config import get_settings
from models import Viewpoint, CaptureResult, BuildingAnalysis
from services import GoogleMapsService, reverse_geocode
from pipeline import RoadFinder, ViewpointGenerator
from agents import FaceScreeningAgent, RefinementAgent, AnalysisAgent
from utils import calculate_distance
from utils.geocoding import snap_to_home_center

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BuildingCapturePipeline:
    """
    V2 Pipeline - Lat/Long Only Input
    
    Captures building images using only latitude/longitude coordinates.
    Does not require polygon/face data.
    
    Pipeline Steps:
    1. Find nearby roads (360° sampling)
    2. Generate viewpoints facing the building
    3. Validate Street View availability
    4. Screen faces with LLM
    5. Refine captures with LLM
    6. Analyze building with LLM
    """
    
    def __init__(self):
        """Initialize pipeline components."""
        self.settings = get_settings()
        
        # Initialize services
        self.maps_service = GoogleMapsService()
        
        # Initialize pipeline stages
        self.road_finder = RoadFinder(self.maps_service)
        self.viewpoint_generator = ViewpointGenerator()
        
        # Initialize agents
        self.face_screening_agent = FaceScreeningAgent()
        self.refinement_agent = RefinementAgent(self.maps_service)
        self.analysis_agent = AnalysisAgent()
        
        logger.info("Building Capture Pipeline V2 initialized")
    
    async def capture_building(
        self, 
        lat: float, 
        lon: float, 
        skip_llm: bool = False,
        polygon: Optional[List[List[float]]] = None
        ) -> Dict[str, Any]:
        """
        Main entry point: Capture a building using only lat/long.
        
        Args:
            lat: Building latitude
            lon: Building longitude
            skip_llm: If True, stops after Step 3 (Validation) and returns viewpoints.
            polygon: Optional list of [lat, lon] points defining building footprint.
            
        Returns:
            Dict with captures, analysis, and metadata
        """
        logger.info("=" * 70)
        logger.info(" BUILDING DETECTION V2 - LAT/LONG ONLY PIPELINE")
        logger.info("=" * 70)
        logger.info(f"Target: ({lat}, {lon})")
        if skip_llm:
            logger.info("Mode: NO-LLM (Geometry Validation Only)")
        if polygon:
            logger.info("Mode: POLYGON-ASSISTED (Strict Frontage Logic)")
        
        start_time = time.time()
        
        try:


            
            # Step 0: Refine coordinates
            logger.info("Step 0: Refining coordinates...")
            refined_location = snap_to_home_center(lat, lon)
            
            if refined_location and "lat" in refined_location and "lng" in refined_location:
                 old_lat, old_lon = lat, lon
                 lat = refined_location["lat"]
                 lon = refined_location["lng"]
                 dist_moved = calculate_distance(old_lat, old_lon, lat, lon)
                 
                 refinement_type = refined_location.get("type", "Unknown")
                 address = refined_location.get("address", "N/A")
                 
                 logger.info(f"Refined location ({refinement_type}): Moved {dist_moved:.1f}m")
                 logger.info(f"New Target: ({lat}, {lon}) - {address}")
                 
                 # Store metadata about refinement if useful for results
                 self.refinement_metadata = {
                     "original_lat": old_lat,
                     "original_lon": old_lon,
                     "distance_moved": dist_moved,
                     "refinement_type": refinement_type,
                     "address": address
                 }
            elif refined_location and "error" in refined_location:
                 logger.warning(f"Coordinate refinement warning: {refined_location['error']}")
            
            # Step 1: Find nearby roads
            logger.info("Step 1: Finding nearby roads...")
            road_points = await self.road_finder.find_candidate_roads(lat, lon)
            
            if not road_points:
                return self._error_result("No roads found near building")
            
            logger.info(f"Found {len(road_points)} road points")
            
            # Step 2: Generate viewpoints
            logger.info("Step 2: Generating viewpoints...")
            viewpoints = self.viewpoint_generator.generate_viewpoints(
                lat, lon, road_points, polygon
            )
            logger.info(f"Generated {len(viewpoints)} viewpoints")
            
            # Step 3: Validate Street View availability
            logger.info("Step 3: Validating Street View availability...")
            validated_viewpoints = await self._validate_streetview(
                viewpoints, lat, lon
            )
            
            if not validated_viewpoints:
                return self._error_result("No Street View coverage within 35m range")
            
            logger.info(f"Validated {len(validated_viewpoints)} viewpoints")
            
            # --- FAST EXIT IF NO LLM ---
            if skip_llm:
                elapsed = time.time() - start_time
                logger.info(f"Pipeline complete (NO-LLM) in {elapsed:.2f}s")
                return {
                    "status": "success",
                    "mode": "no_llm",
                    "building_location": {"lat": lat, "lon": lon},
                    "viewpoints_count": len(validated_viewpoints),
                    "viewpoints": [vp.to_dict() for vp in validated_viewpoints],
                    "execution_time_seconds": round(elapsed, 2)
                }
            
            # Step 4: Screen faces with LLM
            logger.info("Step 4: Screening faces...")
            screened_viewpoints = await self._screen_faces(validated_viewpoints)
            
            valid_faces = [v for v, s in screened_viewpoints if s and s.is_valid_front_face]
            logger.info(f"Valid front faces: {len(valid_faces)}/{len(screened_viewpoints)}")
            
            # Step 4.5: Select best 1- 5 images
            logger.info("Step 4.5: Selecting best images...")
            best_viewpoints = self._select_best_images(screened_viewpoints, max_images=5)
            logger.info(f"Selected {len(best_viewpoints)} best images")
            
            # Step 5: Refine captures (only for selected best)
            logger.info("Step 5: Refining captures...")
            capture_results = await self._refine_captures(
                best_viewpoints, lat, lon
            )
            logger.info(f"Refined {len(capture_results)} captures")
            
            # Step 6: Analyze building
            logger.info("Step 6: Analyzing building...")
            
            # Get address
            address = reverse_geocode(lat, lon)
            
            # Get best images for analysis
            analysis_urls = self._get_analysis_images(capture_results)
            analysis = await self.analysis_agent.analyze_building(
                analysis_urls, address
            )
            
            elapsed = time.time() - start_time
            logger.info(f"Pipeline complete in {elapsed:.2f}s")
            
            return self._format_results(capture_results, analysis, lat, lon, elapsed)
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            return self._error_result(str(e))
    
    async def _validate_streetview(
        self, 
        viewpoints: List[Viewpoint],
        building_lat: float,
        building_lon: float
    ) -> List[Viewpoint]:
        """
        Validate Street View availability and filter by distance.
        
        Args:
            viewpoints: List of candidates
            building_lat, building_lon: Target building coordinates
            
        Returns:
            List of valid viewpoints within 35m range
        """
        validated = []
        
        for viewpoint in viewpoints:
            metadata = await self.maps_service.get_streetview_metadata(
                viewpoint.lat, viewpoint.lon,
                radius=self.settings.streetview_metadata_radius
            )
            
            if metadata and metadata.get("status") == "OK":
                # Update with actual location from metadata
                actual_loc = metadata["location"]
                viewpoint.lat = actual_loc["lat"]
                viewpoint.lon = actual_loc["lng"]
                viewpoint.pano_id = metadata.get("pano_id")
                viewpoint.capture_date = metadata.get("date")
                
                # RECALCULATE DISTANCE after snapping to actual pano location
                new_distance = calculate_distance(
                    viewpoint.lat, viewpoint.lon,
                    building_lat, building_lon
                )
                viewpoint.distance_to_building = new_distance
                
                # FILTER: Reject if > 35 meters
                if new_distance > 35.0:
                    logger.info(f"Rejected viewpoint: Distance {new_distance:.1f}m > 35m constraint")
                    continue

                validated.append(viewpoint)
        
        return validated
    
    async def _screen_faces(
        self, 
        viewpoints: List[Viewpoint]     
    ) -> List[tuple]:
        """Screen viewpoints with face screening agent."""
        # Generate image URLs
        candidates = []
        for i, vp in enumerate(viewpoints):
            url = self.maps_service.generate_streetview_url(vp)
            candidates.append({
                "candidate_index": i,
                "image_url": url,
            })
        
        # Screen with LLM
        screening_results = await self.face_screening_agent.screen_faces(candidates)
        
        # Pair viewpoints with screening results
        return [
            (viewpoints[i], screening_results.get(i))
            for i in range(len(viewpoints))
        ]
    
    def _select_best_images(
        self, 
        screened: List[tuple],
        max_images: int = 3
    ) -> List[tuple]:
        """
        Select top 1-3 best images based on intelligent criteria.
        
        Selection priority:
        1. is_target_building_primary = True
        2. is_road_dominated = False
        3. building_coverage_pct >= 50
        4. clarity_assessment in ["excellent", "good"]
        5. is_valid_front_face = True
        
        Diversity: max 1-2 images per group_id
        """
        # Filter to valid candidates
        valid_candidates = []
        for vp, screening in screened:
            if not screening:
                continue
            if not screening.is_valid_front_face:
                continue
            if not screening.is_target_building_primary:
                logger.info(f"Rejected: target building not primary (idx={screening.candidate_index})")
                continue
            if screening.is_road_dominated:
                logger.info(f"Rejected: road dominated (idx={screening.candidate_index})")
                continue
            valid_candidates.append((vp, screening))
        
        if not valid_candidates:
            logger.warning("No valid candidates after filtering, using all screened images")
            valid_candidates = [(vp, sc) for vp, sc in screened if sc and sc.is_valid_front_face]
        
        # Score each candidate
        def score_candidate(item):
            vp, screening = item
            score = 0
            
            # Building coverage (0-100 points)
            score += screening.building_coverage_pct
            
            # Clarity bonus
            clarity_scores = {"excellent": 30, "good": 20, "acceptable": 10, "poor": 0}
            score += clarity_scores.get(screening.clarity_assessment, 0)
            
            # Primary in group bonus
            if screening.is_primary_in_group:
                score += 15
            
            # No refinement needed bonus
            if not screening.needs_refinement:
                score += 10
            
            return score
        
        # Sort by score
        scored = sorted(valid_candidates, key=score_candidate, reverse=True)
        
        # Select diverse images (max 2 per group)
        selected = []
        group_counts = {}
        
        for vp, screening in scored:
            group_id = screening.group_id or "default"
            current_count = group_counts.get(group_id, 0)
            
            if current_count < 2:  # Max 2 per group
                selected.append((vp, screening))
                group_counts[group_id] = current_count + 1
                
                if len(selected) >= max_images:
                    break
        
        logger.info(f"Selected {len(selected)} best images from {len(valid_candidates)} valid candidates")
        return selected
    
    async def _refine_captures(
        self, 
        screened: List[tuple],
        building_lat: float,
        building_lon: float
    ) -> List[CaptureResult]:
        """Refine valid captures using refinement agent (parallel execution)."""
        
        async def refine_single(viewpoint: Viewpoint, screening) -> Optional[CaptureResult]:
            """Process a single viewpoint asynchronously."""
            # Skip invalid faces
            if not screening or not screening.is_valid_front_face:
                return None
            
            # Refine if needed
            if screening.needs_refinement:
                refined = await self.refinement_agent.refine_capture(
                    viewpoint, building_lat, building_lon
                )
                
                return CaptureResult(
                    image_url=refined["image_url"],
                    viewpoint=refined.get("viewpoint", viewpoint),
                    screening_result=screening,
                    refinement_history=refined.get("refinement_history", []),
                    is_refined=refined.get("is_refined", False),
                    final_quality_score=refined.get("final_quality", 0),
                )
            else:
                return CaptureResult(
                    image_url=self.maps_service.generate_streetview_url(viewpoint),
                    viewpoint=viewpoint,
                    screening_result=screening,
                    is_refined=False,
                )
        
        # Run all refinements in parallel
        tasks = [refine_single(vp, sc) for vp, sc in screened]
        results = await asyncio.gather(*tasks)
        
        # Filter out None results and assign image_id
        final_results = []
        image_id = 1
        for r in results:
            if r is not None:
                r.image_id = image_id
                final_results.append(r)
                image_id += 1
        
        return final_results
    
    def _get_analysis_images(self, captures: List[CaptureResult]) -> List[str]:
        """Get best image URLs for building analysis."""
        # Sort by quality and return URLs
        sorted_captures = sorted(
            captures,
            key=lambda c: c.final_quality_score,
            reverse=True
        )
        return [c.image_url for c in sorted_captures[:5]]  # Top 5 images
    
    def _format_results(
        self,
        captures: List[CaptureResult],
        analysis: Optional[BuildingAnalysis],
        lat: float,
        lon: float,
        elapsed: float
    ) -> Dict[str, Any]:
        """Format final results."""
        return {
            "status": "success",
            "building_location": {"lat": lat, "lon": lon},
            "pipeline_version": "2.0",
            "execution_time_seconds": round(elapsed, 2),
            "captures_count": len(captures),
            "captures": [c.to_dict() for c in captures],
            "building_analysis": analysis.to_dict() if analysis else None,
        }
    
    def _error_result(self, message: str) -> Dict[str, Any]:
        """Format error result."""
        return {
            "status": "error",
            "message": message,
            "pipeline_version": "2.0",
        }



# ==========================================
# MANUAL CONFIGURATION (Ignored if CLI args provided)
# ==========================================
# Example: 17.408
MANUAL_LAT = None
# Example: 78.450
MANUAL_LON = None
# Format: List of [lat, lon] points. Example: [[17.408, 78.450], [17.4081, 78.4501], ...]
MANUAL_POLYGON = None
# ==========================================


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Building Detection V2 - Capture building using lat/long"
    )
    # Make arguments optional to allow manual config fallback
    parser.add_argument("--lat", type=float, required=False, help="Building latitude")
    parser.add_argument("--lon", "--long", dest="lon", type=float, required=False, help="Building longitude")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    
    args = parser.parse_args()
    
    # Determine inputs (CLI takes precedence > Manual Config)
    lat = args.lat if args.lat is not None else MANUAL_LAT
    lon = args.lon if args.lon is not None else MANUAL_LON
    polygon = MANUAL_POLYGON
    
    if lat is None or lon is None:
        logger.error("❌ No coordinates provided!")
        logger.error("Please provide --lat/--lon CLI arguments OR set MANUAL_LAT/MANUAL_LON in main.py")
        return

    # Check for simple polygon validity if provided
    if polygon and not isinstance(polygon, list):
         logger.warning("⚠️ Invalid polygon format in MANUAL_POLYGON. Expected list of lists. Ignoring polygon.")
         polygon = None

    pipeline = BuildingCapturePipeline()
    result = await pipeline.capture_building(
        lat=lat, 
        lon=lon,
        polygon=polygon
    )
    
    # Output
    output_json = json.dumps(result, indent=2)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        logger.info(f"Results written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    asyncio.run(main())
