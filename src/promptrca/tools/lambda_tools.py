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
def get_lambda_config(function_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get comprehensive Lambda function configuration for root cause analysis.
    
    This tool retrieves all critical configuration details needed to diagnose Lambda issues:
    - Runtime environment (Python version, Node.js version, etc.)
    - Resource allocation (memory, timeout settings)
    - IAM role and permissions
    - Environment variables and secrets
    - Layer dependencies
    - Tracing and monitoring configuration
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - function_name: Name of the function
        - function_arn: Full ARN of the function
        - runtime: Runtime version (e.g., "python3.12", "nodejs18.x")
        - role: IAM role ARN used by the function
        - handler: Entry point function (e.g., "index.handler")
        - timeout: Maximum execution time in seconds
        - memory_size: Allocated memory in MB
        - environment_variables: Key-value pairs of environment variables
        - tracing_config: X-Ray tracing configuration
        - layers: List of Lambda layers attached
        - last_modified: When the function was last updated
    
    Common Error Scenarios:
        - ResourceNotFoundException: Function doesn't exist
        - AccessDeniedException: Insufficient permissions to describe function
        - InvalidParameterValueException: Invalid function name format
    
    Use Cases:
        - Diagnosing timeout issues (check timeout vs actual execution time)
        - Memory-related problems (check allocated vs used memory)
        - Permission errors (verify IAM role configuration)
        - Runtime compatibility issues (check runtime version)
        - Environment variable problems (verify env vars are set correctly)
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
def get_lambda_logs(function_name: str, hours_back: int = 1, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve CloudWatch logs for Lambda function error analysis and debugging.
    
    This tool fetches recent log events from the Lambda function's CloudWatch log group
    to identify errors, exceptions, performance issues, and execution patterns.
    Essential for diagnosing runtime errors, timeout issues, and code problems.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        hours_back: Number of hours to look back for logs (default: 1, max recommended: 24)
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - function_name: Name of the function
        - log_group: CloudWatch log group path (e.g., "/aws/lambda/my-function")
        - hours_back: Time range searched
        - event_count: Number of log events found
        - events: Array of log events with:
          - timestamp: Unix timestamp in milliseconds
          - message: Log message content (may contain errors, stack traces, etc.)
    
    Common Error Patterns to Look For:
        - "Task timed out": Function exceeded timeout limit
        - "Memory limit exceeded": Function ran out of allocated memory
        - "AccessDenied": IAM permission issues
        - "ResourceNotFoundException": Missing AWS resources
        - "ValidationException": Invalid input parameters
        - Stack traces: Code errors and exceptions
        - "RequestId": Unique identifier for each invocation
    
    Use Cases:
        - Debugging runtime errors and exceptions
        - Analyzing timeout issues (check for "Task timed out" messages)
        - Memory problems (look for "Memory limit exceeded")
        - Permission errors (search for "AccessDenied" or "Forbidden")
        - Code bugs (examine stack traces and error messages)
        - Performance analysis (check execution patterns and timing)
    
    Note: Logs are retrieved from the most recent log streams to ensure relevance.
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
def get_lambda_metrics(function_name: str, hours_back: int = 24, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve CloudWatch metrics for Lambda function performance analysis.
    
    This tool fetches key performance metrics to identify patterns, bottlenecks,
    and issues with Lambda function execution. Critical for understanding
    invocation patterns, error rates, and resource utilization.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        hours_back: Number of hours to look back for metrics (default: 24)
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - function_name: Name of the function
        - time_range: Start/end times and duration of metrics collection
        - metrics: Dictionary with metric data:
          - Invocations: Total number of function invocations
          - Errors: Number of failed invocations
          - Duration: Execution time statistics (avg, max, sum)
          - Throttles: Number of throttled invocations
          - ConcurrentExecutions: Peak concurrent executions
          - UnreservedConcurrentExecutions: Available concurrency
    
    Key Metrics Analysis:
        - High Error Rate: Errors/Invocations > 5% indicates problems
        - Duration Spikes: Max duration approaching timeout suggests issues
        - Throttling: Throttles > 0 indicates concurrency limits exceeded
        - Low Invocations: May indicate upstream issues or misconfiguration
    
    Use Cases:
        - Performance monitoring and trend analysis
        - Error rate investigation (high error percentages)
        - Timeout analysis (duration vs configured timeout)
        - Throttling issues (concurrent execution limits)
        - Capacity planning (invocation patterns and scaling needs)
        - SLA monitoring (availability and performance metrics)
    
    Note: Metrics are aggregated in 1-hour periods for the specified time range.
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common Lambda metrics
        metric_names = [
            'Invocations', 'Errors', 'Duration', 'Throttles',
            'ConcurrentExecutions', 'UnreservedConcurrentExecutions'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'FunctionName',
                        'Value': function_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "function_name": function_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "function_name": function_name})


@tool
def get_lambda_layers(function_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve Lambda function layer information for dependency analysis.
    
    This tool examines the layers attached to a Lambda function to identify
    potential dependency issues, version conflicts, or missing runtime components.
    Essential for diagnosing import errors and runtime environment problems.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - function_name: Name of the function
        - layer_count: Number of layers attached
        - layers: Array of layer details:
          - arn: Full ARN of the layer
          - name: Layer name (extracted from ARN)
          - size: Layer size in bytes
    
    Common Layer Issues:
        - Missing layers: Function expects layers that aren't attached
        - Version conflicts: Multiple layers with conflicting versions
        - Size limits: Total layer size exceeds Lambda limits (250MB unzipped)
        - Runtime mismatch: Layers built for different runtime versions
        - Import errors: Code can't find modules provided by layers
    
    Use Cases:
        - Diagnosing import errors (missing dependencies in layers)
        - Runtime environment issues (checking layer compatibility)
        - Dependency conflicts (multiple versions of same library)
        - Performance analysis (layer size impact on cold starts)
        - Security auditing (checking layer sources and permissions)
    
    Note: Layer information is retrieved from the function configuration.
    """
    import boto3
    
    try:
        client = boto3.client('lambda', region_name=region)
        response = client.get_function_configuration(FunctionName=function_name)
        
        layers = response.get('Layers', [])
        layer_details = []
        
        for layer in layers:
            layer_arn = layer.get('Arn', '')
            layer_version = layer.get('CodeSize', 0)
            
            # Extract layer name from ARN
            layer_name = layer_arn.split(':')[-1] if layer_arn else 'unknown'
            
            layer_details.append({
                "arn": layer_arn,
                "name": layer_name,
                "size": layer_version
            })
        
        config = {
            "function_name": function_name,
            "layer_count": len(layers),
            "layers": layer_details
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "function_name": function_name})
