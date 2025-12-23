"""
Data classes for Building Detection V2 pipeline.

These dataclasses represent the core data structures passed between pipeline stages.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class RoadPoint:
    """A point on a road near the target building."""
    lat: float
    lon: float
    road_type: str  # 'road', 'streetview', 'synthetic'
    distance_to_building: float = 0.0
    road_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Viewpoint:
    """
    A camera viewpoint for Street View capture.
    
    This represents a position and orientation for capturing a building image.
    The heading is calculated to face the building from the road point.
    """
    lat: float
    lon: float
    heading: float  # degrees, direction camera faces (toward building)
    pitch: float  # degrees, vertical tilt
    fov: float  # degrees, field of view
    distance_to_building: float  # meters
    
    # Quality metrics
    quality_score: float = 0.0
    
    # Street View metadata (populated after validation)
    pano_id: Optional[str] = None
    capture_date: Optional[str] = None
    
    # Source tracking
    road_type: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FaceScreeningResult:
    """Result of LLM face screening for a single candidate image."""
    is_valid_front_face: bool
    confidence: float  # 0-1 scale
    clarity_assessment: str  # "excellent", "good", "acceptable", "poor"
    needs_refinement: bool
    suggestions: str
    
    # Grouping metadata (for identifying same facade from different angles)
    group_id: Optional[str] = None
    is_primary_in_group: Optional[bool] = None
    candidate_index: Optional[int] = None
    has_visible_billboards: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RefinementStep:
    """A single step in the refinement history."""
    iteration: int
    image_url: str
    params: Dict[str, float]  # lat, lon, heading, pitch, fov, distance
    confidence_score: float
    is_full_view: bool
    overall_quality: int
    changes: Dict[str, float]  # distance_change, pitch_change, fov_change
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CaptureResult:
    """Final capture result for a building view."""
    image_url: str
    viewpoint: Viewpoint
    screening_result: Optional[FaceScreeningResult] = None
    refinement_history: List[RefinementStep] = field(default_factory=list)
    
    # Final metrics
    is_refined: bool = False
    final_quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "image_url": self.image_url,
            "viewpoint": self.viewpoint.to_dict(),
            "is_refined": self.is_refined,
            "final_quality_score": self.final_quality_score,
        }
        if self.screening_result:
            result["screening_result"] = self.screening_result.to_dict()
        if self.refinement_history:
            result["refinement_history"] = [step.to_dict() for step in self.refinement_history]
        return result


@dataclass
class Establishment:
    """A business or establishment identified in the building."""
    name: str
    type: str  # e.g., "Restaurant", "Pharmacy", "IT Services"
    description: str


@dataclass
class BuildingAnalysis:
    """Final analysis result for a building."""
    building_usage_summary: str
    visual_description: Dict[str, str]  # floors, style, color
    establishments: List[Establishment] = field(default_factory=list)
    address: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "building_usage_summary": self.building_usage_summary,
            "visual_description": self.visual_description,
            "establishments": [
                {"name": e.name, "type": e.type, "description": e.description}
                for e in self.establishments
            ],
            "address": self.address,
        }
