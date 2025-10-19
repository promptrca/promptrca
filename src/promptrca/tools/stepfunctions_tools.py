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
    Get detailed Step Functions execution information.
    
    Args:
        execution_arn: The execution ARN
    
    Returns:
        JSON string with execution details including history events
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
