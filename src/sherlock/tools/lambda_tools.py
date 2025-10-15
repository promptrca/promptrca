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
from ..utils.config import get_region


@tool
def get_lambda_config(get: str, region: str = None) -> str:
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
def get_lambda_logs(get: str, region: str = None) -> str:
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
def get_lambda_metrics(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch metrics for a Lambda function.
    
    Args:
        function_name: The Lambda function name
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Lambda metrics
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
def get_lambda_layers(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get Lambda function layers information.
    
    Args:
        function_name: The Lambda function name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Lambda layers details
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
