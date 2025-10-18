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
    """
    Get API Gateway stage configuration including integration details (Lambda, Step Functions, etc.).

    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        region: AWS region (default: from environment)

    Returns:
        JSON string with stage configuration and integration details
    """
    region = region or get_region()
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
def get_iam_role_config(role_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get IAM role configuration including trust policy and attached policies.
    
    Args:
        role_name: The IAM role name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with role configuration
    """
    import boto3
    from urllib.parse import unquote
    
    try:
        client = boto3.client('iam', region_name=region)
        
        # Get role details
        role_response = client.get_role(RoleName=role_name)
        role = role_response['Role']
        
        # Get attached policies
        attached_policies_response = client.list_attached_role_policies(RoleName=role_name)
        attached_policies = attached_policies_response.get('AttachedPolicies', [])
        
        # Get inline policies
        inline_policies_response = client.list_role_policies(RoleName=role_name)
        inline_policy_names = inline_policies_response.get('PolicyNames', [])
        
        inline_policies = []
        for policy_name in inline_policy_names:
            policy_response = client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
            inline_policies.append({
                "policy_name": policy_name,
                "policy_document": policy_response.get('PolicyDocument')
            })
        
        config = {
            "role_name": role['RoleName'],
            "role_arn": role['Arn'],
            "assume_role_policy": role.get('AssumeRolePolicyDocument'),
            "attached_policies": [
                {
                    "policy_name": p['PolicyName'],
                    "policy_arn": p['PolicyArn']
                } for p in attached_policies
            ],
            "inline_policies": inline_policies,
            "created_date": str(role.get('CreateDate')),
            "max_session_duration": role.get('MaxSessionDuration')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "role_name": role_name})


@tool
def get_lambda_config(function_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get Lambda function configuration including environment variables and IAM role.
    
    Args:
        function_name: The Lambda function name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Lambda configuration
    """
    import boto3
    
    try:
        client = boto3.client('lambda', region_name=region)
        response = client.get_function_configuration(FunctionName=function_name)
        
        config = {
            "function_name": response.get('FunctionName'),
            "function_arn": response.get('FunctionArn'),
            "runtime": response.get('Runtime'),
            "role": response.get('Role'),
            "handler": response.get('Handler'),
            "timeout": response.get('Timeout'),
            "memory_size": response.get('MemorySize'),
            "environment_variables": response.get('Environment', {}).get('Variables', {}),
            "tracing_config": response.get('TracingConfig', {}),
            "layers": response.get('Layers', []),
            "last_modified": response.get('LastModified')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "function_name": function_name})


@tool
def get_stepfunctions_definition(state_machine_arn: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get Step Functions state machine definition.
    
    Args:
        state_machine_arn: The state machine ARN
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with state machine definition
    """
    import boto3
    
    try:
        client = boto3.client('stepfunctions', region_name=region)
        response = client.describe_state_machine(stateMachineArn=state_machine_arn)
        
        config = {
            "state_machine_arn": response.get('stateMachineArn'),
            "name": response.get('name'),
            "role_arn": response.get('roleArn'),
            "definition": json.loads(response.get('definition', '{}')),
            "type": response.get('type'),
            "creation_date": str(response.get('creationDate')),
            "logging_configuration": response.get('loggingConfiguration', {}),
            "tracing_configuration": response.get('tracingConfiguration', {})
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "state_machine_arn": state_machine_arn})


@tool
def get_xray_trace(trace_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get X-Ray trace details.
    
    Args:
        trace_id: The X-Ray trace ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with trace details
    """
    import boto3
    
    try:
        client = boto3.client('xray', region_name=region)
        response = client.batch_get_traces(TraceIds=[trace_id])
        
        if response.get('Traces'):
            trace = response['Traces'][0]
            config = {
                "trace_id": trace_id,
                "duration": trace.get('Duration'),
                "segments": trace.get('Segments', []),
                "is_partial": trace.get('IsPartial', False)
            }
            return json.dumps(config, indent=2)
        else:
            return json.dumps({"error": "Trace not found", "trace_id": trace_id})
    except Exception as e:
        return json.dumps({"error": str(e), "trace_id": trace_id})


@tool
def get_cloudwatch_logs(log_group: str, hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch logs for a log group.
    
    Args:
        log_group: The CloudWatch log group name
        hours_back: Number of hours to look back (default: 1)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with log events
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('logs', region_name=region)
        
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
        return json.dumps({"error": str(e), "log_group": log_group})


@tool
def get_lambda_logs(function_name: str, hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch logs for a Lambda function.
    
    Args:
        function_name: The Lambda function name
        hours_back: Number of hours to look back (default: 1)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Lambda log events
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('logs', region_name=region)
        
        # Lambda log group format
        log_group = f"/aws/lambda/{function_name}"
        
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
            "function_name": function_name,
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
        return json.dumps({"error": str(e), "function_name": function_name})


@tool
def get_apigateway_logs(api_id: str, stage_name: str = "test", hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch logs for an API Gateway.
    
    Args:
        api_id: The API Gateway REST API ID
        stage_name: The stage name (e.g., 'test', 'prod')
        hours_back: Number of hours to look back (default: 1)
        region: AWS region (default: from environment)
    
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
def get_stepfunctions_logs(state_machine_arn: str, hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch logs for a Step Functions state machine.
    
    Args:
        state_machine_arn: The Step Functions state machine ARN
        hours_back: Number of hours to look back (default: 1)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Step Functions log events
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('logs', region_name=region)
        
        # Extract state machine name from ARN
        state_machine_name = state_machine_arn.split(':')[-1]
        
        # Step Functions log group format
        log_group = f"/aws/stepfunctions/{state_machine_name}"
        
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
            "state_machine_arn": state_machine_arn,
            "state_machine_name": state_machine_name,
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
        return json.dumps({"error": str(e), "state_machine_arn": state_machine_arn})

