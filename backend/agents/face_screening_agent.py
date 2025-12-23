"""
Face Screening Agent - Pipeline Step 3

LLM-powered agent to validate building front faces from Street View images.
"""

import logging
from typing import List, Dict, Optional

from .base_agent import BaseAgent
from models import FaceScreeningResult
from prompts import FACE_SCREENING_PROMPT

logger = logging.getLogger(__name__)


class FaceScreeningAgent(BaseAgent):
    """
    Agent to screen building face images for validity.
    
    Evaluates candidate Street View images to identify valid
    front-facing building facades.
    """
    
    async def screen_faces(
        self, 
        candidates: List[Dict[str, str]]
    ) -> Dict[int, Optional[FaceScreeningResult]]:
        """
        Batch-screen multiple candidate images in a single LLM call.
        
        Args:
            candidates: List of dicts with keys:
                - candidate_index: int
                - image_url: str
                
        Returns:
            Dict mapping candidate_index to FaceScreeningResult (or None if failed)
        """
        if not self.enabled or not candidates:
            return {}
        
        logger.info(f"Screening {len(candidates)} face candidates...")
        
        # Build content with images
        content_parts = [
            {
                "type": "text", 
                "text": "Analyze the following building images to identify valid front facades."
            }
        ]
        
        for candidate in candidates:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": candidate["image_url"]}
            })
        
        # Call LLM
        data = await self._call_llm(FACE_SCREENING_PROMPT, content_parts)
        
        if not data:
            logger.error("Face screening LLM call failed")
            return {}
        
        # Parse results
        results: Dict[int, Optional[FaceScreeningResult]] = {}
        faces_list = data.get("faces", [])
        
        # Handle single-face response format
        if not faces_list and "face_screening" in data and len(candidates) == 1:
            fs = data["face_screening"]
            faces_list = [{
                "candidate_index": candidates[0]["candidate_index"],
                **fs
            }]
        
        for item in faces_list:
            try:
                idx = int(item.get("candidate_index", -1))
                fs_data = item.get("face_screening", item)
                
                results[idx] = FaceScreeningResult(
                    is_valid_front_face=bool(fs_data.get("is_valid_front_face", False)),
                    has_visible_billboards=bool(fs_data.get("has_visible_billboards", False)),
                    confidence=float(fs_data.get("confidence", 0.0) or 0.0),
                    clarity_assessment=str(fs_data.get("clarity_assessment", "poor")).lower(),
                    needs_refinement=bool(fs_data.get("needs_refinement", False)),
                    suggestions=str(fs_data.get("suggestions", "")),
                    group_id=fs_data.get("group_id"),
                    is_primary_in_group=fs_data.get("is_primary_in_group"),
                    candidate_index=idx,
                    # New intelligent selection fields
                    building_coverage_pct=float(fs_data.get("building_coverage_pct", 0) or 0),
                    is_target_building_primary=bool(fs_data.get("is_target_building_primary", True)),
                    is_road_dominated=bool(fs_data.get("is_road_dominated", False)),
                )
                
            except (TypeError, ValueError, KeyError) as e:
                logger.error(f"Parse error for candidate {item.get('candidate_index')}: {e}")
                continue
        
        # Log results
        valid_count = sum(1 for r in results.values() if r and r.is_valid_front_face)
        logger.info(f"Screening complete: {valid_count}/{len(candidates)} valid front faces")
        
        return results
