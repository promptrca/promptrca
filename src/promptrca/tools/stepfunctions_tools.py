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
from typing import Dict, Any, Optional
import json
from ..context import get_aws_client


@tool
def get_stepfunctions_definition(state_machine_arn: str) -> str:
    """
    Get Step Functions state machine definition.
    
    Args:
        state_machine_arn: The state machine ARN
    
    Returns:
        JSON string with state machine definition
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('stepfunctions')
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
def get_stepfunctions_logs(state_machine_arn: str, hours_back: int = 1) -> str:
    """
    Get Step Functions execution logs for debugging and analysis.
    
    Args:
        state_machine_arn: The state machine ARN
        hours_back: Number of hours to look back for logs (default: 1)
    
    Returns:
        JSON string with execution logs
    """
    
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        client = aws_client.get_client('logs')
        
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


@tool
def get_stepfunctions_execution_details(execution_arn: str) -> str:
    """
    Retrieve comprehensive Step Functions execution details for failure analysis and debugging.

    This tool fetches complete execution information including which state failed, error messages,
    input/output data, and the full execution timeline. Essential for investigating Step Functions
    execution failures, state transition errors, and workflow issues.

    Use this tool when:
    - Investigating a specific failed Step Functions execution
    - Need to identify which state in the workflow failed
    - Want to see the exact error message and cause
    - Need to understand the execution timeline and state transitions
    - Analyzing input/output data that caused failures
    - Debugging state machine logic errors

    Args:
        execution_arn: The Step Functions execution ARN (e.g., "arn:aws:states:us-east-1:123456789012:execution:MyStateMachine:execution-name")

    Returns:
        JSON string containing:
        - execution_arn: The execution ARN
        - state_machine_arn: Parent state machine ARN
        - status: Execution status (RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED)
        - start_date: When execution started
        - stop_date: When execution ended (if completed)
        - input: Input JSON passed to execution
        - output: Output JSON (if successful)
        - error: Error code if failed (e.g., "States.TaskFailed", "States.Timeout")
        - cause: Detailed error cause/message
        - trace_header: X-Ray trace header for correlation
        - history_events: Array of execution history events showing:
          - State transitions (which states executed in order)
          - Failed states with error details
          - Task inputs and outputs
          - Retry attempts
          - Time spent in each state

    Common Error Patterns:
        - States.TaskFailed: Lambda function or integrated service returned error
        - States.Timeout: State execution exceeded timeout setting
        - States.Permissions: IAM role lacks permissions for state's task
        - States.Runtime: Invalid state machine definition or runtime error
        - States.DataLimitExceeded: Input/output data exceeds size limits

    Investigation Workflow:
        1. Check execution status to confirm failure
        2. Review error and cause for immediate issue
        3. Examine history_events to find failed state
        4. Look at failed state's input to understand what triggered error
        5. Check if error is consistent (use list_recent_executions to see pattern)
        6. Verify IAM permissions if States.Permissions error
        7. Check integrated service (Lambda, DynamoDB, etc.) if States.TaskFailed

    Example Use Cases:
        - Failed execution: See which state failed and why
        - Timeout issues: Find which state timed out and typical duration
        - Permission errors: Identify which AWS service call was denied
        - Data issues: Review input that caused validation errors
        - Logic errors: Trace state transitions to find incorrect flow
        - Integration failures: See which Lambda/API call failed

    Note: History events are limited to most recent 20 for performance. For full history, check CloudWatch Logs.
    """
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('stepfunctions')

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
def get_stepfunctions_metrics(state_machine_arn: str, hours_back: int = 24) -> str:
    """
    Get Step Functions metrics and performance data.
    
    Args:
        state_machine_arn: The state machine ARN
        hours_back: Number of hours to look back for metrics (default: 24)
    
    Returns:
        JSON string with metrics data
    """
    
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('cloudwatch')
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Extract state machine name from ARN
        state_machine_name = state_machine_arn.split(':')[-1]
        
        metrics = {}
        
        # Common Step Functions metrics
        metric_names = [
            'ExecutionsStarted', 'ExecutionsSucceeded', 'ExecutionsFailed', 
            'ExecutionsTimedOut', 'ExecutionsAborted', 'ExecutionTime'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/States',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'StateMachineArn',
                        'Value': state_machine_arn
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "state_machine_arn": state_machine_arn,
            "state_machine_name": state_machine_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "state_machine_arn": state_machine_arn})


@tool
def list_recent_stepfunctions_executions(state_machine_arn: str, status_filter: str = "FAILED", limit: int = 10) -> str:
    """
    List recent Step Functions executions to identify failure patterns and trends.

    This tool retrieves recent executions for a state machine, filtered by status, to help identify
    recurring failures, pattern analysis, and historical context. Essential for understanding if
    a failure is isolated or part of a larger pattern.

    Use this tool when:
    - Investigating if a failure is a one-time issue or recurring pattern
    - Looking for similar past failures to understand root cause
    - Analyzing failure frequency and trends over time
    - Finding other failed executions with same error pattern
    - Checking if all executions are failing or only some
    - Correlating failures with deployments or changes

    Args:
        state_machine_arn: The state machine ARN (e.g., "arn:aws:states:us-east-1:123456789012:stateMachine:MyStateMachine")
        status_filter: Filter by execution status - "RUNNING", "SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED" (default: "FAILED")
        limit: Maximum number of executions to return (default: 10, max: 100)

    Returns:
        JSON string containing:
        - state_machine_arn: The state machine ARN
        - status_filter: The status filter applied
        - execution_count: Number of executions found
        - executions: Array of execution summaries with:
          - execution_arn: ARN of the execution
          - name: Execution name
          - status: Execution status
          - start_date: When execution started
          - stop_date: When execution ended (if completed)

    Investigation Patterns:
        - All recent executions failing: Likely state machine configuration issue or IAM problem
        - Intermittent failures: May be input-dependent or downstream service issue
        - Failures started at specific time: Correlate with deployments/changes
        - Same error across executions: Systematic issue (config, permissions, logic)
        - Different errors: Input-dependent or environmental issues

    Common Patterns Found:
        - 100% failure rate: State machine definition error or IAM issue
        - 50% failure rate: Input validation or conditional logic issue
        - Increasing failure rate: Downstream service degradation
        - Failures after deployment: New code or configuration issue
        - Timeout pattern: Performance degradation or resource constraints

    Investigation Workflow:
        1. List recent FAILED executions to see failure frequency
        2. Compare with SUCCEEDED executions to see success rate
        3. Check if failures started at specific time (deployment correlation)
        4. Use execution ARNs to get details of failed executions
        5. Look for common error patterns across failures
        6. Cross-reference with recent state machine or IAM changes

    Example Use Cases:
        - Pattern detection: "Are all executions failing or just some?"
        - Timeline analysis: "When did failures start?"
        - Success rate calculation: Compare FAILED vs SUCCEEDED counts
        - Error correlation: Get multiple failed execution ARNs for detailed analysis
        - Deployment impact: Check if failures started after recent deployment

    Note: Results are sorted by start time (most recent first). Use execution ARN from results
    with get_stepfunctions_execution_details for detailed failure analysis.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('stepfunctions')

        # List executions with filter
        response = client.list_executions(
            stateMachineArn=state_machine_arn,
            statusFilter=status_filter,
            maxResults=min(limit, 100)  # AWS API max is 1000, we limit to 100 for performance
        )

        executions = response.get('executions', [])

        config = {
            "state_machine_arn": state_machine_arn,
            "status_filter": status_filter,
            "execution_count": len(executions),
            "executions": [
                {
                    "execution_arn": exec.get('executionArn'),
                    "name": exec.get('name'),
                    "status": exec.get('status'),
                    "start_date": str(exec.get('startDate')),
                    "stop_date": str(exec.get('stopDate')) if exec.get('stopDate') else None
                }
                for exec in executions
            ]
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({
            "error": str(e),
            "error_type": type(e).__name__,
            "state_machine_arn": state_machine_arn,
            "status_filter": status_filter
        })
