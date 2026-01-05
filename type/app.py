import json
import os
import boto3

lambda_client = boto3.client('lambda')

def lambda_handler(event, context):
    """
    Dispatcher Handler.
    Routes requests based on 'type' field in the body.
    """
    print("Received event:", json.dumps(event))
    
    try:
        body = json.loads(event.get("body", "{}"))
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"status": "failure", "message": "Invalid JSON body"})
        }
        
    request_type = body.get("type")
    
    # Environment variables for function names
    v2_function_name = os.environ.get("V2_FUNCTION_NAME")
    v1_function_name = os.environ.get("V1_FUNCTION_NAME")
    
    if request_type == "latlong":
        target_function = v2_function_name
        print(f"Dispatching to Lat/Long V2: {target_function}")
    elif request_type == "polygon":
        target_function = v1_function_name
        print(f"Dispatching to Polygon V1: {target_function}")
    else:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "status": "failure", 
                "message": f"Unknown or missing 'type'. Supported: 'latlong', 'polygon'. Received: {request_type}"
            })
        }
        
    try:
        # Invoke the target function synchronously (RequestResponse)
        # We pass the original event through
        response = lambda_client.invoke(
            FunctionName=target_function,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        
        response_payload = response['Payload'].read().decode('utf-8')
        print("Downstream response:", response_payload)
        
        # Parse the response from the downstream lambda to return valid API Gateway response
        # The downstream lambda (if proxy integration) returns {statusCode, body, ...}
        # We can just return that directly.
        return json.loads(response_payload)
        
    except Exception as e:
        print(f"Error invoking function: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"status": "error", "message": str(e)})
        }
