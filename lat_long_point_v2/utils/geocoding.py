import googlemaps
import math
import os
from dotenv import load_dotenv
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance in meters between two points."""
    R = 6371000  # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def snap_to_home_center(click_lat, click_lng):
    # Phase 1: Check for Roads API
    try:
        roads_results = gmaps.nearest_roads((click_lat, click_lng))
        if roads_results:
            # Check the nearest snapped point
            road_point = roads_results[0]['location']
            road_lat = road_point['latitude']
            road_lng = road_point['longitude']
            
            distance = haversine(click_lat, click_lng, road_lat, road_lng)
            
            # If within 5 meters, classify as Road
            if distance < 5:
                # Get road address (optional lookup)
                address_res = gmaps.reverse_geocode((road_lat, road_lng))
                road_address = address_res[0]['formatted_address'] if address_res else "Unknown Road"
                
                return {
                    "type": "Road",
                    "address": road_address,
                    "lat": road_lat,
                    "lng": road_lng,
                    "distance_to_road_m": round(distance, 2)
                }
    except Exception as e:
        print(f"Roads API Warning: {e}")

    # Phase 2: Reverse Geocoding for ROOFTOP buildings
    results = gmaps.reverse_geocode((click_lat, click_lng))

    if results:
        # Look for the most precise building/address match
        for res in results:
            # Check if it is a specific building or sub-unit
            is_building = any(t in res['types'] for t in ['street_address', 'premise', 'subpremise'])
            accuracy = res['geometry']['location_type']
            
            # Snap ONLY if it's a ROOFTOP match
            if is_building and accuracy == 'ROOFTOP':
                return {
                    "type": "Residential",
                    "address": res['formatted_address'],
                    "lat": res['geometry']['location']['lat'],
                    "lng": res['geometry']['location']['lng'],
                    "accuracy": "ROOFTOP"
                }

    return {"error": "No building or road detected at this location."}

if __name__ == "__main__":
    # Test point (user's sample which is near a road)
    click_lat = 10.98795538  
    click_lng = 76.94848
    result = snap_to_home_center(click_lat, click_lng)
    print(result)
