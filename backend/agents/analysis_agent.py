"""
Analysis Agent - Pipeline Step 5

LLM-powered agent to analyze building images and extract business intelligence.
"""

import logging
from typing import List, Optional

from .base_agent import BaseAgent
from models import BuildingAnalysis, Establishment
from prompts import ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    Agent to analyze building images and identify establishments.
    
    Uses OCR and visual analysis to extract business names,
    building descriptions, and establishment information.
    """
    
    async def analyze_building(
        self, 
        image_urls: List[str],
        address: Optional[str] = None
    ) -> Optional[BuildingAnalysis]:
        """
        Analyze building images to create a consolidated report.
        
        Args:
            image_urls: List of Street View image URLs showing valid building faces
            address: Optional address string from geocoding
            
        Returns:
            BuildingAnalysis with usage summary, description, and establishments
        """
        if not self.enabled or not image_urls:
            return None
        
        logger.info(f"Analyzing {len(image_urls)} building images...")
        
        # Build content with images
        content_parts = [
            {
                "type": "text",
                "text": "Analyze the following building images together to provide a consolidated report."
            }
        ]
        
        for url in image_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": url}
            })
        
        # Call LLM
        data = await self._call_llm(ANALYSIS_PROMPT, content_parts)
        
        if not data:
            logger.error("Building analysis LLM call failed")
            return None
        
        # Parse establishments
        establishments = []
        for est_data in data.get("establishments", []):
            try:
                establishments.append(Establishment(
                    name=est_data.get("name", "Unknown"),
                    type=est_data.get("type", "Unknown"),
                    description=est_data.get("description", "")
                ))
            except Exception as e:
                logger.warning(f"Failed to parse establishment: {e}")
                continue
        
        result = BuildingAnalysis(
            building_usage_summary=data.get("building_usage_summary", "Unable to determine building usage."),
            visual_description=data.get("visual_description", {}),
            establishments=establishments,
            address=address
        )
        
        logger.info(f"Analysis complete: {len(establishments)} establishments found")
        return result
