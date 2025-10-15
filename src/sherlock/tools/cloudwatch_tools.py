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
def get_cloudwatch_metrics(metric_name: str, hours_back: int = 24, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch metrics for a specific namespace and metric.
    
    Args:
        namespace: The CloudWatch namespace (e.g., "AWS/Lambda", "AWS/ApiGateway")
        metric_name: The metric name (e.g., "Invocations", "Errors")
        dimensions: List of dimension dictionaries (e.g., [{"Name": "FunctionName", "Value": "my-function"}])
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with metric data
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        kwargs = {
            'Namespace': namespace,
            'MetricName': metric_name,
            'StartTime': start_time,
            'EndTime': end_time,
            'Period': 3600,  # 1 hour periods
            'Statistics': ['Sum', 'Average', 'Maximum', 'Minimum']
        }
        
        if dimensions:
            kwargs['Dimensions'] = dimensions
        
        response = client.get_metric_statistics(**kwargs)
        
        config = {
            "namespace": namespace,
            "metric_name": metric_name,
            "dimensions": dimensions,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "datapoints": response.get('Datapoints', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "namespace": namespace, "metric_name": metric_name})


@tool
def get_cloudwatch_alarms(alarm_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch alarms and their status.
    
    Args:
        alarm_names: Optional list of alarm names to filter by
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with alarm information
    """
    import boto3
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        if alarm_names:
            response = client.describe_alarms(AlarmNames=alarm_names)
        else:
            response = client.describe_alarms()
        
        alarms = response.get('MetricAlarms', [])
        
        config = {
            "alarm_count": len(alarms),
            "alarms": [
                {
                    "alarm_name": alarm.get('AlarmName'),
                    "alarm_arn": alarm.get('AlarmArn'),
                    "state_value": alarm.get('StateValue'),
                    "state_reason": alarm.get('StateReason'),
                    "metric_name": alarm.get('MetricName'),
                    "namespace": alarm.get('Namespace'),
                    "threshold": alarm.get('Threshold'),
                    "comparison_operator": alarm.get('ComparisonOperator'),
                    "evaluation_periods": alarm.get('EvaluationPeriods'),
                    "period": alarm.get('Period'),
                    "statistic": alarm.get('Statistic')
                }
                for alarm in alarms
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "alarm_names": alarm_names})


@tool
def list_cloudwatch_dashboards(list: str, region: str = None) -> str:
    region = region or get_region()
    """
    List CloudWatch dashboards.
    
    Args:
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with dashboard information
    """
    import boto3
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        response = client.list_dashboards()
        dashboards = response.get('DashboardEntries', [])
        
        config = {
            "dashboard_count": len(dashboards),
            "dashboards": [
                {
                    "dashboard_name": dashboard.get('DashboardName'),
                    "last_modified": str(dashboard.get('LastModified')),
                    "size": dashboard.get('Size')
                }
                for dashboard in dashboards
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
