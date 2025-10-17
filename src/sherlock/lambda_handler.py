#!/usr/bin/env python3
"""
Sherlock Core - AI-powered root cause analysis for AWS infrastructure
Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: christiangenn99+sherlock@gmail.com

AWS Lambda handler for Sherlock investigations.

Deployment options:
  1. Direct invocation: Invoke Lambda directly with investigation payload
  2. API Gateway: HTTP API that triggers Lambda
  3. EventBridge: Scheduled or event-driven investigations
  4. SNS/SQS: Queue-based processing

Example events:

1. Direct Lambda invocation:
   {
     "free_text_input": "My Lambda payment-processor is failing with errors"
   }

2. API Gateway proxy:
   {
     "body": "{\"function_name\": \"test-function\", \"region\": \"eu-west-1\"}",
     "headers": {...},
     "requestContext": {...}
   }

3. EventBridge:
   {
     "detail": {
       "function_name": "test-function",
       "region": "eu-west-1"
     }
   }
"""

import json
from typing import Dict, Any

from .handlers import handle_investigation

# Initialize telemetry on module import (Lambda cold start)
from .utils.config import setup_strands_telemetry
setup_strands_telemetry()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Sherlock investigations.

    Args:
        event: Lambda event (varies by trigger source)
        context: Lambda context object

    Returns:
        Investigation report or error response
    """
    print(f"[Sherlock Lambda] Received event: {json.dumps(event, default=str)}")

    # Parse payload based on event source
    payload = _parse_event(event)

    # Run investigation using shared handler
    result = handle_investigation(payload)

    # Add Lambda-specific metadata
    if "investigation" in result:
        result["investigation"]["execution_environment"] = "lambda"
        result["investigation"]["aws_request_id"] = context.aws_request_id
        result["investigation"]["function_name"] = context.function_name
        result["investigation"]["memory_limit_mb"] = context.memory_limit_in_mb
        result["investigation"]["remaining_time_ms"] = context.get_remaining_time_in_millis()

    print(f"[Sherlock Lambda] Investigation completed: {result.get('investigation', {}).get('status', 'unknown')}")

    # Return response (format depends on trigger)
    return _format_response(event, result)


def _parse_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse Lambda event to extract investigation payload.

    Supports multiple event sources:
    - Direct invocation: event is the payload
    - API Gateway: extract from body
    - EventBridge: extract from detail
    - SNS: extract from message
    - SQS: extract from body
    """
    # API Gateway (HTTP API or REST API)
    if "body" in event and "requestContext" in event:
        try:
            return json.loads(event["body"])
        except (json.JSONDecodeError, TypeError):
            return {"error": "Invalid JSON in request body"}

    # EventBridge
    if "detail" in event and "source" in event:
        return event["detail"]

    # SNS
    if "Records" in event and event["Records"][0].get("EventSource") == "aws:sns":
        try:
            return json.loads(event["Records"][0]["Sns"]["Message"])
        except (json.JSONDecodeError, KeyError):
            return {"error": "Invalid SNS message"}

    # SQS
    if "Records" in event and event["Records"][0].get("eventSource") == "aws:sqs":
        try:
            return json.loads(event["Records"][0]["body"])
        except (json.JSONDecodeError, KeyError):
            return {"error": "Invalid SQS message"}

    # Direct invocation - event is the payload
    return event


def _format_response(event: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format response based on event source.

    API Gateway requires specific response format with statusCode and body.
    Direct invocation can return the result directly.
    """
    # API Gateway - needs HTTP response format
    if "requestContext" in event:
        status_code = 200 if result.get("success", True) else 500

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",  # CORS
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": json.dumps(result)
        }

    # Direct invocation, EventBridge, SNS, SQS - return result directly
    return result


# Support for testing locally
if __name__ == "__main__":
    """Test Lambda handler locally."""
    import sys

    # Mock Lambda context
    class MockContext:
        request_id = "local-test-request-id"
        function_name = "sherlock-investigator-local"
        memory_limit_in_mb = 2048

        def get_remaining_time_in_millis(self):
            return 900000  # 15 minutes

    # Test event - direct invocation
    test_event = {
        "free_text_input": "My Lambda function payment-processor is failing with division by zero errors"
    }

    # Test event - API Gateway
    # test_event = {
    #     "body": json.dumps({
    #         "function_name": "test-function",
    #         "region": "eu-west-1"
    #     }),
    #     "requestContext": {
    #         "requestId": "test-request-id"
    #     }
    # }

    print("Testing Lambda handler locally...")
    result = lambda_handler(test_event, MockContext())
    print(json.dumps(result, indent=2, default=str))
