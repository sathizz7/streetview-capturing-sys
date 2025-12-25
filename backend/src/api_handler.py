"""
API Handler - Entry point for /create endpoint.
Accepts lat/lon, generates rev_id, and invokes ProcessBuildingFunction asynchronously.
"""

import os
import json
import uuid
import boto3
from datetime import datetime

# Initialize clients
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')

TABLE_NAME = os.environ.get('TABLE_NAME', 'BuildingRequestsTable')
PROCESSOR_FUNCTION = os.environ.get('PROCESSOR_FUNCTION', '')
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')

table = dynamodb.Table(TABLE_NAME)


def get_cors_headers():
    """Return CORS headers for responses."""
    return {
        'Access-Control-Allow-Origin': ALLOWED_ORIGINS,
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,POST',
        'Content-Type': 'application/json'
    }


def lambda_handler(event, context):
    """
    Handle POST /api/v2/create requests.
    
    Request Body:
        {
            "lat": float,
            "lon": float
        }
    
    Response:
        {
            "status": "success",
            "rev_id": "<uuid>",
            "message": "Request submitted successfully"
        }
    """
    print(f"Received event: {json.dumps(event)}")
    
    headers = get_cors_headers()
    
    try:
        # Parse request body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {}) or {}
        
        lat = body.get('lat')
        lon = body.get('lon')
        
        # Validation
        if lat is None or lon is None:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Missing required fields: lat and lon'
                })
            }
        
        # Generate unique request ID
        rev_id = str(uuid.uuid4())
        
        # Store initial request in DynamoDB
        table.put_item(Item={
            'rev_id': rev_id,
            'status': 'PENDING',
            'input': {
                'lat': str(lat),
                'lon': str(lon)
            },
            'created_at': datetime.utcnow().isoformat() + 'Z'
        })
        
        # Invoke processor function asynchronously
        if PROCESSOR_FUNCTION:
            lambda_client.invoke(
                FunctionName=PROCESSOR_FUNCTION,
                InvocationType='Event',  # Async
                Payload=json.dumps({
                    'rev_id': rev_id,
                    'input': {
                        'lat': float(lat),
                        'lon': float(lon)
                    }
                })
            )
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({
                'status': 'success',
                'rev_id': rev_id,
                'message': 'Request submitted successfully. Use /status/{rev_id} to check progress.'
            })
        }
        
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({
                'status': 'error',
                'message': 'Invalid JSON in request body'
            })
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            })
        }
