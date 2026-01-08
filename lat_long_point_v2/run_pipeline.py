"""
Runner Script for Building Detection V2 Pipeline.

Supports partial execution (NO-LLM mode) for debugging geometry/API steps.

Usage:
    python run_pipeline.py --lat 12.97 --lon 77.59 --no-llm
"""

import asyncio
import argparse
import json
import logging
from main import BuildingCapturePipeline
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def run():
    parser = argparse.ArgumentParser(description="V2 Pipeline Runner")
    parser.add_argument("--lat", type=float, required=True, help="Target Latitude")
    parser.add_argument("--lon", "--long", dest="lon", type=float, required=True, help="Target Longitude")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--no-llm", action="store_true", help="Run only geometry/validation steps (Skip LLM agents)")
    parser.add_argument("--polygon", type=str, help="JSON string of polygon coordinates e.g. '[[lat,lon],...]'")
    
    args = parser.parse_args()
    
    logger.info(f"Starting Pipeline Runner for ({args.lat}, {args.lon})")
    
    # Parse polygon if provided
    polygon = None
    if args.polygon:
        try:
            raw_poly = json.loads(args.polygon)
            
            # Helper to normalize polygon data
            def get_exterior_ring(data):
                # Case 1: GeoJSON Object
                if isinstance(data, dict):
                    coords = data.get("geometry", data).get("coordinates")
                    # Recursive call on coordinates
                    return get_exterior_ring(coords)
                
                # Case 2: List (Coordinates)
                if isinstance(data, list):
                    if not data: return None
                    
                    # Depth check
                    # Depth 2: [[x,y], [x,y]] -> This is the ring
                    if isinstance(data[0], list) and not isinstance(data[0][0], list):
                         return data
                    
                    # Depth 3: [[[x,y],...]] -> Polygon (List of rings). Return 1st ring.
                    if isinstance(data[0][0], list) and not isinstance(data[0][0][0], list):
                        return data[0]

                    # Depth 4: [[[[x,y],...]]] -> MultiPolygon using user example. Return 1st poly, 1st ring.
                    # Standard GeoJSON MultiPolygon is Depth 4 also: [ [ [ [x,y]... ] ] ]
                    if isinstance(data[0][0][0], list):
                        return data[0][0]
                
                return None

            ring = get_exterior_ring(raw_poly)
            
            if ring:
                # Convert [Lon, Lat] to [Lat, Lon] if necessary
                # GeoJSON is [Lon, Lat]. User inputs like 78, 17 confirm this.
                # Heuristic: Lat is typically -90 to 90. Lon -180 to 180.
                # If we see the first coord > 90 or < -90, it's definitely Lon.
                # But here we assume GeoJSON standard [Lon, Lat].
                # We simply swap to [Lat, Lon] for internal use.
                polygon = [[p[1], p[0]] for p in ring]
                logger.info(f"Loaded polygon with {len(polygon)} points (Swapped Lon/Lat to Lat/Lon)")
            else:
                 logger.error("Could not extract exterior ring from polygon data")
                 return

        except json.JSONDecodeError:
            logger.error("Invalid polygon JSON string")
            return
        except Exception as e:
            logger.error(f"Error processing polygon: {e}")
            return
    
    pipeline = BuildingCapturePipeline()
    
    # Run pipeline with skip_llm flag
    result = await pipeline.capture_building(
        args.lat, 
        args.lon, 
        skip_llm=args.no_llm,
        polygon=polygon
    )
    
    # Output handling
    output_json = json.dumps(result, indent=2)
    
    if args.output:
        with open(args.output, "w") as f:
            f.write(output_json)
        logger.info(f"Results written to {args.output}")
    else:
        print("\n" + "="*50)
        print("PIPELINE RESULT")
        print("="*50)
        print(output_json)

if __name__ == "__main__":
    asyncio.run(run())
