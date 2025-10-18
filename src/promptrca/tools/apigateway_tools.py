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

Contact: christiangenn99+promptrca@gmail.com

"""

from strands import tool
from typing import Dict, Any
import json
from ..utils.config import get_region


@tool
def get_api_gateway_stage_config(api_id: str, stage_name: str, region: str = None) -> str:
    region = region or get_region()
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
    import boto3

    try:
        client = boto3.client('apigateway', region_name=region)

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
def get_apigateway_logs(api_id: str, stage_name: str = "test", hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
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
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('logs', region_name=region)
        
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
def resolve_api_gateway_id(resolve: str, region: str = None) -> str:
    region = region or get_region()
    """
    Resolve API Gateway name or ID to the actual REST API ID.
    Handles both cases:
    - If given a numeric ID (like "142gh05m9a"), returns it as-is
    - If given a name (like "promptrca-test-test-api"), looks it up and returns the ID

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
def get_api_gateway_metrics(api_id: str, stage_name: str = "test", hours_back: int = 24, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch metrics for an API Gateway.
    
    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with API Gateway metrics
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
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
