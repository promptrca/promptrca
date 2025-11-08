#!/usr/bin/env python3
"""
PromptRCA Core - AI-powered root cause analysis for AWS infrastructure
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

Contact: info@promptrca.com

"""

from strands import tool
from typing import Dict, Any, Optional
import json
from ..context import get_aws_client


@tool
def get_api_gateway_stage_config(api_id: str, stage_name: str) -> str:
    """
    Retrieve comprehensive API Gateway stage configuration for integration and routing analysis.
    
    This tool fetches all critical stage settings needed to diagnose API Gateway issues:
    - Integration configurations (Lambda, Step Functions, HTTP endpoints)
    - IAM roles and credentials used for integrations
    - Caching and performance settings
    - X-Ray tracing configuration
    - Method settings and throttling
    - Stage variables and deployment details
    
    Args:
        api_id: The API Gateway REST API ID (e.g., "abc123xyz", "142gh05m9a")
        stage_name: The stage name (e.g., "test", "prod", "dev")
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - api_id: REST API ID
        - stage_name: Stage name
        - deployment_id: Current deployment ID
        - xray_tracing_enabled: Whether X-Ray tracing is enabled
        - cache_cluster_enabled: Whether caching is enabled
        - cache_cluster_size: Cache cluster size if enabled
        - method_settings: Method-level settings and throttling
        - variables: Stage variables
        - integrations: Array of integration details:
          - resource_path: API resource path (e.g., "/users", "/orders")
          - http_method: HTTP method (GET, POST, PUT, DELETE, etc.)
          - integration_type: Type of integration (AWS_PROXY, AWS, HTTP, etc.)
          - integration_uri: Target service URI
          - target_service: Parsed target service (Lambda, Step Functions, HTTP)
          - credentials_role: IAM role used for integration
        - created_date: When the stage was created
        - last_updated_date: When the stage was last updated
    
    Common Integration Issues:
        - Wrong integration type: Mismatch between expected and actual integration
        - Missing IAM permissions: Integration role lacks required permissions
        - Incorrect URI: Integration points to wrong service or function
        - Missing credentials: Integration lacks proper IAM role
        - CORS issues: Missing or misconfigured CORS settings
        - Throttling: Method-level throttling causing 429 errors
    
    Use Cases:
        - Integration debugging (verify backend service connections)
        - Permission analysis (check IAM role configurations)
        - Routing issues (verify resource paths and methods)
        - Performance optimization (check caching and throttling settings)
        - Security auditing (review integration credentials and permissions)
        - CORS troubleshooting (verify cross-origin resource sharing setup)
    
    Note: This tool examines the current stage configuration, not historical changes.
    """
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('apigateway')

        # Get stage config
        stage_response = client.get_stage(
            restApiId=api_id,
            stageName=stage_name
        )

        # Get resources to find integrations
        resources_response = client.get_resources(restApiId=api_id)
        resources = resources_response.get('items', [])

        # Extract integration details for each resource/method
        integrations = []
        for resource in resources:
            resource_path = resource.get('path', '/')
            for method, method_config in resource.get('resourceMethods', {}).items():
                # Get integration for this method
                try:
                    integration_response = client.get_integration(
                        restApiId=api_id,
                        resourceId=resource['id'],
                        httpMethod=method
                    )

                    # Determine integration type
                    integration_type = integration_response.get('type', 'UNKNOWN')
                    uri = integration_response.get('uri', '')
                    credentials = integration_response.get('credentials', '')

                    # Parse integration target from URI
                    target_service = "unknown"
                    if 'lambda' in uri.lower():
                        target_service = "Lambda"
                    elif 'states:action/StartSyncExecution' in uri or 'states:action/StartExecution' in uri:
                        target_service = "Step Functions"
                    elif 'http://' in uri or 'https://' in uri:
                        target_service = "HTTP"

                    integrations.append({
                        "resource_path": resource_path,
                        "http_method": method,
                        "integration_type": integration_type,
                        "integration_uri": uri,
                        "target_service": target_service,
                        "credentials_role": credentials
                    })
                except Exception:
                    # Integration might not exist for this method (e.g., OPTIONS mock)
                    pass

        config = {
            "api_id": api_id,
            "stage_name": stage_response.get('stageName'),
            "deployment_id": stage_response.get('deploymentId'),
            "xray_tracing_enabled": stage_response.get('tracingEnabled', False),
            "cache_cluster_enabled": stage_response.get('cacheClusterEnabled', False),
            "cache_cluster_size": stage_response.get('cacheClusterSize'),
            "method_settings": stage_response.get('methodSettings', {}),
            "variables": stage_response.get('variables', {}),
            "integrations": integrations,  # NEW: Integration details showing what backends are used
            "created_date": str(stage_response.get('createdDate')),
            "last_updated_date": str(stage_response.get('lastUpdatedDate'))
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "api_id": api_id, "stage": stage_name})


@tool
def get_apigateway_logs(api_id: str, stage_name: str = "test", hours_back: int = 1) -> str:
    """
    Retrieve CloudWatch logs for API Gateway request/response analysis and error debugging.
    
    This tool fetches execution logs from API Gateway to identify request patterns,
    error responses, integration failures, and performance issues. Essential for
    diagnosing API Gateway routing, integration, and client-side problems.
    
    Args:
        api_id: The API Gateway REST API ID (e.g., "abc123xyz", "142gh05m9a")
        stage_name: The stage name (e.g., "test", "prod", "dev")
        hours_back: Number of hours to look back for logs (default: 1, max recommended: 24)
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - api_id: REST API ID
        - stage_name: Stage name
        - log_group: CloudWatch log group path
        - hours_back: Time range searched
        - event_count: Number of log events found
        - events: Array of log events with:
          - timestamp: Unix timestamp in milliseconds
          - message: Log message content (request/response details, errors)
    
    Common Log Patterns to Look For:
        - HTTP status codes: 4xx (client errors), 5xx (server errors)
        - Integration errors: Backend service failures or timeouts
        - Authentication errors: Invalid API keys or IAM permissions
        - Throttling: 429 Too Many Requests responses
        - CORS errors: Cross-origin request failures
        - Request validation: Malformed requests or missing parameters
        - Response transformation: Integration response mapping issues
    
    Use Cases:
        - Request/response debugging (analyze API call patterns)
        - Error investigation (identify 4xx/5xx error causes)
        - Integration troubleshooting (check backend service calls)
        - Performance analysis (analyze request latency and patterns)
        - Security auditing (review authentication and authorization)
        - Client debugging (help developers understand API behavior)
    
    Note: Logs are retrieved from the most recent log streams to ensure relevance.
    """
    
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('logs')
        
        # API Gateway log group format
        log_group = f"API-Gateway-Execution-Logs_{api_id}/{stage_name}"
        
        start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp() * 1000)
        end_time = int(datetime.now().timestamp() * 1000)
        
        # Get log streams
        streams_response = client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )
        
        log_events = []
        for stream in streams_response.get('logStreams', [])[:3]:  # Get events from top 3 streams
            events_response = client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream['logStreamName'],
                startTime=start_time,
                endTime=end_time,
                limit=20
            )
            log_events.extend(events_response.get('events', []))
        
        config = {
            "api_id": api_id,
            "stage_name": stage_name,
            "log_group": log_group,
            "hours_back": hours_back,
            "event_count": len(log_events),
            "events": [
                {
                    "timestamp": event.get('timestamp'),
                    "message": event.get('message')
                } for event in log_events[:20]  # Limit to 20 events
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "api_id": api_id, "stage_name": stage_name})


@tool
def resolve_api_gateway_id(resolve: str) -> str:
    """
    Resolve API Gateway name or ID to the actual REST API ID.
    Handles both cases:
    - If given a numeric ID (like "142gh05m9a"), returns it as-is
    - If given a name (like "promptrca-test-test-api"), looks it up and returns the ID

    Args:
        api_name_or_id: API Gateway name or ID

    Returns:
        JSON string with the REST API ID
    """
    import re

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        # Check if it's already a REST API ID format (alphanumeric, typically 10 chars)
        # REST API IDs look like: 142gh05m9a, abc123xyz, etc.
        if re.match(r'^[a-z0-9]{10}$', api_name_or_id):
            return json.dumps({
                "api_id": api_name_or_id,
                "source": "direct",
                "message": "Already a valid REST API ID"
            })

        # Otherwise, search for it by name
        client = aws_client.get_client('apigateway')

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
def get_api_gateway_access_logs_parsed(api_id: str, stage_name: str = "test", hours_back: int = 1, limit: int = 50) -> str:
    """
    Get parsed API Gateway access logs with structured request/response data.

    This tool uses CloudWatch Logs Insights to parse API Gateway access logs,
    extracting HTTP status codes, methods, paths, latencies, and error details.
    Essential for diagnosing request failures, integration issues, and performance problems.

    Args:
        api_id: The API Gateway REST API ID (e.g., "abc123xyz", "142gh05m9a")
        stage_name: The stage name (e.g., "test", "prod", "dev")
        hours_back: Number of hours to look back (default: 1)
        limit: Maximum number of requests to return (default: 50)

    Returns:
        JSON string containing:
        - api_id: REST API ID
        - stage_name: Stage name
        - hours_back: Time range searched
        - request_count: Total number of requests found
        - error_count: Number of failed requests (4xx/5xx)
        - requests: Array of parsed requests with:
          - timestamp: When the request occurred
          - method: HTTP method (GET, POST, PUT, DELETE, etc.)
          - path: API resource path
          - status_code: HTTP status code (200, 403, 502, etc.)
          - integration_status: Backend integration HTTP status
          - request_latency_ms: Total request latency
          - integration_latency_ms: Backend integration latency
          - error_message: Error message if available
          - request_id: AWS request ID for correlation
          - ip: Client IP address (if available)

    Common Error Analysis:
        - 4xx errors: Client-side errors (bad requests, auth failures, not found)
          - 400: Bad Request - malformed request
          - 403: Forbidden - auth/permission issue
          - 404: Not Found - wrong path or resource
          - 429: Too Many Requests - throttling
        - 5xx errors: Server-side errors (integration failures, timeouts)
          - 500: Internal Server Error - general backend error
          - 502: Bad Gateway - invalid response from integration
          - 503: Service Unavailable - integration unavailable
          - 504: Gateway Timeout - integration timed out

    Use Cases:
        - Error investigation (identify failing requests and status codes)
        - Integration troubleshooting (check backend integration status)
        - Performance analysis (analyze latency patterns)
        - Client debugging (understand request failures)
        - CORS troubleshooting (identify preflight failures)
        - Authentication debugging (track 403 errors)

    Note: This tool uses CloudWatch Logs Insights which may take several seconds to execute.
    Access logs must be enabled for the API Gateway stage.
    """
    from datetime import datetime, timedelta
    import time

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        logs_client = aws_client.get_client('logs')

        # API Gateway access log group format
        # Access logs use a custom log group specified in stage configuration
        # Try common patterns
        log_group_patterns = [
            f"API-Gateway-Access-Logs_{api_id}/{stage_name}",
            f"/aws/apigateway/{api_id}/{stage_name}",
            f"/aws/api-gateway/{api_id}/{stage_name}"
        ]

        # Try to find the log group
        log_group = None
        for pattern in log_group_patterns:
            try:
                logs_client.describe_log_streams(logGroupName=pattern, limit=1)
                log_group = pattern
                break
            except:
                continue

        if not log_group:
            # Fallback to execution logs
            log_group = f"API-Gateway-Execution-Logs_{api_id}/{stage_name}"

        # Calculate time range
        start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
        end_time = int(datetime.now().timestamp())

        # CloudWatch Logs Insights query to parse access logs
        # Access log format: $context.requestId $context.httpMethod $context.resourcePath $context.protocol $context.status $context.integrationStatus ...
        query = f"""
        fields @timestamp, @message
        | parse @message /(?<requestId>[A-Za-z0-9-]+)\\s+(?<method>[A-Z]+)\\s+(?<path>\\/[^\\s]*)\\s+(?<protocol>HTTP\\/[0-9.]+)\\s+(?<status>[0-9]+)\\s+(?<integrationStatus>[0-9-]+)\\s+(?<requestLatency>[0-9]+)\\s+(?<integrationLatency>[0-9]+)\\s+(?<responseLength>[0-9]+)/
        | filter @message like /.+/
        | sort @timestamp desc
        | limit {limit}
        """

        # Start the query
        query_response = logs_client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query
        )

        query_id = query_response['queryId']

        # Poll for query completion (max 30 seconds)
        max_attempts = 30
        for attempt in range(max_attempts):
            result_response = logs_client.get_query_results(queryId=query_id)
            status = result_response['status']

            if status == 'Complete':
                break
            elif status == 'Failed' or status == 'Cancelled':
                raise Exception(f"Query failed with status: {status}")

            time.sleep(1)

        # Parse results
        results = result_response.get('results', [])
        requests = []
        error_count = 0

        for result in results:
            # Convert list of field/value dicts to a simple dict
            fields = {field['field']: field.get('value', '') for field in result}

            timestamp = fields.get('@timestamp', '')
            message = fields.get('@message', '')
            request_id = fields.get('requestId', '')
            method = fields.get('method', '')
            path = fields.get('path', '')
            protocol = fields.get('protocol', '')
            status_code = fields.get('status', '')
            integration_status = fields.get('integrationStatus', '')
            request_latency = fields.get('requestLatency', '0')
            integration_latency = fields.get('integrationLatency', '0')
            response_length = fields.get('responseLength', '0')

            # Convert to integers if possible
            try:
                status_code_int = int(status_code) if status_code else 0
                if status_code_int >= 400:
                    error_count += 1
            except:
                status_code_int = 0

            # Determine error message based on status code
            error_message = None
            if status_code_int >= 500:
                error_message = "Server error (5xx) - integration or backend issue"
            elif status_code_int >= 400:
                error_message = "Client error (4xx) - bad request, auth, or not found"

            requests.append({
                "timestamp": timestamp,
                "request_id": request_id,
                "method": method,
                "path": path,
                "protocol": protocol,
                "status_code": status_code_int if status_code_int else status_code,
                "integration_status": integration_status,
                "request_latency_ms": int(request_latency) if request_latency and request_latency.isdigit() else None,
                "integration_latency_ms": int(integration_latency) if integration_latency and integration_latency.isdigit() else None,
                "response_length": int(response_length) if response_length and response_length.isdigit() else None,
                "error_message": error_message
            })

        config = {
            "api_id": api_id,
            "stage_name": stage_name,
            "log_group": log_group,
            "hours_back": hours_back,
            "request_count": len(requests),
            "error_count": error_count,
            "requests": requests,
            "query_status": status
        }

        return json.dumps(config, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "api_id": api_id,
            "stage_name": stage_name,
            "message": "Failed to parse access logs. Access logs may not be enabled or the log format may differ."
        })


@tool
def get_api_gateway_deployment_history(api_id: str, limit: int = 10) -> str:
    """
    Retrieve API Gateway deployment history to correlate API changes with incidents.

    This tool lists recent deployments for an API Gateway REST API, enabling temporal correlation
    between API changes and incidents. Critical for determining if an issue started after a
    deployment of new routes, integrations, or configurations.

    Use this tool when:
    - Investigating if an issue started after an API deployment
    - Correlating error timeline with API configuration changes
    - Analyzing deployment frequency and patterns
    - Checking what changed between working and failing states
    - Understanding the deployment history of an API
    - Identifying rollback candidates (previous working deployment)

    Args:
        api_id: The API Gateway REST API ID (e.g., "abc123xyz", "142gh05m9a")
        limit: Maximum number of deployments to return (default: 10, max: 25)

    Returns:
        JSON string containing:
        - api_id: REST API ID
        - deployment_count: Number of deployments found
        - deployments: Array of deployment details (newest first):
          - id: Deployment ID
          - created_date: ISO timestamp when this deployment was created
          - description: Deployment description if provided
          - api_stages: List of stages using this deployment
          - api_summary: Summary of API changes in this deployment

    Investigation Patterns:
        - Recent deployment correlation: Compare created_date with incident start time
        - Stage tracking: See which stages are using which deployments
        - Rapid deployments: Multiple deployments in short time may indicate troubleshooting
        - Deployment description: Look for clues about what changed
        - Rollback identification: Find last known good deployment before issues started

    Common Deployment Scenarios:
        - Issue started immediately after deployment: New integration or route has bug
        - Issue started hours after deployment: Gradual traffic shift or cache problem
        - Multiple rapid deployments: Team is trying to fix an issue
        - No recent deployments: Issue is environmental, not API-related
        - Stage-specific issue: Only one stage affected (check which deployment it's using)

    Investigation Workflow:
        1. List deployment history to see timeline
        2. Compare incident start time with recent deployment timestamps
        3. Identify which deployment each stage is currently using
        4. Check deployment descriptions for clues about changes
        5. Identify deployment deployed just before issue started
        6. Use get_api_gateway_stage_config to compare stage configurations

    Integration with Other Tools:
        - Use with get_api_gateway_stage_config to see current deployment details
        - Cross-reference timestamps with get_apigateway_logs for correlation
        - Compare with get_api_gateway_metrics to see performance before/after deployment
        - Validate against get_api_gateway_access_logs_parsed to confirm error timeline

    Example Use Cases:
        - "Did this error start after the latest deployment?" → Check if latest deployment timestamp matches error start time
        - "What changed in the last deployment?" → Use deployment ID to investigate stage config
        - "Which deployment should we roll back to?" → Find deployment before issues started
        - "How frequently is this API deployed?" → Analyze deployment creation patterns
        - "Which stage is using which deployment?" → Check api_stages for each deployment

    Note: Deployments are returned in reverse chronological order (newest first).
    A deployment must be associated with a stage to actually serve traffic.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('apigateway')

        # List deployments
        response = client.get_deployments(
            restApiId=api_id,
            limit=min(limit, 25)
        )

        deployments = response.get('items', [])
        deployment_details = []

        for deployment in deployments:
            deployment_details.append({
                "id": deployment.get('id'),
                "created_date": str(deployment.get('createdDate')),
                "description": deployment.get('description', ''),
                "api_summary": deployment.get('apiSummary', {})
            })

        # Get stages to see which deployment each uses
        stages_response = client.get_stages(restApiId=api_id)
        stages = stages_response.get('item', [])

        # Map stages to deployments
        deployment_to_stages = {}
        for stage in stages:
            deployment_id = stage.get('deploymentId')
            stage_name = stage.get('stageName')
            if deployment_id:
                if deployment_id not in deployment_to_stages:
                    deployment_to_stages[deployment_id] = []
                deployment_to_stages[deployment_id].append(stage_name)

        # Add stage info to deployments
        for deployment in deployment_details:
            deployment['api_stages'] = deployment_to_stages.get(deployment['id'], [])

        config = {
            "api_id": api_id,
            "deployment_count": len(deployment_details),
            "deployments": deployment_details
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "api_id": api_id
        })


@tool
def get_api_gateway_metrics(api_id: str, stage_name: str = "test", hours_back: int = 24) -> str:
    """
    Get CloudWatch metrics for an API Gateway.
    
    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        hours_back: Number of hours to look back (default: 24)
    
    Returns:
        JSON string with API Gateway metrics
    """
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('cloudwatch')
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common API Gateway metrics
        metric_names = [
            'Count', 'Latency', '4XXError', '5XXError', 'CacheHitCount', 'CacheMissCount'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/ApiGateway',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'ApiName',
                        'Value': api_id
                    },
                    {
                        'Name': 'Stage',
                        'Value': stage_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "api_id": api_id,
            "stage_name": stage_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "api_id": api_id, "stage_name": stage_name})
