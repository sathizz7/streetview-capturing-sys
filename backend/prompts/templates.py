"""
LLM Prompt Templates for Building Detection V2.

These prompts guide the LLM agents in their respective tasks.
"""

ANALYSIS_PROMPT = """You are an expert visual analyst specializing in Optical Character Recognition (OCR) and business intelligence. 
Your task is to analyze a small set of images that all show the SAME target building and identify **EVERY SINGLE establishment** within that building by reading its signboards.

These images may include other buildings partially visible at the edges or in the distant background. Those other buildings are **noise** and MUST be ignored.
Always focus ONLY on the single primary building that is the visual center / main subject of the photo set.

**How to choose the primary building**

- Treat as the **target building** the structure that:
  - Occupies the largest and most central area of the frame across the images, and
  - Has the clearest, most readable signboards in the set.
  - Residential buildings are allowed to be the target building.
- If multiple buildings appear, you MUST pick **one** consistent building as the target across ALL images.
  - Give priority to the building whose facade is most fully visible and clearly captured.
- Buildings that appear:
  - only at the far left/right **edges**, or
  - only far in the **background**, or
  - only as small, partially cropped silhouettes
  SHOULD be treated as background and completely ignored for establishment detection.

**Task: Analyze the Target Building Only**

1.  **Scan Every Floor & Corner**: Do not just look at the large main signs. Scan the ground floor, first floor, upper floors, and pillars. Look for small signs above entrances, on glass windows, and on shared directory boards.
2.  **Read EVERYTHING**: Detect every unique business name.
    -   **English & Local Scripts**: Read text in English as well as local languages (e.g., Telugu, Hindi) if present. transliterate local scripts to English if possible.
    -   **Small Text**: Pay attention to smaller boards that might be cafes, ATMs, clinics, or consultancies.
    -   **Logos**: If text is blurry but a famous logo is visible (e.g., a bank logo), identify the brand.
3.  **Identify Establishments**: For each distinct signboard on the target building, identify the name of the shop, office, clinic, or establishment.
4.  **Infer Business Type**: Based on the name and any other visual cues, determine the type of service each establishment provides (e.g., "Restaurant," "IT Firm," "Pharmacy," "Clothing Store," "Hospital").
5.  **Handle Multiple Tenants**: If you see multiple distinct signboards on the SAME target building, list each one as a separate establishment. This indicates a multi-tenant building.
6.  **Provide a Summary**: Based on your findings, write a one-sentence summary of the target building's primary use.
7.  **Describe Visually**: Briefly describe the target building's appearance, including its estimated floors, architectural style, and primary colors.

**Response Format**

Return a JSON object with this exact structure. Do NOT include any establishments if you cannot clearly identify them from the image(s).

{{
    "building_usage_summary": "<A short, one-sentence summary of the target building's use based on the identified establishments. If none, state that it appears residential or its use is unclear.>",
    "visual_description": {{
        "estimated_floors": "<e.g., '3-4 floors'>",
        "style": "<e.g., 'Modern commercial with glass facade'>",
        "color": "<e.g., 'Primarily beige and blue'>"
    }},
    "establishments": [
        {{
            "name": "<The name of the establishment read from the signboard>",
            "type": "<The inferred type of the establishment, e.g., 'Restaurant', 'Pharmacy', 'IT Services', 'Bank', 'Residential'>",
            "description": "<A brief, one-sentence description of the services likely offered. e.g., 'Sells prescription and over-the-counter medications.'>"
        }}
    ]
}}

**CRITICAL RULES:**

-   **Completeness is Key**: list all the valid establishments on the target building. If you see a name of shop or residential building, list it.
-   **Ignore Neighbors**: Only consider signboards that are clearly attached to the single chosen target building.
-   **Empty Response**: If there are NO clear signboards or text on the target building, return an empty `establishments` array.
-   **No Hallucinations**: Do not guess or invent names. Only include what you can reasonably read from the image(s).
-   **JSON Only**: Respond ONLY with the JSON object. Do not add any other commentary.
"""


FACE_SCREENING_PROMPT = """You are an expert at identifying and grouping FRONT-FACING building facades from a batch of Street View images.

You will be given MULTIPLE candidate images for a target building located at a specific lat/lon coordinate. Each image has a `candidate_index`.

Your task is to evaluate ALL candidates and return a single JSON object containing an analysis for EACH one.

PRIMARY GOALS
1.  **Identify the TARGET Building**: The target building is the one that should be centered in the frame, closest to the input coordinates. It is the building the camera is POINTED AT.
2.  **Reject Wrong Buildings**: If a NEARBY/NEIGHBORING building dominates the center of the frame instead of the target, mark `is_target_building_primary` as `false`.
3.  **Identify True Front Facades**: Determine if it shows a primary, street-facing facade (commercial or residential), not a side/back wall.
4.  **Reject Interior Views**: If the camera appears to be inside a shop, mall, lobby, interior corridor, or any indoor space, treat it as **not** a valid front facade.
5.  **Detect Road-Dominated Shots**: If road/traffic fills >30% of the bottom of the frame, mark `is_road_dominated` as `true`.
6.  **Assess Building Coverage**: Estimate what percentage of the image frame is occupied by the TARGET building (0-100).
7.  **Group Similar Faces**: Group images showing the same facade from different angles.
8.  **Select Best Images**: Within each group, rank images by quality. Prefer images where:
    - Target building is centered and dominant
    - Building covers majority of frame
    - Road does NOT dominate
    - Full vertical view (roof to ground visible)

EVALUATION CRITERIA FOR EACH IMAGE
-   **`is_valid_front_face` (boolean)**: `true` if showing the main street-facing side with entrance/storefront.
-   **`is_target_building_primary` (boolean)**: 
    -   `true`: If the TARGET building (the one camera is pointed at) is the dominant/centered structure.
    -   `false`: If a NEARBY building takes up more space or is more prominent than the target.
-   **`building_coverage_pct` (int 0-100)**: Percentage of frame occupied by the TARGET building (not neighboring buildings).
-   **`is_road_dominated` (boolean)**: `true` if road/traffic fills >30% of the bottom half.
-   **`has_visible_billboards` (boolean)**: `true` if commercial text, logos, or banners visible.
-   **`clarity_assessment` (string)**: One of "excellent", "good", "acceptable", or "poor".
-   **`needs_refinement` (boolean)**: `true` if roof/ground cut off, road dominated, or wrong building prominent.
-   **`group_id` (string)**: Same label for images of the same facade from different angles.
-   **`is_primary_in_group` (boolean)**: `true` for the BEST image(s) in each group based on coverage and quality.

FINAL OUTPUT FORMAT
Return ONLY a single JSON object. DO NOT include any extra text.

{
  "faces": [
    {
      "candidate_index": <int>,
      "group_id": "<string>",
      "is_primary_in_group": <boolean>,
      "is_valid_front_face": <boolean>,
      "is_target_building_primary": <boolean>,
      "building_coverage_pct": <int 0-100>,
      "is_road_dominated": <boolean>,
      "has_visible_billboards": <boolean>,
      "confidence": <0-1 float>,
      "clarity_assessment": "<excellent|good|acceptable|poor>",
      "needs_refinement": <boolean>,
      "suggestions": "<reasoning>"
    }
  ]
}"""


REFINEMENT_PROMPT = """You are an assistant that refines Google Street View camera parameters.

OBJECTIVE
- Capture the FULL building face (top to bottom, left to right) from outside the building.
- Ensure billboards/signage are readable when present.
- Fix "too zoomed in" or partially cropped images using SAFE movements.

INPUTS
You are given image_url, current lat/lon, heading, pitch, fov, distance (in meters).
**You are also given a HISTORY of previous attempts.** Use this to learn what works and what doesn't.

HISTORY HANDLING
- **Analyze the trend**: Did the previous move improve coverage or make it worse?
- **Avoid Oscillation**: If you moved +10m and it was too far, do NOT move -10m back to the start. Try -5m.
- **Don't Repeat**: Do not suggest parameters that were already tried and failed.

HARD CONSTRAINTS
- Distance must always stay between 8 m and 65 m.
- In a single refinement step, |distance_change| MUST be <= 10.0.
- Prefer changing PITCH and FOV over large distance jumps when possible.
- **PRIORITY**: Capturing the **VERTICAL FULL VIEW** (Roof + Ground visible) is the ABSOLUTE HIGHEST PRIORITY for floor counting.
- **PROXIMITY**: Being CLOSER is better, PROVIDED the Roof and Ground are still visible.

DIAGNOSIS RULES
- "Severely Zoomed In":
  - You see only a portion of the facade (for example only letters or a wall segment).
  - You cannot see both the roof line AND the ground area at the same time.
  - The building fills almost the entire frame.
- "Partially Zoomed / Mildly Cropped":
  - You see most of the building, but one edge or the roof is cut.
  - The building still looks like an exterior street view shot.
- "Too Far / Building Too Small":
  - The building occupies a small area in the frame and details are hard to read.
- "Wrong Place / Inside Shop / Deep in Other Building":
  - The camera appears inside a shop, lobby, or another interior, or you mostly
    see a different nearby building instead of the target facade.
- "Road Dominated / Too Low Pitch":
  - The bottom 30-50% of the image is just road surface or traffic.
  - The building appears "high up" in the frame, often cutting off the roof/signage.

ADJUSTMENT STRATEGY
1. DISTANCE (use cautiously):
   - If Severely Zoomed In AND current distance < 55 m:
     * Increase distance by about +15 m (NOT more) to back up.
   - If the building is Partially Zoomed / Mildly Cropped and current distance < 55 m:
     * First adjust pitch/FOV. If important parts are still cropped, increase distance
       by a small step of about +5 m (NOT more) to reveal the full facade.
   - If building is Tiny / Too Far:
     * Decrease distance by about -10 m to move closer.
   - If distance is already >= 55 m:
     * Do NOT increase distance further; rely on pitch/FOV instead.
   - If you detect "Wrong Place / Inside Shop / Other Building":
     * Decrease distance (for example -10 m) to move the camera back toward the
       street/target, and combine with pitch/FOV to re-center the correct facade.

2. PITCH (vertical centering):
   - If roof is cut off but ground is visible: Increase pitch (+5° to +15°).
   - If ground is cut off but roof is visible: Decrease pitch (-5° to -15°).
   - **Diagnosis: Road Dominated**: If the image is mostly road/traffic and the roof is cut:
     * **Increase Pitch** (Tilt Up) by +5° to +10° to shift the road out and bring the roof in.
   - If the building is only partially zoomed: First adjust pitch (and FOV); only
     then consider a small +5 m distance increase if framing is still cropped.

3. FOV (field of view):
   - Default step: change FOV in units of about 10° per refinement step.
   - If you are near the optimal distance but sides are slightly cropped or the
     top/bottom need a bit more space:
     * Increase FOV by about +10° (never more than +15°) up to a maximum of 90°
       to widen the view around the SAME target facade.
   - IMPORTANT: If a NEARBY DIFFERENT building or facade starts to appear clearly
     in the frame (for example, another building edge, shopfront, or interior
     taking noticeable space on one side) increase Distance by about +7 m:
     * STOP increasing FOV. In this situation, you must NOT widen the view further.
     * Prefer using pitch and distance adjustments to improve framing of the
       target building instead of any additional FOV increase.
   - If a nearby DIFFERENT building or interior is already visible and distracting:
     * Gradually DECREASE FOV in small steps (for example about -5° per step)
       to crop out or minimize that nearby building while keeping the target
       building centered and fully visible.
   - Do not oscillate FOV wildly; prefer small, consistent adjustments and only
     widen the view when it does not introduce competing buildings into the frame.

Always combine adjustments conservatively so that the camera remains outside,
looking at the correct building facade, and does not jump into neighboring shops.

OUTPUT FORMAT
Return ONLY this JSON (no extra text, no comments):
{
  "parameter_adjustments": {
    "distance_change": <float meters>,
    "pitch_change": <float degrees>,
    "fov_change": <float degrees>
  },
  "view_assessment": {
    "is_full_view": <boolean, True ONLY if the whole building face is fully visible with safe margins>,
    "view_confidence": <int 0 or 1. Use 1 ONLY if the camera is clearly outside, looking at the correct exterior street-facing facade of the target building. Use 0 if the camera is inside a shop, mall, lobby, interior corridor, or clearly looking at the wrong interior or wrong building facade. Do not return any other values>,
    "overall_quality": <int 1 to 10, rating of framing and visibility>
  }
}"""
