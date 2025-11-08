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
def get_lambda_config(function_name: str) -> str:
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
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('lambda')
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
def get_lambda_logs(function_name: str, hours_back: int = 1) -> str:
    """
    Retrieve CloudWatch logs for Lambda function error analysis and debugging.
    
    This tool fetches recent log events from the Lambda function's CloudWatch log group
    to identify errors, exceptions, performance issues, and execution patterns.
    Essential for diagnosing runtime errors, timeout issues, and code problems.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        hours_back: Number of hours to look back for logs (default: 1, max recommended: 24)
    
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
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('logs')
        
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
def get_lambda_metrics(function_name: str, hours_back: int = 24) -> str:
    """
    Retrieve CloudWatch metrics for Lambda function performance analysis.
    
    This tool fetches key performance metrics to identify patterns, bottlenecks,
    and issues with Lambda function execution. Critical for understanding
    invocation patterns, error rates, and resource utilization.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        hours_back: Number of hours to look back for metrics (default: 24)
    
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
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('cloudwatch')
        
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
def get_lambda_failed_invocations(function_name: str, hours_back: int = 24, limit: int = 10) -> str:
    """
    Get recent FAILED Lambda invocations with detailed error information.

    This tool uses CloudWatch Logs Insights to query for failed invocations,
    extracting error messages, stack traces, request IDs, and timing information.
    Essential for diagnosing runtime errors, exceptions, and failure patterns.

    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        hours_back: Number of hours to look back (default: 24)
        limit: Maximum number of failed invocations to return (default: 10)

    Returns:
        JSON string containing:
        - function_name: Name of the function
        - hours_back: Time range searched
        - failure_count: Total number of failures found
        - failed_invocations: Array of failed invocations with:
          - timestamp: When the error occurred
          - request_id: AWS Request ID for correlation
          - error_type: Type of error (e.g., "ZeroDivisionError", "KeyError")
          - error_message: Detailed error message
          - stack_trace: Stack trace if available
          - duration_ms: Execution duration before failure
          - memory_used_mb: Memory used before failure

    Common Error Patterns:
        - Runtime exceptions: ZeroDivisionError, KeyError, AttributeError, etc.
        - Timeout errors: Task timed out after X seconds
        - Memory errors: Memory limit exceeded
        - Permission errors: AccessDenied, Forbidden
        - Integration errors: Failed to connect to downstream service

    Use Cases:
        - Debugging runtime errors (get exact error messages and stack traces)
        - Pattern analysis (identify recurring error types)
        - Input correlation (understand what inputs cause failures)
        - Performance diagnosis (check duration and memory before failure)
        - Error rate investigation (quantify failure frequency)

    Note: This tool uses CloudWatch Logs Insights which may take several seconds to execute.
    """
    from datetime import datetime, timedelta
    import time

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        logs_client = aws_client.get_client('logs')

        # Lambda log group format
        log_group = f"/aws/lambda/{function_name}"

        # Calculate time range
        start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
        end_time = int(datetime.now().timestamp())

        # CloudWatch Logs Insights query to find errors
        query = f"""
        fields @timestamp, @requestId, @message, @duration, @maxMemoryUsed
        | filter @message like /ERROR|Exception|Traceback|Task timed out|Memory limit exceeded/
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
        failed_invocations = []

        for result in results:
            # Convert list of field/value dicts to a simple dict
            fields = {field['field']: field.get('value', '') for field in result}

            timestamp = fields.get('@timestamp', '')
            request_id = fields.get('@requestId', '')
            message = fields.get('@message', '')
            duration_ms = fields.get('@duration', '0')
            memory_used_mb = fields.get('@maxMemoryUsed', '0')

            # Extract error type and message from log message
            error_type = "Unknown"
            error_message = message
            stack_trace = None

            # Try to extract error type from common patterns
            if "Error:" in message or "Exception:" in message:
                try:
                    # Extract error type (e.g., "ZeroDivisionError", "KeyError")
                    if ":" in message:
                        parts = message.split(":")
                        error_type = parts[0].strip().split()[-1]  # Get last word before colon
                        error_message = ":".join(parts[1:]).strip()
                except:
                    pass
            elif "Task timed out" in message:
                error_type = "Timeout"
                error_message = message
            elif "Memory limit exceeded" in message:
                error_type = "MemoryError"
                error_message = message

            # Check if there's a stack trace in the message
            if "Traceback" in message or "  File " in message:
                stack_trace = message

            failed_invocations.append({
                "timestamp": timestamp,
                "request_id": request_id,
                "error_type": error_type,
                "error_message": error_message[:500],  # Limit message length
                "stack_trace": stack_trace[:1000] if stack_trace else None,  # Limit stack trace
                "duration_ms": float(duration_ms) if duration_ms and duration_ms != '0' else None,
                "memory_used_mb": int(memory_used_mb) if memory_used_mb and memory_used_mb != '0' else None
            })

        config = {
            "function_name": function_name,
            "log_group": log_group,
            "hours_back": hours_back,
            "failure_count": len(failed_invocations),
            "failed_invocations": failed_invocations,
            "query_status": status
        }

        return json.dumps(config, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "function_name": function_name,
            "log_group": f"/aws/lambda/{function_name}"
        })


@tool
def get_lambda_version_history(function_name: str, limit: int = 10) -> str:
    """
    Retrieve Lambda function version history to correlate failures with deployments.

    This tool lists recent function versions to identify when code changes were deployed,
    enabling temporal correlation between deployments and incidents. Critical for determining
    if a failure started after a recent deployment or configuration change.

    Use this tool when:
    - Investigating if an issue started after a recent deployment
    - Correlating error timeline with code changes
    - Analyzing deployment frequency and patterns
    - Checking what changed between working and failing states
    - Understanding the deployment history of a function
    - Identifying rollback candidates (previous working version)

    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
        limit: Maximum number of versions to return (default: 10, max: 50)

    Returns:
        JSON string containing:
        - function_name: Name of the function
        - version_count: Number of versions found
        - versions: Array of version details (newest first):
          - version: Version number (e.g., "$LATEST", "1", "2", "3")
          - last_modified: ISO timestamp when this version was created
          - code_sha256: Hash of the deployment package (detects code changes)
          - runtime: Runtime version (e.g., "python3.12")
          - memory_size: Allocated memory in MB
          - timeout: Function timeout in seconds
          - environment_variables_hash: Hash of env vars (detects config changes)
          - description: Version description if provided

    Investigation Patterns:
        - Recent deployment correlation: Compare last_modified timestamps with incident start time
        - Code change detection: Different code_sha256 between versions indicates new code
        - Configuration drift: Changed memory_size, timeout, or runtime between versions
        - Rapid deployments: Multiple versions in short time may indicate troubleshooting attempts
        - Rollback identification: Find last known good version before issues started

    Common Deployment Scenarios:
        - Issue started immediately after deployment: New version has bug
        - Issue started hours after deployment: Cold start or gradual traffic shift problem
        - Multiple rapid deployments: Team is trying to fix an issue
        - No recent deployments: Issue is environmental, not code-related
        - Config-only change: Same code_sha256 but different memory/timeout

    Investigation Workflow:
        1. List version history to see deployment timeline
        2. Compare incident start time with recent version timestamps
        3. Check code_sha256 to confirm code actually changed
        4. Review configuration changes (memory, timeout, env vars)
        5. Identify version deployed just before issue started
        6. Use that version number to get full configuration for comparison

    Integration with Other Tools:
        - Use with get_lambda_config to get full details of specific version
        - Cross-reference timestamps with get_lambda_logs for correlation
        - Compare with get_lambda_metrics to see performance before/after deployment
        - Validate against get_lambda_failed_invocations to confirm error timeline

    Example Use Cases:
        - "Did this error start after the latest deployment?" → Check if latest version timestamp matches error start time
        - "What changed in the last deployment?" → Compare code_sha256 and config between versions
        - "Which version should we roll back to?" → Find version before issues started
        - "How frequently is this function deployed?" → Analyze version creation patterns
        - "Was this a code change or config change?" → Compare code_sha256 between versions

    Note: Versions are returned in reverse chronological order (newest first).
    The $LATEST version represents the current editable version.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('lambda')

        # List versions (newest first)
        response = client.list_versions_by_function(
            FunctionName=function_name,
            MaxItems=min(limit, 50)
        )

        versions = response.get('Versions', [])
        version_details = []

        for version in versions:
            # Create a hash of environment variables to detect config changes
            env_vars = version.get('Environment', {}).get('Variables', {})
            import hashlib
            env_hash = hashlib.md5(json.dumps(env_vars, sort_keys=True).encode()).hexdigest()[:8]

            version_details.append({
                "version": version.get('Version'),
                "last_modified": version.get('LastModified'),
                "code_sha256": version.get('CodeSha256'),
                "runtime": version.get('Runtime'),
                "memory_size": version.get('MemorySize'),
                "timeout": version.get('Timeout'),
                "environment_variables_hash": env_hash,
                "description": version.get('Description', '')
            })

        config = {
            "function_name": function_name,
            "version_count": len(version_details),
            "versions": version_details
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "function_name": function_name
        })


@tool
def get_lambda_layers(function_name: str) -> str:
    """
    Retrieve Lambda function layer information for dependency analysis.
    
    This tool examines the layers attached to a Lambda function to identify
    potential dependency issues, version conflicts, or missing runtime components.
    Essential for diagnosing import errors and runtime environment problems.
    
    Args:
        function_name: The Lambda function name (e.g., "my-function", "prod-api-handler")
    
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
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('lambda')
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
