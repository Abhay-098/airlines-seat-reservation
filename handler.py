import json
import os
import uuid
import boto3

# Initialize DynamoDB client
# The region and other settings are typically configured by the Serverless Framework
# and AWS environment variables, so we don't hardcode them.
dynamodb_client = boto3.client('dynamodb')
# We'll use an environment variable for the table name, set in serverless.yml
table_name = os.environ['DYNAMODB_TABLE']

def handle_request(event, context):
    """
    Main handler for all incoming API Gateway requests.
    This function acts as a router for different HTTP methods and paths.
    """
    try:
        http_method = event.get('httpMethod')
        path = event.get('path')

        if http_method == 'GET' and path == '/seats':
            return get_seats()
        elif http_method == 'POST' and path == '/reserve':
            return reserve_seat(json.loads(event.get('body')))
        elif http_method == 'POST' and path == '/cancel':
            return cancel_seat(json.loads(event.get('body')))
        else:
            return {
                'statusCode': 404,
                'body': json.dumps({'message': 'Not Found'})
            }

    except Exception as e:
        print(f"Error handling request: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'An internal error occurred.'})
        }

def get_seats():
    """
    Retrieves all seat reservations from the DynamoDB table.
    """
    try:
        response = dynamodb_client.scan(TableName=table_name)
        items = response['Items']
        
        # DynamoDB returns data with type annotations (e.g., {'S': 'A1', 'N': '123'}).
        # We need to clean this up for the front end.
        seats = {}
        for item in items:
            seat_id = item['seatId']['S']
            reserved_by = item['reservedBy']['S']
            seats[seat_id] = {
                'reserved_by': reserved_by
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps(seats)
        }
    except Exception as e:
        print(f"Error getting seats: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Failed to retrieve seats.'})
        }


def reserve_seat(data):
    """
    Reserves a seat by adding an item to the DynamoDB table.
    Uses a condition expression to prevent conflicts.
    """
    seat_id = data.get('seatId')
    user_id = data.get('userId')
    
    if not seat_id or not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Seat ID and User ID are required.'})
        }

    try:
        # Use a transaction to ensure no other user reserves the seat at the same time
        dynamodb_client.put_item(
            TableName=table_name,
            Item={
                'seatId': {'S': seat_id},
                'reservedBy': {'S': user_id}
            },
            ConditionExpression='attribute_not_exists(seatId)'
        )
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f"Seat {seat_id} reserved successfully."})
        }
    except dynamodb_client.exceptions.ConditionalCheckFailedException:
        return {
            'statusCode': 409,
            'body': json.dumps({'message': f"Seat {seat_id} is already reserved."})
        }
    except Exception as e:
        print(f"Error reserving seat: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'An error occurred during reservation.'})
        }

def cancel_seat(data):
    """
    Cancels a seat reservation by deleting an item from the DynamoDB table.
    """
    seat_id = data.get('seatId')
    user_id = data.get('userId')
    
    if not seat_id or not user_id:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Seat ID and User ID are required.'})
        }

    try:
        # Check if the seat is reserved by the current user before deleting
        response = dynamodb_client.delete_item(
            TableName=table_name,
            Key={'seatId': {'S': seat_id}},
            ConditionExpression='reservedBy = :reservedBy',
            ExpressionAttributeValues={
                ':reservedBy': {'S': user_id}
            }
        )
        return {
            'statusCode': 200,
            'body': json.dumps({'message': f"Reservation for seat {seat_id} canceled."})
        }
    except dynamodb_client.exceptions.ConditionalCheckFailedException:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'You cannot cancel this reservation as it does not belong to you.'})
        }
    except Exception as e:
        print(f"Error canceling reservation: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'An error occurred while canceling.'})
        }
