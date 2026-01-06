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
    
    args = parser.parse_args()
    
    logger.info(f"Starting Pipeline Runner for ({args.lat}, {args.lon})")
    
    pipeline = BuildingCapturePipeline()
    
    # Run pipeline with skip_llm flag
    result = await pipeline.capture_building(
        args.lat, 
        args.lon, 
        skip_llm=args.no_llm
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
