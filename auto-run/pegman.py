import requests
import math

GOOGLE_API_KEY = "YOUR_API_KEY"

def get_smart_streetview_heading(target_lat, target_lon):
    """
    1. Checks if Street View exists.
    2. If yes, calculates the exact heading to look AT the target 
       from the camera's actual position.
    """
    
    # --- STEP 1: Metadata Availability Check ---
    metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    params = {
        "location": f"{target_lat},{target_lon}",
        "radius": 50,  # Search within 50 meters of the target
        "key": GOOGLE_API_KEY
    }
    
    response = requests.get(metadata_url, params=params).json()
    
    if response.get("status") != "OK":
        return {
            "available": False, 
            "message": "No Street View found near this location."
        }

    # --- STEP 2: Extract Camera Location ---
    # The 'location' in the response is where the CAR was, not your target.
    camera_lat = response["location"]["lat"]
    camera_lon = response["location"]["lng"]
    pano_id = response["pano_id"]

    # --- STEP 3: Calculate Bearing (The "Look At" Logic) ---
    # We need the angle from Camera -> Target
    heading = calculate_bearing(camera_lat, camera_lon, target_lat, target_lon)
    
    return {
        "available": True,
        "pano_id": pano_id,
        "camera_location": (camera_lat, camera_lon),
        "target_location": (target_lat, target_lon),
        "calculated_heading": heading, # <--- PASS THIS TO THE IMAGE API
        "message": f"Found pano {pano_id}. Camera should face {heading}° to see target."
    }

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculates the bearing from Point A (Camera) to Point B (Target).
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    diff_lon_rad = math.radians(lon2 - lon1)

    x = math.sin(diff_lon_rad) * math.cos(lat2_rad)
    y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
        math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(diff_lon_rad)

    initial_bearing = math.atan2(x, y)
    
    # Convert from radians to degrees and normalize to 0-360
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return round(compass_bearing, 2)

# --- Usage ---
# target = (latitude of that Red Marker in your image)
result = get_smart_streetview_heading(-10.9849, 76.9475) 
print(result)