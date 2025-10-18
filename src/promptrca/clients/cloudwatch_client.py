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

import boto3
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botocore.exceptions import ClientError
from ..models import Fact
from ..utils import get_logger
from .base_client import BaseAWSClient

logger = get_logger(__name__)


class CloudWatchClient(BaseAWSClient):
    """CloudWatch-specific AWS client."""

    def __init__(self, region: str = "eu-west-1", session: Optional[boto3.Session] = None):
        """Initialize CloudWatch client with optional shared session."""
        super().__init__(region, session=session)
        self._cloudwatch_client = self.get_client('cloudwatch')
        self._logs_client = self.get_client('logs')

    def get_cloudwatch_metrics(self, function_name: str) -> List[Fact]:
        """Get CloudWatch metrics for a function."""
        facts = []
        
        try:
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=24)
            
            # Get error metrics
            error_response = self._cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum']
            )
            
            total_errors = sum(point['Sum'] for point in error_response['Datapoints'])
            
            if total_errors > 0:
                facts.append(Fact(
                    source="cloudwatch",
                    content=f"Function had {int(total_errors)} errors in the last 24 hours",
                    confidence=0.9,
                    metadata={
                        "function_name": function_name,
                        "error_count": int(total_errors),
                        "metric": "Errors"
                    }
                ))
            
            # Get duration metrics
            duration_response = self._cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Average', 'Maximum']
            )
            
            if duration_response['Datapoints']:
                avg_duration = sum(point['Average'] for point in duration_response['Datapoints']) / len(duration_response['Datapoints'])
                max_duration = max(point['Maximum'] for point in duration_response['Datapoints'])
                
                facts.append(Fact(
                    source="cloudwatch",
                    content=f"Function duration: avg {avg_duration:.0f}ms, max {max_duration:.0f}ms",
                    confidence=0.8,
                    metadata={
                        "function_name": function_name,
                        "avg_duration_ms": avg_duration,
                        "max_duration_ms": max_duration,
                        "metric": "Duration"
                    }
                ))
            
            # Get invocation metrics
            invocation_response = self._cloudwatch_client.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )
            
            total_invocations = sum(point['Sum'] for point in invocation_response['Datapoints'])
            
            if total_invocations > 0:
                facts.append(Fact(
                    source="cloudwatch",
                    content=f"Function had {int(total_invocations)} invocations in the last 24 hours",
                    confidence=0.9,
                    metadata={
                        "function_name": function_name,
                        "invocation_count": int(total_invocations),
                        "metric": "Invocations"
                    }
                ))
                
                # Calculate error rate
                if total_errors > 0:
                    error_rate = (total_errors / total_invocations) * 100
                    facts.append(Fact(
                        source="cloudwatch",
                        content=f"Function error rate: {error_rate:.1f}%",
                        confidence=0.9,
                        metadata={
                            "function_name": function_name,
                            "error_rate_percent": error_rate,
                            "error_count": int(total_errors),
                            "invocation_count": int(total_invocations)
                        }
                    ))
        
        except Exception as e:
            facts.append(Fact(
                source="cloudwatch",
                content=f"Could not get CloudWatch metrics: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts

    def get_cloudwatch_logs(self, function_name: str) -> List[Fact]:
        """Get CloudWatch logs for a function."""
        facts = []
        
        try:
            log_group_name = f"/aws/lambda/{function_name}"
            
            # Check if log group exists
            try:
                self._logs_client.describe_log_groups(logGroupNamePrefix=log_group_name)
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    facts.append(Fact(
                        source="cloudwatch_logs",
                        content=f"No CloudWatch log group found for function '{function_name}'",
                        confidence=1.0,
                        metadata={"function_name": function_name, "log_group": log_group_name}
                    ))
                    return facts
            
            # Get recent log streams
            response = self._logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=10
            )
            
            if response['logStreams']:
                facts.append(Fact(
                    source="cloudwatch_logs",
                    content=f"Found {len(response['logStreams'])} recent log streams",
                    confidence=0.9,
                    metadata={
                        "function_name": function_name,
                        "log_group": log_group_name,
                        "stream_count": len(response['logStreams'])
                    }
                ))
                
                # Get recent log events from the most recent stream
                latest_stream = response['logStreams'][0]
                events_response = self._logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=latest_stream['logStreamName'],
                    limit=50
                )
                
                if events_response['events']:
                    # Analyze log events for errors
                    error_events = [event for event in events_response['events'] 
                                  if 'ERROR' in event['message'] or 'Exception' in event['message']]
                    
                    if error_events:
                        facts.append(Fact(
                            source="cloudwatch_logs",
                            content=f"Found {len(error_events)} error events in recent logs",
                            confidence=0.9,
                            metadata={
                                "function_name": function_name,
                                "error_event_count": len(error_events),
                                "total_events": len(events_response['events'])
                            }
                        ))
                        
                        # Get the most recent error
                        latest_error = error_events[0]
                        facts.append(Fact(
                            source="cloudwatch_logs",
                            content=f"Latest error: {latest_error['message'][:200]}...",
                            confidence=0.8,
                            metadata={
                                "function_name": function_name,
                                "error_message": latest_error['message'],
                                "error_timestamp": latest_error['timestamp']
                            }
                        ))
                    else:
                        facts.append(Fact(
                            source="cloudwatch_logs",
                            content="No error events found in recent logs",
                            confidence=0.8,
                            metadata={
                                "function_name": function_name,
                                "total_events": len(events_response['events'])
                            }
                        ))
            else:
                facts.append(Fact(
                    source="cloudwatch_logs",
                    content=f"No log streams found for function '{function_name}'",
                    confidence=0.8,
                    metadata={"function_name": function_name, "log_group": log_group_name}
                ))
        
        except Exception as e:
            facts.append(Fact(
                source="cloudwatch_logs",
                content=f"Could not get CloudWatch logs: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts
