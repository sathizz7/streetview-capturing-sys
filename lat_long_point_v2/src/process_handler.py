"""
Process Handler - Worker Lambda for building capture pipeline.
Invoked asynchronously by ApiHandlerFunction.
"""

import os
import json
import sys
import asyncio
import boto3
from datetime import datetime
from decimal import Decimal

# Add parent directory to path to import backend modules
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from main import BuildingCapturePipeline

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'BuildingRequestsTable')
table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """
    Handle async processing of building capture.
    
    Triggered by ApiHandlerFunction via invoke(InvocationType='Event').
    
    Event Payload:
        {
            "rev_id": "<uuid>",
            "input": {
                "lat": float,
                "lon": float
            }
        }
    """
    print(f"Received event: {json.dumps(event)}")
    
    rev_id = event.get('rev_id')
    input_payload = event.get('input', {})
    
    if not rev_id:
        print("Error: missing rev_id")
        return {'error': 'missing rev_id'}
    
    # Update status to IN_PROGRESS
    try:
        table.update_item(
            Key={'rev_id': rev_id},
            UpdateExpression='SET #s = :s, started_at = :t',
            ExpressionAttributeNames={'#s': 'status'},
            ExpressionAttributeValues={
                ':s': 'IN_PROGRESS',
                ':t': datetime.utcnow().isoformat() + 'Z'
            }
        )
    except Exception as e:
        print(f"Failed to update status to IN_PROGRESS: {e}")
        return {'error': str(e)}
    
    try:
        # Initialize Pipeline
        pipeline = BuildingCapturePipeline()
        
        lat = float(input_payload.get('lat', 0))
        lon = float(input_payload.get('lon', 0))
        
        print(f"Starting capture for rev_id: {rev_id}, lat: {lat}, lon: {lon}")
        
        # Run the async pipeline
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(pipeline.capture_building(lat, lon))
        
        print("Capture completed successfully")
        
        # Update DB with result
        result_json = json.dumps(result, cls=DecimalEncoder)
        
        table.update_item(
            Key={'rev_id': rev_id},
            UpdateExpression='SET #s = :s, #r = :r, finished_at = :t',
            ExpressionAttributeNames={
                '#s': 'status',
                '#r': 'result'
            },
            ExpressionAttributeValues={
                ':s': 'DONE',
                ':r': result_json,
                ':t': datetime.utcnow().isoformat() + 'Z'
            }
        )
        
        return {'status': 'DONE', 'rev_id': rev_id}
        
    except Exception as e:
        print(f"Processing failed: {e}")
        
        # Update DB with failure
        try:
            table.update_item(
                Key={'rev_id': rev_id},
                UpdateExpression='SET #s = :s, #e = :e, finished_at = :t',
                ExpressionAttributeNames={
                    '#s': 'status',
                    '#e': 'error'
                },
                ExpressionAttributeValues={
                    ':s': 'FAILED',
                    ':e': str(e),
                    ':t': datetime.utcnow().isoformat() + 'Z'
                }
            )
        except Exception as db_err:
            print(f"Failed to update DB with error status: {db_err}")
        
        return {'status': 'FAILED', 'error': str(e)}
