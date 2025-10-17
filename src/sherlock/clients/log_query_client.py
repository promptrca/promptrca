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

import boto3
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from ..models import Fact
from ..utils import get_logger
from ..utils.config import get_region

logger = get_logger(__name__)


class LogQueryClient:
    """Client for querying CloudWatch Logs using Logs Insights."""

    def __init__(self, region: str = None, session: Optional[boto3.Session] = None):
        """
        Initialize the log query client with optional shared session.
        
        Args:
            region: AWS region
            session: Optional pre-created boto3 session. If not provided, creates a new one.
        """
        self.region = region or get_region()
        # Use provided session or create new one
        if session:
            self.logs_client = session.client('logs', region_name=self.region)
        else:
            import boto3
            self.logs_client = boto3.client('logs', region_name=self.region)

    def query_lambda_failed_invocations(
        self,
        function_name: str,
        hours_back: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query recent failed Lambda invocations with full context.

        Returns detailed invocation data including:
        - Request ID
        - Input payload (from START line)
        - Error message
        - Stack trace
        - Duration and memory usage
        """
        logger.info(f"🔍 Querying failed invocations for Lambda: {function_name}")
        logger.debug(f"   Parameters: hours_back={hours_back}, limit={limit}")

        log_group = f"/aws/lambda/{function_name}"

        # Query for failed invocations
        query = f"""
fields @timestamp, @message, @requestId, @duration, @billedDuration, @memorySize, @maxMemoryUsed
| filter @type = "REPORT" and ispresent(@requestId)
| sort @timestamp desc
| limit {limit}
        """

        logger.debug(f"   Log group: {log_group}")
        logger.debug(f"   Query: {query.strip()}")

        results = self._execute_query(log_group, query, hours_back)
        logger.info(f"📊 Query returned {len(results)} REPORT lines")

        # For each failed invocation, get full context
        invocations = []
        for idx, result in enumerate(results):
            request_id = self._get_field_value(result, '@requestId')
            logger.debug(f"   [{idx+1}/{len(results)}] Processing request ID: {request_id}")

            if request_id:
                # Get full invocation context
                logger.debug(f"      Getting full context for request {request_id}")
                context = self._get_invocation_context(log_group, request_id, hours_back)

                invocation_data = {
                    'request_id': request_id,
                    'timestamp': self._get_field_value(result, '@timestamp'),
                    'duration_ms': self._get_field_value(result, '@duration'),
                    'billed_duration_ms': self._get_field_value(result, '@billedDuration'),
                    'memory_size_mb': self._get_field_value(result, '@memorySize'),
                    'max_memory_used_mb': self._get_field_value(result, '@maxMemoryUsed'),
                    'input_payload': context.get('input'),
                    'error_message': context.get('error'),
                    'stack_trace': context.get('stack_trace'),
                    'logs': context.get('logs', [])
                }

                logger.debug(f"      ✅ Context retrieved: {len(context.get('logs', []))} log lines, "
                           f"error={'YES' if context.get('error') else 'NO'}, "
                           f"input={'YES' if context.get('input') else 'NO'}")

                invocations.append(invocation_data)

        logger.info(f"✅ Found {len(invocations)} failed invocations with full context")
        return invocations

    def query_lambda_errors_by_pattern(
        self,
        function_name: str,
        error_pattern: str,
        hours_back: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query Lambda errors matching a specific pattern.

        Args:
            function_name: Lambda function name
            error_pattern: Error pattern to search (e.g., "ZeroDivisionError", "timeout")
            hours_back: How many hours back to search
            limit: Maximum results to return
        """
        logger.info(f"Querying errors matching pattern '{error_pattern}' for {function_name}")

        log_group = f"/aws/lambda/{function_name}"

        query = f"""
fields @timestamp, @message, @requestId
| filter @message like /{error_pattern}/
| sort @timestamp desc
| limit {limit}
        """

        results = self._execute_query(log_group, query, hours_back)

        errors = []
        for result in results:
            errors.append({
                'timestamp': self._get_field_value(result, '@timestamp'),
                'message': self._get_field_value(result, '@message'),
                'request_id': self._get_field_value(result, '@requestId')
            })

        logger.info(f"Found {len(errors)} errors matching pattern")
        return errors

    def query_lambda_performance_issues(
        self,
        function_name: str,
        min_duration_ms: int = 1000,
        hours_back: int = 24,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Query Lambda invocations with performance issues (slow executions)."""
        logger.info(f"Querying slow invocations (>{min_duration_ms}ms) for {function_name}")

        log_group = f"/aws/lambda/{function_name}"

        query = f"""
fields @timestamp, @requestId, @duration, @maxMemoryUsed, @memorySize
| filter @type = "REPORT" and @duration > {min_duration_ms}
| sort @duration desc
| limit {limit}
        """

        results = self._execute_query(log_group, query, hours_back)

        slow_invocations = []
        for result in results:
            slow_invocations.append({
                'timestamp': self._get_field_value(result, '@timestamp'),
                'request_id': self._get_field_value(result, '@requestId'),
                'duration_ms': self._get_field_value(result, '@duration'),
                'max_memory_used_mb': self._get_field_value(result, '@maxMemoryUsed'),
                'memory_size_mb': self._get_field_value(result, '@memorySize')
            })

        logger.info(f"Found {len(slow_invocations)} slow invocations")
        return slow_invocations

    def query_step_functions_failed_executions(
        self,
        state_machine_name: str,
        hours_back: int = 24,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Query failed Step Functions executions from CloudWatch Logs."""
        logger.info(f"Querying failed executions for Step Functions: {state_machine_name}")

        # Step Functions logs to CloudWatch with pattern: /aws/vendedlogs/states/{state-machine-name}-Logs
        log_group = f"/aws/vendedlogs/states/{state_machine_name}-Logs"

        query = f"""
fields @timestamp, @message, execution_arn, type
| filter type = "ExecutionFailed" or type = "TaskFailed"
| sort @timestamp desc
| limit {limit}
        """

        try:
            results = self._execute_query(log_group, query, hours_back)

            failed_executions = []
            for result in results:
                failed_executions.append({
                    'timestamp': self._get_field_value(result, '@timestamp'),
                    'execution_arn': self._get_field_value(result, 'execution_arn'),
                    'type': self._get_field_value(result, 'type'),
                    'message': self._get_field_value(result, '@message')
                })

            logger.info(f"Found {len(failed_executions)} failed executions")
            return failed_executions

        except Exception as e:
            logger.warning(f"Step Functions log group not found or no logging enabled: {e}")
            return []

    def query_api_gateway_errors(
        self,
        api_id: str,
        stage: str,
        hours_back: int = 24,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Query API Gateway errors from access logs."""
        logger.info(f"Querying errors for API Gateway: {api_id}/{stage}")

        # API Gateway access logs pattern
        log_group = f"API-Gateway-Access-Logs_{api_id}/{stage}"

        query = f"""
fields @timestamp, requestId, status, ip, httpMethod, resourcePath, error.message
| filter status >= 400
| sort @timestamp desc
| limit {limit}
        """

        try:
            results = self._execute_query(log_group, query, hours_back)

            errors = []
            for result in results:
                errors.append({
                    'timestamp': self._get_field_value(result, '@timestamp'),
                    'request_id': self._get_field_value(result, 'requestId'),
                    'status': self._get_field_value(result, 'status'),
                    'method': self._get_field_value(result, 'httpMethod'),
                    'path': self._get_field_value(result, 'resourcePath'),
                    'ip': self._get_field_value(result, 'ip'),
                    'error': self._get_field_value(result, 'error.message')
                })

            logger.info(f"Found {len(errors)} API Gateway errors")
            return errors

        except Exception as e:
            logger.warning(f"API Gateway access logs not found or not enabled: {e}")
            return []

    def _execute_query(
        self,
        log_group: str,
        query: str,
        hours_back: int
    ) -> List[List[Dict[str, str]]]:
        """
        Execute a CloudWatch Logs Insights query.

        Returns:
            List of result rows, where each row is a list of field-value pairs
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours_back)

        logger.debug(f"⏰ Query time range: {start_time.isoformat()} to {end_time.isoformat()}")
        logger.debug(f"📁 Log group: {log_group}")

        try:

            # Start the query
            logger.debug("🚀 Starting CloudWatch Logs Insights query...")
            response = self.logs_client.start_query(
                logGroupName=log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )

            query_id = response['queryId']
            logger.info(f"📋 Query started with ID: {query_id}")

            # Wait for query to complete
            max_wait = 30  # seconds
            wait_interval = 0.5  # seconds
            elapsed = 0
            checks = 0

            while elapsed < max_wait:

                results = self.logs_client.get_query_results(queryId=query_id)
                status = results['status']
                checks += 1

                logger.debug(f"   Check {checks}: status={status}, elapsed={elapsed:.1f}s")

                if status == 'Complete':
                    result_count = len(results.get('results', []))
                    stats = results.get('statistics', {})
                    logger.info(f"✅ Query completed in {elapsed:.1f}s")
                    logger.info(f"   Results: {result_count} rows")
                    if stats:
                        logger.debug(f"   Stats: recordsMatched={stats.get('recordsMatched', 0)}, "
                                   f"recordsScanned={stats.get('recordsScanned', 0)}, "
                                   f"bytesScanned={stats.get('bytesScanned', 0)}")
                    return results.get('results', [])
                elif status == 'Failed':
                    error_msg = results.get('error', 'Unknown error')
                    logger.error(f"❌ Query failed: {error_msg}")
                    raise Exception(f"Query failed: {error_msg}")
                elif status == 'Cancelled':
                    logger.error("❌ Query was cancelled")
                    raise Exception("Query was cancelled")

                time.sleep(wait_interval)
                elapsed += wait_interval

            logger.error(f"⏱️ Query timed out after {max_wait} seconds")
            raise Exception(f"Query timed out after {max_wait} seconds")

        except self.logs_client.exceptions.ResourceNotFoundException:
            logger.warning(f"⚠️ Log group not found: {log_group}")
            return []
        except Exception as e:
            logger.error(f"❌ Query execution failed: {e}")
            raise

    def _get_invocation_context(
        self,
        log_group: str,
        request_id: str,
        hours_back: int
    ) -> Dict[str, Any]:
        """Get full context for a specific Lambda invocation."""
        logger.debug(f"🔎 Getting context for request ID: {request_id}")

        # Query for all logs related to this request ID
        query = f"""
fields @timestamp, @message
| filter @requestId = "{request_id}"
| sort @timestamp asc
        """

        results = self._execute_query(log_group, query, hours_back)
        logger.debug(f"   Retrieved {len(results)} log entries for request {request_id}")

        context = {
            'input': None,
            'error': None,
            'stack_trace': [],
            'logs': []
        }

        for result in results:
            message = self._get_field_value(result, '@message')

            if message:
                # Store all log messages
                context['logs'].append({
                    'timestamp': self._get_field_value(result, '@timestamp'),
                    'message': message
                })

                # Extract input from START line
                if message.startswith('START RequestId:'):
                    logger.debug(f"   Found START line")
                    # Sometimes input is logged separately, look for it
                    pass

                # Look for event processing logs (common pattern)
                if 'Processing event:' in message or 'event:' in message.lower():
                    logger.debug(f"   Found potential input in log: {message[:100]}...")
                    # Try to extract JSON from the message
                    try:
                        import json
                        import re
                        # Look for JSON in the message
                        json_match = re.search(r'\{.*\}', message)
                        if json_match:
                            context['input'] = json.loads(json_match.group())
                            logger.debug(f"   ✅ Extracted input payload")
                    except:
                        pass

                # Extract error information
                if 'ERROR' in message or 'Exception' in message or 'Error' in message:
                    if not context['error']:
                        context['error'] = message
                        logger.debug(f"   ❌ Found error: {message[:100]}...")
                    context['stack_trace'].append(message)

                # Look for Traceback
                if 'Traceback' in message or '  File ' in message:
                    context['stack_trace'].append(message)
                    logger.debug(f"   📚 Found stack trace line")

        logger.debug(f"   Context summary: logs={len(context['logs'])}, "
                   f"error={'YES' if context['error'] else 'NO'}, "
                   f"input={'YES' if context['input'] else 'NO'}, "
                   f"stack_trace={len(context['stack_trace'])} lines")

        return context

    def _get_field_value(self, result: List[Dict[str, str]], field_name: str) -> Optional[str]:
        """Extract a field value from a query result row."""
        for field in result:
            if field.get('field') == field_name:
                return field.get('value')
        return None
