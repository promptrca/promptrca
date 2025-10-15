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

"""

from strands import tool
import json


@tool
def query_logs_by_trace_id(query: str, region: str = None) -> str:
    region = region or get_region()
    """
    Query CloudWatch Logs Insights for ALL logs related to a specific X-Ray trace ID.
    This is THE KEY tool for trace-driven investigation - it correlates logs with traces.

    Args:
        trace_id: The X-Ray trace ID to search for (e.g., "1-68e915e7-7a2c7c6d1427db5e5b97c431")
        region: AWS region (default: from environment)

    Returns:
        JSON string with all logs matching the trace ID across all log groups
    """
    import boto3
    import time
    from datetime import datetime, timedelta

    try:
        client = boto3.client('logs', region_name=region)

        # CloudWatch Insights query to find logs with this trace ID
        query = f'''
        fields @timestamp, @message, @logStream, @log
        | filter @message like /{trace_id}/
        | sort @timestamp desc
        | limit 100
        '''

        # Start the query (24 hours lookback)
        start_time = int((datetime.now() - timedelta(hours=24)).timestamp())
        end_time = int(datetime.now().timestamp())

        # Try to find existing log groups
        existing_log_groups = []
        try:
            paginator = client.get_paginator('describe_log_groups')
            for page in paginator.paginate():
                for log_group in page.get('logGroups', []):
                    log_group_name = log_group['logGroupName']
                    # Include Lambda, Step Functions, and API Gateway logs
                    if any(prefix in log_group_name for prefix in ['/aws/lambda/', '/aws/stepfunctions/', 'API-Gateway-Execution-Logs']):
                        existing_log_groups.append(log_group_name)
                        if len(existing_log_groups) >= 20:  # Limit to 20 log groups
                            break
                if len(existing_log_groups) >= 20:
                    break
        except Exception as e:
            return json.dumps({
                "trace_id": trace_id,
                "error": f"Failed to list log groups: {str(e)}"
            })

        if not existing_log_groups:
            return json.dumps({
                "trace_id": trace_id,
                "error": "No serverless log groups found",
                "searched_patterns": ["/aws/lambda/", "/aws/stepfunctions/", "API-Gateway-Execution-Logs"]
            })

        # Start Insights query
        response = client.start_query(
            logGroupNames=existing_log_groups,
            startTime=start_time,
            endTime=end_time,
            queryString=query
        )

        query_id = response['queryId']

        # Wait for query to complete (max 30 seconds)
        max_wait = 30
        waited = 0
        while waited < max_wait:
            time.sleep(1)
            waited += 1

            result = client.get_query_results(queryId=query_id)
            status = result['status']

            if status == 'Complete':
                logs = []
                for result_row in result.get('results', []):
                    log_entry = {}
                    for field in result_row:
                        log_entry[field['field']] = field['value']
                    logs.append(log_entry)

                return json.dumps({
                    "trace_id": trace_id,
                    "log_groups_searched": existing_log_groups,
                    "match_count": len(logs),
                    "logs": logs[:50],  # Return top 50 matches
                    "query": query
                }, indent=2)

            elif status in ['Failed', 'Cancelled']:
                return json.dumps({
                    "trace_id": trace_id,
                    "error": f"Query {status.lower()}",
                    "status": status
                })

        # Timeout
        return json.dumps({
            "trace_id": trace_id,
            "error": "Query timeout after 30 seconds",
            "status": "Timeout"
        })

    except Exception as e:
        return json.dumps({"error": str(e), "trace_id": trace_id})


@tool
def get_stepfunctions_execution_details(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get detailed Step Functions execution information including status, input, output, and history.
    Use this when you have a Step Functions execution ARN to investigate what happened.

    Args:
        execution_arn: The Step Functions execution ARN
        region: AWS region (default: from environment)

    Returns:
        JSON string with execution details including history events
    """
    import boto3

    try:
        client = boto3.client('stepfunctions', region_name=region)

        # Get execution details
        exec_response = client.describe_execution(executionArn=execution_arn)

        # Get execution history
        history_response = client.get_execution_history(
            executionArn=execution_arn,
            maxResults=100,
            reverseOrder=True
        )

        config = {
            "execution_arn": exec_response.get('executionArn'),
            "state_machine_arn": exec_response.get('stateMachineArn'),
            "status": exec_response.get('status'),
            "start_date": str(exec_response.get('startDate')),
            "stop_date": str(exec_response.get('stopDate')) if exec_response.get('stopDate') else None,
            "input": json.loads(exec_response.get('input', '{}')),
            "output": json.loads(exec_response.get('output', '{}')) if exec_response.get('output') else None,
            "error": exec_response.get('error'),
            "cause": exec_response.get('cause'),
            "trace_header": exec_response.get('traceHeader'),
            "history_event_count": len(history_response.get('events', [])),
            "history_events": [
                {
                    "id": event.get('id'),
                    "timestamp": str(event.get('timestamp')),
                    "type": event.get('type'),
                    "details": {k: v for k, v in event.items() if k not in ['id', 'timestamp', 'type']}
                }
                for event in history_response.get('events', [])[:20]  # Top 20 events
            ]
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "execution_arn": execution_arn})


@tool
def resolve_api_gateway_id(resolve: str, region: str = None) -> str:
    region = region or get_region()
    """
    Resolve API Gateway name or ID to the actual REST API ID.
    Handles both cases:
    - If given a numeric ID (like "142gh05m9a"), returns it as-is
    - If given a name (like "sherlock-test-test-api"), looks it up and returns the ID

    Args:
        api_name_or_id: API Gateway name or ID
        region: AWS region (default: from environment)

    Returns:
        JSON string with the REST API ID
    """
    import boto3
    import re

    try:
        # Check if it's already a REST API ID format (alphanumeric, typically 10 chars)
        # REST API IDs look like: 142gh05m9a, abc123xyz, etc.
        if re.match(r'^[a-z0-9]{10}$', api_name_or_id):
            return json.dumps({
                "api_id": api_name_or_id,
                "source": "direct",
                "message": "Already a valid REST API ID"
            })

        # Otherwise, search for it by name
        client = boto3.client('apigateway', region_name=region)

        # List all REST APIs and find by name
        paginator = client.get_paginator('get_rest_apis')
        for page in paginator.paginate():
            for api in page.get('items', []):
                if api['name'] == api_name_or_id:
                    return json.dumps({
                        "api_id": api['id'],
                        "api_name": api['name'],
                        "source": "name_lookup",
                        "message": f"Resolved '{api_name_or_id}' to REST API ID '{api['id']}'"
                    })

        # Not found
        return json.dumps({
            "error": "API Gateway not found",
            "api_name_or_id": api_name_or_id,
            "message": f"No REST API found with name '{api_name_or_id}'"
        })

    except Exception as e:
        return json.dumps({"error": str(e), "api_name_or_id": api_name_or_id})


@tool
def get_all_resources_from_trace(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Extract ALL AWS resources involved in an X-Ray trace.
    This discovers Lambda functions, Step Functions, API Gateways, and other services.

    Args:
        trace_id: The X-Ray trace ID
        region: AWS region (default: from environment)

    Returns:
        JSON string with all discovered resources and their metadata
    """
    import boto3

    try:
        client = boto3.client('xray', region_name=region)
        response = client.batch_get_traces(TraceIds=[trace_id])

        if not response.get('Traces'):
            return json.dumps({"error": "Trace not found", "trace_id": trace_id})

        trace = response['Traces'][0]
        segments = trace.get('Segments', [])

        resources = []
        discovered = set()  # Avoid duplicates

        for segment in segments:
            segment_doc = segment.get('Document', {})

            # Parse JSON if needed
            if isinstance(segment_doc, str):
                try:
                    segment_doc = json.loads(segment_doc)
                except:
                    continue

            segment_name = segment_doc.get('name', '')
            origin = segment_doc.get('origin', '')

            # Extract resource info
            resource = None

            # Lambda detection
            if 'AWS::Lambda' in origin or 'lambda' in segment_name.lower():
                func_name = segment_name
                if func_name and func_name not in discovered:
                    resource = {
                        "type": "lambda",
                        "name": func_name,
                        "arn": segment_doc.get('resource_arn'),
                        "segment_id": segment.get('Id')
                    }
                    discovered.add(func_name)

            # Step Functions detection
            elif 'AWS::STEPFUNCTIONS' in origin or 'STEPFUNCTIONS' in segment_name:
                aws_metadata = segment_doc.get('aws', {})
                execution_arn = aws_metadata.get('execution_arn')
                if execution_arn and execution_arn not in discovered:
                    resource = {
                        "type": "stepfunctions",
                        "name": "STEPFUNCTIONS",
                        "execution_arn": execution_arn,
                        "segment_id": segment.get('Id')
                    }
                    discovered.add(execution_arn)

            # API Gateway detection
            elif 'AWS::ApiGateway' in origin or '/' in segment_name:
                parts = segment_name.split('/')
                if len(parts) >= 2:
                    api_id = parts[0]
                    stage = parts[1] if len(parts) > 1 else 'unknown'
                    key = f"{api_id}:{stage}"
                    if key not in discovered:
                        resource = {
                            "type": "apigateway",
                            "name": api_id,
                            "stage": stage,
                            "segment_id": segment.get('Id')
                        }
                        discovered.add(key)

            if resource:
                resources.append(resource)

        return json.dumps({
            "trace_id": trace_id,
            "duration": trace.get('Duration'),
            "is_partial": trace.get('IsPartial', False),
            "resource_count": len(resources),
            "resources": resources
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "trace_id": trace_id})
