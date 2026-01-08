# Building Detection V2 - Agent Architecture

## Overview

The Building Detection V2 pipeline is a multi-stage system that captures and analyzes building facades using only latitude/longitude coordinates. The system employs a modular architecture with specialized agents, each responsible for a specific aspect of the image capture and analysis workflow.

## Core Architecture

### Pipeline Flow

```
Input: (Latitude, Longitude)
    ↓
[Step 0] Geocoding Refinement → snap_to_home_center()
    ↓
[Step 1] Road Discovery → RoadFinder
    ↓
[Step 2] Viewpoint Generation → ViewpointGenerator
    ↓
[Step 3] Street View Validation → GoogleMapsService
    ↓
[Step 4] Face Screening → FaceScreeningAgent (LLM)
    ↓
[Step 5] Image Refinement → RefinementAgent (LLM)
    ↓
[Step 6] Building Analysis → AnalysisAgent (LLM)
    ↓
Output: {captures, building_analysis, metadata}
```

---

## Agent Ecosystem

### 1. **BaseAgent** (Abstract Base)

**Location**: `agents/base_agent.py`

**Purpose**: Provides common infrastructure for all LLM-based agents.

**Key Features**:
- LLM client initialization (via LiteLLM)
- Model configuration management
- Prompt token tracking
- Enable/disable toggling per agent

**Configuration**:
```python
settings:
  - face_screening_model: str
  - refinement_model: str
  - analysis_model: str
```

---

### 2. **FaceScreeningAgent**

**Location**: `agents/face_screening_agent.py`

**Purpose**: Initial quality gate that filters out unusable Street View captures.

**Pipeline Stage**: Step 4 (Post-Validation)

**Input**:
- Street View image URL
- Building centroid coordinates
- Viewpoint metadata

**Output**:
```python
{
  "is_valid": bool,
  "reason": str,
  "confidence": float
}
```

**Rejection Criteria**:
- No building visible
- Building heavily occluded
- Poor image quality (blur, darkness)
- Incorrect viewpoint direction
- Obstructions (trees, vehicles, scaffolding)

**Model**: `gemini-2.5-flash` (configurable)

---

### 3. **RefinementAgent**

**Location**: `agents/refinement_agent.py`

**Purpose**: Iteratively improves viewpoint selection to capture the best possible building facade.

**Pipeline Stage**: Step 5 (Post-Screening)

**Input**:
- Initial valid capture (from FaceScreeningAgent)
- Building location
- Capture history

**Refinement Strategy**:
1. **Analysis**: LLM evaluates current image quality
2. **Decision**: Determines if refinement is needed
3. **Adjustment**: Suggests new heading/pitch/distance
4. **Iteration**: Captures new image and repeats (max 3 iterations)

**Output**:
```python
{
  "final_capture": CaptureResult,
  "refinement_history": List[RefinementStep],
  "total_iterations": int
}
```

**LLM Capabilities**:
- Suggests optimal camera angles
- Identifies better vantage points
- Balances coverage vs. detail

**Model**: `gemini-2.5-flash` (configurable)

---

### 4. **AnalysisAgent**

**Location**: `agents/analysis_agent.py`

**Purpose**: Generates comprehensive building analysis from the final capture.

**Pipeline Stage**: Step 6 (Final Stage)

**Input**:
- Best refined image URL
- Building metadata

**Output**:
```python
{
  "building_type": str,
  "architectural_style": str,
  "floor_count": int,
  "condition": str,
  "materials": List[str],
  "notable_features": List[str],
  "description": str
}
```

**Analysis Dimensions**:
- Structural characteristics
- Architectural style
- Materials and finishes
- Condition assessment
- Notable features

**Model**: `gemini-2.5-flash` (configurable)

---

## Pipeline Components (Non-Agent)

### **RoadFinder**

**Location**: `pipeline/road_finder.py`

**Purpose**: Discovers nearby roads with Street View coverage.

**Algorithm**:
1. Sample 360° circle around building (typically 8-16 directions)
2. Use Google Roads API to snap points to nearest roads
3. De-duplicate road segments
4. Validate Street View metadata availability

**Output**: List of accessible road positions with Street View coverage.

---

### **ViewpointGenerator**

**Location**: `pipeline/viewpoint_generator.py`

**Purpose**: Converts road positions into camera viewpoints facing the building.

**Calculations**:
- Heading: Azimuth from road → building center
- Pitch: Elevation angle (default: 0°, adjustable)
- FOV: Field of view (default: 90°)

**Output**: `Viewpoint` objects ready for Street View API.

---

### **GoogleMapsService**

**Location**: `services/google_maps.py`

**Purpose**: Wrapper for Google Maps APIs.

**APIs Used**:
- **Street View Static API**: Image fetching
- **Street View Metadata API**: Coverage validation
- **Roads API**: Road snapping
- **Geocoding API**: Address lookup

---

## Data Flow

### Input Processing
1. User provides `(lat, lon)`
2. **Geocoding Refinement** (`snap_to_home_center`) ensures precise building center
3. Coordinates passed to `BuildingCapturePipeline.capture_building()`

### Discovery Phase
1. **RoadFinder** identifies nearby roads
2. **ViewpointGenerator** creates candidate viewpoints
3. **GoogleMapsService** validates Street View coverage

### Quality Processing (LLM-Driven)
1. **FaceScreeningAgent** filters initial captures
2. **RefinementAgent** iteratively improves selected capture
3. **AnalysisAgent** generates final building report

### Output Generation
```python
{
  "status": "success",
  "captures": [CaptureResult],
  "building_analysis": BuildingAnalysis,
  "execution_time": float,
  "metadata": {...}
}
```

---

## Configuration

All agents are configured via `config/settings.py`:

```python
class Settings:
    # API Keys
    GOOGLE_MAPS_API_KEY: str
    LITELLM_API_KEY: str
    
    # Agent Models
    FACE_SCREENING_MODEL: str = "gemini/gemini-2.5-flash"
    REFINEMENT_MODEL: str = "gemini/gemini-2.5-flash"
    ANALYSIS_MODEL: str = "gemini/gemini-2.5-flash"
    
    # Pipeline Parameters
    MAX_REFINEMENT_ITERATIONS: int = 3
    ROAD_SEARCH_RADIUS: int = 50
    STREET_VIEW_SIZE: str = "640x640"
```

---

## Error Handling

### Agent Failures
- **FaceScreeningAgent**: All captures rejected → Pipeline returns error
- **RefinementAgent**: Max iterations reached → Returns best available capture
- **AnalysisAgent**: LLM error → Returns empty analysis dict

### Pipeline Failures
- **No roads found**: Returns error with diagnostics
- **No Street View coverage**: Returns error with distance to nearest coverage
- **API rate limits**: Implements exponential backoff

---

## Performance Characteristics

| Stage | Latency | API Calls | LLM Tokens |
|-------|---------|-----------|------------|
| Step 0 | ~2s | 2 (Roads + Geocoding) | 0 |
| Step 1 | ~1-3s | 8-16 (Roads API) | 0 |
| Step 2 | <100ms | 0 | 0 |
| Step 3 | ~0.5s/viewpoint | N (Metadata checks) | 0 |
| Step 4 | ~1-2s/capture | 0 | ~500-1000 |
| Step 5 | ~3-6s | 1-3 (Street View) | ~1500-3000 |
| Step 6 | ~1-2s | 0 | ~500-1000 |

**Total**: ~10-20 seconds per building (depending on refinement iterations)

---

## Extension Points

### Adding New Agents
1. Inherit from `BaseAgent`
2. Implement agent-specific logic
3. Register in `agents/__init__.py`
4. Add to `BuildingCapturePipeline.__init__()`

### Custom Analysis
- Extend `AnalysisAgent` prompt for domain-specific detection
- Add custom fields to `BuildingAnalysis` model

### Alternative LLM Providers
- LiteLLM supports 100+ providers
- Update model strings in settings (e.g., `anthropic/claude-3-5-sonnet`)

---

## Key Design Decisions

1. **Agent Separation**: Each agent has a single, well-defined responsibility
2. **Async-First**: All I/O operations use `asyncio` for concurrency
3. **LLM Flexibility**: Agents can use different models based on task complexity
4. **Graceful Degradation**: Pipeline can operate in "no-LLM" mode for testing
5. **Stateless Agents**: Agents don't maintain state between calls (pipeline orchestrates)

---

## Future Enhancements

- **Batch Processing**: Parallel execution for multiple buildings
- **Caching**: Store Street View metadata to reduce API calls
- **Advanced Refinement**: Multi-view fusion for better coverage
- **Custom Agents**: Damage assessment, solar panel detection, etc.
