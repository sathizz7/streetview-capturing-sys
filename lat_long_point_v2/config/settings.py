"""
Configuration settings for Building Detection V2.

Loads environment variables and provides configurable thresholds.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Settings:
    """Application settings with defaults."""
    
    # API Keys
    google_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_API_KEY", ""))
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    
    # Road Discovery Settings
    road_search_radius: float = 50.0  # meters - radius to search for roads around building
    road_sample_distances: tuple = (15.0, 25.0, 35.0, 50.0)  # meters - distances to sample
    road_sample_directions: int = 8  # number of directions to sample (360° / 8 = every 45°)
    
    # Street View Settings
    streetview_metadata_radius: int = 50  # meters - radius for Street View availability check
    streetview_image_size: str = "640x640"  # image resolution
    min_distance: float = 8.0  # meters - minimum camera distance from building
    max_distance: float = 65.0  # meters - maximum camera distance from building
    
    # Camera Parameter Bounds
    min_pitch: float = -15.0  # degrees
    max_pitch: float = 55.0  # degrees
    min_fov: float = 30.0  # degrees
    max_fov: float = 90.0  # degrees
    
    # LLM Agent Settings
    llm_model: str = "gemini/gemini-2.5-flash"
    max_refinement_iterations: int = 3
    llm_temperature: float = 0.1
    llm_num_retries: int = 3
    
    # Quality Thresholds
    min_perpendicularity: float = 85.0  # minimum score to consider a viewpoint
    excellent_threshold: float = 90.0
    good_threshold: float = 80.0
    acceptable_threshold: float = 75.0
    
    # API Budget
    max_api_calls: int = 40
    max_candidates_per_building: int = 10
    
    def __post_init__(self):
        """Validate settings after initialization."""
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Set Gemini API key for LiteLLM
        os.environ["GEMINI_API_KEY"] = self.gemini_api_key


# Singleton instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
