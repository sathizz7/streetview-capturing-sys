"""
Status Handler - Returns the status and result of a building capture request.
"""

import os
import json
import boto3
from decimal import Decimal

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
TABLE_NAME = os.environ.get('TABLE_NAME', 'BuildingRequestsTable')
ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '*')

table = dynamodb.Table(TABLE_NAME)


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, set):
            return list(obj)
        return super(DecimalEncoder, self).default(obj)


def get_cors_headers():
    """Return CORS headers for responses."""
    return {
        'Access-Control-Allow-Origin': ALLOWED_ORIGINS,
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'OPTIONS,GET',
        'Content-Type': 'application/json'
    }


def lambda_handler(event, context):
    """
    Handle GET /api/v2/status/{rev_id} requests.
    
    Path Parameters:
        rev_id: The request ID to check status for
    
    Response:
        {
            "status": "PENDING" | "IN_PROGRESS" | "DONE" | "FAILED",
            "rev_id": "<uuid>",
            "result": {...} (if DONE),
            "error": "..." (if FAILED),
            "created_at": "...",
            "started_at": "..." (if started),
            "finished_at": "..." (if finished)
        }
    """
    print(f"Received event: {json.dumps(event)}")
    
    headers = get_cors_headers()
    
    try:
        # Extract rev_id from path parameters
        path_params = event.get('pathParameters', {}) or {}
        rev_id = path_params.get('rev_id')
        
        if not rev_id:
            return {
                'statusCode': 400,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Missing rev_id in path'
                })
            }
        
        # Query DynamoDB
        response = table.get_item(Key={'rev_id': rev_id})
        item = response.get('Item')
        
        if not item:
            return {
                'statusCode': 404,
                'headers': headers,
                'body': json.dumps({
                    'status': 'error',
                    'message': f'Request {rev_id} not found'
                })
            }
        
        # Build response
        result = {
            'rev_id': item.get('rev_id'),
            'status': item.get('status', 'UNKNOWN'),
            'created_at': item.get('created_at'),
        }
        
        if item.get('started_at'):
            result['started_at'] = item['started_at']
        
        if item.get('finished_at'):
            result['finished_at'] = item['finished_at']
        
        if item.get('status') == 'DONE' and item.get('result'):
            # Parse the stored JSON result
            try:
                result['result'] = json.loads(item['result'])
            except (json.JSONDecodeError, TypeError):
                result['result'] = item['result']
        
        if item.get('status') == 'FAILED' and item.get('error'):
            result['error'] = item['error']
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(result, cls=DecimalEncoder)
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
