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

import boto3
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botocore.exceptions import ClientError
from ..models import Fact
from ..utils import get_logger
from .base_client import BaseAWSClient

logger = get_logger(__name__)


class LambdaClient(BaseAWSClient):
    """Lambda-specific AWS client."""

    def __init__(self, region: str = "eu-west-1", session: Optional[boto3.Session] = None):
        """Initialize Lambda client with optional shared session."""
        super().__init__(region, session=session)
        self._lambda_client = self.get_client('lambda')
        self._code_cache = {}  # Cache for Lambda function code

    def get_lambda_function_info(self, function_name: str) -> List[Fact]:
        """Get Lambda function information and configuration."""
        facts = []
        
        try:
            response = self._lambda_client.get_function(FunctionName=function_name)
            
            # Basic function info
            config = response['Configuration']
            facts.append(Fact(
                source="lambda",
                content=f"Lambda function '{function_name}' is {config['State']}",
                confidence=1.0,
                metadata={
                    "function_name": function_name,
                    "state": config['State'],
                    "runtime": config['Runtime'],
                    "handler": config['Handler'],
                    "memory_size": config['MemorySize'],
                    "timeout": config['Timeout'],
                    "last_modified": config['LastModified']
                }
            ))
            
            # Environment variables
            env_vars = config.get('Environment', {}).get('Variables', {})
            if env_vars:
                facts.append(Fact(
                    source="lambda",
                    content=f"Function has {len(env_vars)} environment variables",
                    confidence=0.9,
                    metadata={"env_var_count": len(env_vars), "function_name": function_name}
                ))
            
            # VPC configuration
            vpc_config = config.get('VpcConfig', {})
            if vpc_config.get('VpcId'):
                facts.append(Fact(
                    source="lambda",
                    content=f"Function is in VPC: {vpc_config['VpcId']}",
                    confidence=1.0,
                    metadata={"vpc_id": vpc_config['VpcId'], "function_name": function_name}
                ))
            
            # Dead letter queue
            if config.get('DeadLetterConfig', {}).get('TargetArn'):
                facts.append(Fact(
                    source="lambda",
                    content=f"Function has dead letter queue configured",
                    confidence=1.0,
                    metadata={"dlq_arn": config['DeadLetterConfig']['TargetArn'], "function_name": function_name}
                ))
            
            # Reserved concurrency
            if config.get('ReservedConcurrencyLimit'):
                facts.append(Fact(
                    source="lambda",
                    content=f"Function has reserved concurrency: {config['ReservedConcurrencyLimit']}",
                    confidence=1.0,
                    metadata={"reserved_concurrency": config['ReservedConcurrencyLimit'], "function_name": function_name}
                ))
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ResourceNotFoundException':
                facts.append(Fact(
                    source="lambda",
                    content=f"Lambda function '{function_name}' not found",
                    confidence=1.0,
                    metadata={"function_name": function_name, "error": "not_found"}
                ))
            else:
                facts.append(Fact(
                    source="lambda",
                    content=f"Failed to get Lambda function info: {str(e)}",
                    confidence=0.0,
                    metadata={"error": str(e), "function_name": function_name}
                ))
        except Exception as e:
            facts.append(Fact(
                source="lambda",
                content=f"Unexpected error getting Lambda function info: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts

    def get_lambda_function(self, function_name: str) -> Dict[str, Any]:
        """Get raw Lambda function data."""
        return self._lambda_client.get_function(FunctionName=function_name)

    def _analyze_source_code(self, source_code: str, function_name: str) -> List[Fact]:
        """Analyze Lambda function source code for potential issues."""
        facts = []
        
        try:
            # Check for common error patterns
            error_patterns = [
                ('division by zero', 'Division by zero error'),
                ('null pointer', 'Null pointer exception'),
                ('undefined', 'Undefined variable access'),
                ('timeout', 'Potential timeout issue'),
                ('memory', 'Memory-related issue'),
                ('permission', 'Permission-related issue'),
                ('network', 'Network-related issue'),
                ('database', 'Database-related issue')
            ]
            
            source_lower = source_code.lower()
            for pattern, description in error_patterns:
                if pattern in source_lower:
                    facts.append(Fact(
                        source="lambda_code_analysis",
                        content=f"Source code contains potential {description.lower()}",
                        confidence=0.7,
                        metadata={"pattern": pattern, "function_name": function_name}
                    ))
            
            # Check for error handling
            if 'try:' in source_code and 'except' in source_code:
                facts.append(Fact(
                    source="lambda_code_analysis",
                    content="Function has error handling (try/except blocks)",
                    confidence=0.8,
                    metadata={"function_name": function_name}
                ))
            else:
                facts.append(Fact(
                    source="lambda_code_analysis",
                    content="Function has no explicit error handling",
                    confidence=0.6,
                    metadata={"function_name": function_name}
                ))
            
            # Check for logging
            if 'print(' in source_code or 'logger' in source_code.lower():
                facts.append(Fact(
                    source="lambda_code_analysis",
                    content="Function has logging statements",
                    confidence=0.8,
                    metadata={"function_name": function_name}
                ))
            
        except Exception as e:
            facts.append(Fact(
                source="lambda_code_analysis",
                content=f"Could not analyze source code: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts

    def get_lambda_failed_invocations_detailed(self, function_name: str, hours_back: int = 24) -> List[Fact]:
        """Get detailed information about failed Lambda invocations."""
        facts = []
        
        try:
            # Get function configuration to understand timeout and memory
            function_config = self._lambda_client.get_function(FunctionName=function_name)
            timeout = function_config['Configuration']['Timeout']
            memory = function_config['Configuration']['MemorySize']
            
            # Get CloudWatch metrics for errors
            cloudwatch = self.get_client('cloudwatch')
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours_back)
            
            # Get error count
            error_response = cloudwatch.get_metric_statistics(
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
                    source="lambda_metrics",
                    content=f"Function had {int(total_errors)} errors in the last {hours_back} hours",
                    confidence=0.9,
                    metadata={
                        "function_name": function_name,
                        "error_count": int(total_errors),
                        "time_period_hours": hours_back
                    }
                ))
                
                # Get duration metrics to check for timeouts
                duration_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Duration',
                    Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Maximum']
                )
                
                if duration_response['Datapoints']:
                    max_duration = max(point['Maximum'] for point in duration_response['Datapoints'])
                    timeout_threshold = timeout * 1000  # Convert to milliseconds
                    
                    if max_duration > timeout_threshold * 0.9:  # 90% of timeout
                        facts.append(Fact(
                            source="lambda_metrics",
                            content=f"Function approaching timeout limit (max duration: {max_duration:.0f}ms, limit: {timeout_threshold}ms)",
                            confidence=0.8,
                            metadata={
                                "function_name": function_name,
                                "max_duration_ms": max_duration,
                                "timeout_limit_ms": timeout_threshold
                            }
                        ))
            
        except Exception as e:
            facts.append(Fact(
                source="lambda_metrics",
                content=f"Could not analyze Lambda metrics: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts

    def get_lambda_error_patterns(self, function_name: str, hours_back: int = 24) -> List[Fact]:
        """Analyze Lambda error patterns from CloudWatch logs."""
        facts = []
        
        try:
            # Get CloudWatch logs
            logs_client = self.get_client('logs')
            log_group_name = f"/aws/lambda/{function_name}"
            
            # Query logs for errors
            query = """
            fields @timestamp, @message
            | filter @message like /ERROR/ or @message like /Exception/ or @message like /Error/
            | sort @timestamp desc
            | limit 100
            """
            
            start_query_response = logs_client.start_query(
                logGroupName=log_group_name,
                startTime=int((datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp()),
                endTime=int(datetime.now(timezone.utc).timestamp()),
                queryString=query
            )
            
            query_id = start_query_response['queryId']
            
            # Wait for query to complete
            import time
            time.sleep(2)  # Wait 2 seconds for query to complete
            
            try:
                query_results = logs_client.get_query_results(queryId=query_id)
                
                if query_results['results']:
                    error_messages = [row[1]['value'] for row in query_results['results'] if len(row) > 1]
                    
                    # Analyze error patterns
                    error_patterns = {}
                    for error_msg in error_messages:
                        # Common error patterns
                        if 'timeout' in error_msg.lower():
                            error_patterns['timeout'] = error_patterns.get('timeout', 0) + 1
                        elif 'memory' in error_msg.lower():
                            error_patterns['memory'] = error_patterns.get('memory', 0) + 1
                        elif 'permission' in error_msg.lower() or 'access denied' in error_msg.lower():
                            error_patterns['permission'] = error_patterns.get('permission', 0) + 1
                        elif 'network' in error_msg.lower():
                            error_patterns['network'] = error_patterns.get('network', 0) + 1
                        else:
                            error_patterns['other'] = error_patterns.get('other', 0) + 1
                    
                    for pattern, count in error_patterns.items():
                        facts.append(Fact(
                            source="lambda_logs",
                            content=f"Error pattern '{pattern}': {count} occurrences",
                            confidence=0.8,
                            metadata={
                                "function_name": function_name,
                                "pattern": pattern,
                                "count": count,
                                "time_period_hours": hours_back
                            }
                        ))
                
            except Exception as e:
                facts.append(Fact(
                    source="lambda_logs",
                    content=f"Could not retrieve log query results: {str(e)}",
                    confidence=0.0,
                    metadata={"error": str(e), "function_name": function_name}
                ))
        
        except Exception as e:
            facts.append(Fact(
                source="lambda_logs",
                content=f"Could not analyze error patterns: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "function_name": function_name}
            ))
        
        return facts
