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
from typing import Dict, Any
import json


@tool
def get_api_gateway_stage_config(api_id: str, stage_name: str, region: str = "eu-west-1") -> str:
    """
    Get API Gateway stage configuration including integration details (Lambda, Step Functions, etc.).

    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        region: AWS region (default: eu-west-1)

    Returns:
        JSON string with stage configuration and integration details
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
def get_apigateway_logs(api_id: str, stage_name: str = "test", hours_back: int = 1, region: str = "eu-west-1") -> str:
    """
    Get CloudWatch logs for an API Gateway.
    
    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        hours_back: Number of hours to look back (default: 1)
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with API Gateway log events
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
def resolve_api_gateway_id(api_name_or_id: str, region: str = "eu-west-1") -> str:
    """
    Resolve API Gateway name or ID to the actual REST API ID.
    Handles both cases:
    - If given a numeric ID (like "142gh05m9a"), returns it as-is
    - If given a name (like "sherlock-test-test-api"), looks it up and returns the ID

    Args:
        api_name_or_id: API Gateway name or ID
        region: AWS region (default: eu-west-1)

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
def get_api_gateway_metrics(api_id: str, stage_name: str = "test", hours_back: int = 24, region: str = "eu-west-1") -> str:
    """
    Get CloudWatch metrics for an API Gateway.
    
    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: eu-west-1)
    
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
