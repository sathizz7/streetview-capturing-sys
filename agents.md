# Building Detection V2 - Agents Documentation

This document describes the LLM-powered agents used in the Building Detection V2 pipeline.

## Overview

The V2 system uses three specialized LLM agents to handle intelligent processing tasks:

| Agent | Pipeline Step | Purpose |
|-------|---------------|---------|
| Face Screening Agent | Step 3 | Validate building front faces |
| Refinement Agent | Step 4 | Optimize camera parameters |
| Analysis Agent | Step 5 | Extract building information |

## Face Screening Agent

**Purpose**: Evaluate Street View images to identify valid front-facing building facades.

**Input**: Batch of candidate images with their viewpoint metadata

**Output**: For each image:
- `is_valid_front_face`: Whether it shows a street-facing facade
- `confidence`: 0-1 confidence score
- `clarity_assessment`: excellent/good/acceptable/poor
- `needs_refinement`: Whether parameters should be adjusted
- `group_id`: Groups similar views of the same facade
- `is_primary_in_group`: Whether this is the best view in the group

**Rejection Criteria**:
- Side/back walls
- Interior views (inside shops, lobbies)
- Heavily cropped or obscured views
- Wrong building in frame

## Refinement Agent

**Purpose**: Iteratively adjust camera parameters to achieve optimal building capture.

**Input**: Current viewpoint, image URL, history of previous attempts

**Output**: Parameter adjustments:
- `distance_change`: Move closer/farther (meters)
- `pitch_change`: Tilt camera up/down (degrees)
- `fov_change`: Zoom in/out (degrees)

**Parameter Bounds**:
- Distance: 8m - 65m
- Pitch: -15° to +55°
- FOV: 30° to 90°
- Max change per iteration: ±10m distance, ±15° pitch/fov

**Strategy**:
1. Prioritize vertical full view (roof to ground visible)
2. Prefer closer distances when full view is achieved
3. Use history to avoid oscillation
4. Early stop when quality ≥ 8 and full view achieved

## Analysis Agent

**Purpose**: Extract business intelligence from building facade images.

**Input**: Set of validated building face images

**Output**:
- `building_usage_summary`: One-sentence description of building purpose
- `visual_description`: Floors, style, colors
- `establishments`: List of businesses/shops detected via OCR
  - `name`: Business name from signboard
  - `type`: Inferred business type
  - `description`: Brief service description

**OCR Capabilities**:
- English and local scripts (Telugu, Hindi, etc.)
- Small text on windows, directories, pillars
- Logo recognition for known brands

## Configuration

All agents use `gemini/gemini-2.5-flash` by default. Configure in `backend/config/settings.py`:

```python
LLM_MODEL = "gemini/gemini-2.5-flash"
MAX_REFINEMENT_ITERATIONS = 3
```

## Model Selection Guidance

| Scenario | Recommended Model |
|----------|-------------------|
| Fast iteration, cost-sensitive | gemini-2.5-flash |
| Higher accuracy needed | gemini-2.5-pro |
| Complex OCR requirements | gemini-2.5-pro |
