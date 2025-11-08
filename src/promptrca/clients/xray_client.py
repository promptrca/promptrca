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
from botocore.exceptions import ClientError
from ..models import Fact
from ..utils import get_logger
from .base_client import BaseAWSClient

logger = get_logger(__name__)


class XRayClient(BaseAWSClient):
    """X-Ray-specific AWS client."""

    def __init__(self, region: str = "eu-west-1", session: Optional[boto3.Session] = None):
        """Initialize X-Ray client with optional shared session."""
        super().__init__(region, session=session)
        self._xray_client = self.get_client('xray')

    def get_xray_trace(self, trace_id: str) -> List[Fact]:
        """Get X-Ray trace information with detailed resource discovery."""
        facts = []
        
        try:
            response = self._xray_client.batch_get_traces(TraceIds=[trace_id])
            
            if response['Traces']:
                trace = response['Traces'][0]
                segments = trace['Segments']
                
                # Basic trace info
                facts.append(Fact(
                    source="xray",
                    content=f"X-Ray trace {trace_id} found with {len(segments)} segments",
                    confidence=1.0,
                    metadata={
                        "trace_id": trace_id,
                        "segment_count": len(segments),
                        "duration": trace.get('Duration', 0),
                        "is_partial": trace.get('IsPartial', False),
                        # Store detailed trace data for component detection
                        "trace_data": {
                            "segments": segments,
                            "duration": trace.get('Duration', 0),
                            "is_partial": trace.get('IsPartial', False)
                        }
                    }
                ))
                
                # Enhanced resource discovery from segments
                discovered_resources = self._extract_resources_from_segments(segments, trace_id)
                facts.extend(discovered_resources)
                
                # Analyze segments for errors
                error_segments = []
                for segment in trace['Segments']:
                    if segment.get('Error'):
                        error_segments.append(segment)
                
                if error_segments:
                    facts.append(Fact(
                        source="xray",
                        content=f"Trace contains {len(error_segments)} error segments",
                        confidence=0.9,
                        metadata={
                            "trace_id": trace_id,
                            "error_segment_count": len(error_segments)
                        }
                    ))
                    
                    # Get details of first error
                    first_error = error_segments[0]
                    facts.append(Fact(
                        source="xray",
                        content=f"Error in segment: {first_error.get('Error', 'Unknown error')}",
                        confidence=0.8,
                        metadata={
                            "trace_id": trace_id,
                            "error": first_error.get('Error'),
                            "error_throttle": first_error.get('ErrorThrottle', False),
                            "fault": first_error.get('Fault', False)
                        }
                    ))
                
                # Check for throttling
                throttled_segments = [seg for seg in trace['Segments'] if seg.get('Throttle')]
                if throttled_segments:
                    facts.append(Fact(
                        source="xray",
                        content=f"Trace contains {len(throttled_segments)} throttled segments",
                        confidence=0.9,
                        metadata={
                            "trace_id": trace_id,
                            "throttled_segment_count": len(throttled_segments)
                        }
                    ))
                
                # Check for faults
                fault_segments = [seg for seg in trace['Segments'] if seg.get('Fault')]
                if fault_segments:
                    facts.append(Fact(
                        source="xray",
                        content=f"Trace contains {len(fault_segments)} fault segments",
                        confidence=0.9,
                        metadata={
                            "trace_id": trace_id,
                            "fault_segment_count": len(fault_segments)
                        }
                    ))
                
                # Analyze duration
                duration = trace.get('Duration', 0)
                if duration > 0:
                    facts.append(Fact(
                        source="xray",
                        content=f"Trace duration: {duration:.2f} seconds",
                        confidence=0.8,
                        metadata={
                            "trace_id": trace_id,
                            "duration_seconds": duration
                        }
                    ))
            
            else:
                facts.append(Fact(
                    source="xray",
                    content=f"X-Ray trace {trace_id} not found",
                    confidence=1.0,
                    metadata={"trace_id": trace_id, "error": "not_found"}
                ))
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidRequestException':
                facts.append(Fact(
                    source="xray",
                    content=f"Invalid X-Ray trace ID: {trace_id}",
                    confidence=1.0,
                    metadata={"trace_id": trace_id, "error": "invalid_trace_id"}
                ))
            else:
                facts.append(Fact(
                    source="xray",
                    content=f"Failed to get X-Ray trace: {str(e)}",
                    confidence=0.0,
                    metadata={"error": str(e), "trace_id": trace_id}
                ))
        except Exception as e:
            facts.append(Fact(
                source="xray",
                content=f"Unexpected error getting X-Ray trace: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "trace_id": trace_id}
            ))
        
        return facts
    
    def _extract_resources_from_segments(self, segments: List[Dict[str, Any]], trace_id: str) -> List[Fact]:
        """Extract AWS resources from X-Ray segments for automatic discovery."""
        facts = []
        
        for segment in segments:
            segment_doc = segment.get('Document', {})
            
            # Handle case where Document might be a string (JSON)
            if isinstance(segment_doc, str):
                try:
                    import json
                    segment_doc = json.loads(segment_doc)
                except (json.JSONDecodeError, TypeError):
                    segment_doc = {}
            
            # Extract segment name from parsed document (it's usually in the document, not the segment)
            segment_name = segment_doc.get('name', segment.get('name', ''))
            
            # Extract service information
            service_info = self._extract_service_info(segment_name, segment_doc)
            if service_info:
                facts.append(Fact(
                    source="xray",
                    content=f"Discovered {service_info['type']}: {service_info['name']}",
                    confidence=0.9,
                    metadata={
                        "trace_id": trace_id,
                        "resource_type": service_info['type'],
                        "resource_name": service_info['name'],
                        "resource_arn": service_info.get('arn'),
                        "segment_name": segment_name,
                        "service_info": service_info
                    }
                ))
            
            # Extract downstream services
            downstream = segment_doc.get('downstream', [])
            if downstream and isinstance(downstream, list):
                for downstream_service in downstream:
                    if isinstance(downstream_service, dict):
                        downstream_info = self._extract_service_info(
                            downstream_service.get('name', ''),
                            downstream_service
                        )
                        if downstream_info:
                            facts.append(Fact(
                                source="xray",
                                content=f"Discovered downstream {downstream_info['type']}: {downstream_info['name']}",
                                confidence=0.8,
                                metadata={
                                    "trace_id": trace_id,
                                    "resource_type": downstream_info['type'],
                                    "resource_name": downstream_info['name'],
                                    "resource_arn": downstream_info.get('arn'),
                                    "relationship": "downstream",
                                    "parent_segment": segment_name
                                }
                            ))
        
        return facts
    
    def _extract_service_info(self, segment_name: str, segment_doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract service information from segment name and document."""
        if not segment_name:
            return None
        
        # Lambda function detection
        if 'lambda' in segment_name.lower():
            # Extract function name from ARN or name
            if 'arn:aws:lambda:' in segment_name:
                # Full ARN: arn:aws:lambda:region:account:function:name
                parts = segment_name.split(':')
                if len(parts) >= 7:
                    function_name = parts[6]
                    return {
                        'type': 'lambda',
                        'name': function_name,
                        'arn': segment_name,
                        'region': parts[3],
                        'account': parts[4]
                    }
            else:
                # Just function name
                return {
                    'type': 'lambda',
                    'name': segment_name,
                    'arn': None
                }
        
        # Step Functions detection
        elif 'states' in segment_name.lower() or 'stepfunctions' in segment_name.lower():
            if 'arn:aws:states:' in segment_name:
                # Full ARN: arn:aws:states:region:account:stateMachine:name
                parts = segment_name.split(':')
                if len(parts) >= 7:
                    state_machine_name = parts[6]
                    return {
                        'type': 'stepfunctions',
                        'name': state_machine_name,
                        'arn': segment_name,
                        'region': parts[3],
                        'account': parts[4]
                    }
            else:
                return {
                    'type': 'stepfunctions',
                    'name': segment_name,
                    'arn': None
                }
        
        # API Gateway detection
        elif 'apigateway' in segment_name.lower() or 'execute-api' in segment_name.lower() or '/' in segment_name:
            # Try to get REST API ID from AWS metadata first (most reliable)
            aws_metadata = segment_doc.get('aws', {})
            api_gateway_metadata = aws_metadata.get('api_gateway', {})
            rest_api_id = api_gateway_metadata.get('rest_api_id')
            stage_name = api_gateway_metadata.get('stage')

            if rest_api_id:
                # We have the actual REST API ID from metadata - use it!
                logger.info(f"Found API Gateway REST API ID from metadata: {rest_api_id}")
                return {
                    'type': 'apigateway',
                    'name': rest_api_id,  # This is the ACTUAL API ID
                    'arn': None,
                    'stage': stage_name or 'unknown',
                    'metadata': api_gateway_metadata
                }

            # Fallback: try to parse from segment name
            if 'arn:aws:execute-api:' in segment_name:
                # Full ARN: arn:aws:execute-api:region:account:api-id/stage/method/resource
                parts = segment_name.split(':')
                if len(parts) >= 6:
                    api_parts = parts[5].split('/')
                    if len(api_parts) >= 2:
                        api_id = api_parts[0]
                        return {
                            'type': 'apigateway',
                            'name': api_id,
                            'arn': segment_name,
                            'region': parts[3],
                            'account': parts[4],
                            'stage': api_parts[1] if len(api_parts) > 1 else None
                        }
            elif '/' in segment_name:
                # API Gateway format: api-id/stage/method/resource
                parts = segment_name.split('/')
                if len(parts) >= 2:
                    api_id = parts[0]
                    return {
                        'type': 'apigateway',
                        'name': api_id,
                        'arn': None,
                        'stage': parts[1] if len(parts) > 1 else None,
                        'resource_path': '/'.join(parts[2:]) if len(parts) > 2 else None
                    }
            else:
                return {
                    'type': 'apigateway',
                    'name': segment_name,
                    'arn': None
                }
        
        # DynamoDB detection
        elif 'dynamodb' in segment_name.lower():
            if 'arn:aws:dynamodb:' in segment_name:
                parts = segment_name.split(':')
                if len(parts) >= 6:
                    table_name = parts[5].split('/')[-1]
                    return {
                        'type': 'dynamodb',
                        'name': table_name,
                        'arn': segment_name,
                        'region': parts[3],
                        'account': parts[4]
                    }
            else:
                return {
                    'type': 'dynamodb',
                    'name': segment_name,
                    'arn': None
                }
        
        # S3 detection
        elif 's3' in segment_name.lower():
            if 'arn:aws:s3:::' in segment_name:
                bucket_name = segment_name.replace('arn:aws:s3:::', '')
                return {
                    'type': 's3',
                    'name': bucket_name,
                    'arn': segment_name
                }
            else:
                return {
                    'type': 's3',
                    'name': segment_name,
                    'arn': None
                }
        
        # SNS detection
        elif 'sns' in segment_name.lower():
            if 'arn:aws:sns:' in segment_name:
                parts = segment_name.split(':')
                if len(parts) >= 6:
                    topic_name = parts[5]
                    return {
                        'type': 'sns',
                        'name': topic_name,
                        'arn': segment_name,
                        'region': parts[3],
                        'account': parts[4]
                    }
            else:
                return {
                    'type': 'sns',
                    'name': segment_name,
                    'arn': None
                }
        
        # SQS detection
        elif 'sqs' in segment_name.lower():
            if 'arn:aws:sqs:' in segment_name:
                parts = segment_name.split(':')
                if len(parts) >= 6:
                    queue_name = parts[5]
                    return {
                        'type': 'sqs',
                        'name': queue_name,
                        'arn': segment_name,
                        'region': parts[3],
                        'account': parts[4]
                    }
            else:
                return {
                    'type': 'sqs',
                    'name': segment_name,
                    'arn': None
                }
        
        # Generic AWS service detection
        elif any(service in segment_name.lower() for service in ['aws.', 'amazonaws.com']):
            # Try to extract service name from domain
            if 'amazonaws.com' in segment_name:
                service_name = segment_name.split('.')[0]
                return {
                    'type': 'aws_service',
                    'name': service_name,
                    'arn': segment_name if 'arn:' in segment_name else None
                }

        return None

    def get_stepfunctions_execution_arn_from_trace(self, trace_id: str) -> Optional[str]:
        """Extract Step Functions execution ARN from an X-Ray trace.

        This looks for the execution ARN in the Step Functions subsegment metadata.
        """
        try:
            response = self._xray_client.batch_get_traces(TraceIds=[trace_id])

            if not response['Traces']:
                return None

            trace = response['Traces'][0]
            segments = trace['Segments']

            for segment in segments:
                segment_doc = segment.get('Document', {})

                # Handle case where Document might be a string (JSON)
                if isinstance(segment_doc, str):
                    try:
                        import json
                        segment_doc = json.loads(segment_doc)
                    except (json.JSONDecodeError, TypeError):
                        continue

                # Check if this is a Step Functions segment
                segment_name = segment_doc.get('name', '')
                origin = segment_doc.get('origin', '')

                if 'STEPFUNCTIONS' in segment_name or 'AWS::STEPFUNCTIONS' in origin:
                    # Check for execution ARN in AWS metadata
                    aws_metadata = segment_doc.get('aws', {})

                    # Execution ARN might be in various places
                    execution_arn = (
                        aws_metadata.get('execution_arn') or
                        aws_metadata.get('executionArn') or
                        segment_doc.get('execution_arn') or
                        segment_doc.get('executionArn')
                    )

                    if execution_arn:
                        logger.info(f"Found Step Functions execution ARN in trace: {execution_arn}")
                        return execution_arn

                    # If not directly available, try to extract from HTTP request URL
                    http_metadata = segment_doc.get('http', {})
                    request_metadata = http_metadata.get('request', {})
                    url = request_metadata.get('url', '')

                    # Look for execution ARN pattern in URL or response
                    if 'arn:aws:states:' in url:
                        # Try to extract ARN from URL
                        import re
                        arn_match = re.search(r'(arn:aws:states:[^:]+:[^:]+:execution:[^&\s]+)', url)
                        if arn_match:
                            execution_arn = arn_match.group(1)
                            logger.info(f"Extracted execution ARN from URL: {execution_arn}")
                            return execution_arn

                # Check subsegments for Step Functions calls
                subsegments = segment_doc.get('subsegments', [])
                for subsegment in subsegments:
                    subseg_name = subsegment.get('name', '')
                    if 'STEPFUNCTIONS' in subseg_name or 'states' in subseg_name.lower():
                        aws_metadata = subsegment.get('aws', {})
                        execution_arn = (
                            aws_metadata.get('execution_arn') or
                            aws_metadata.get('executionArn')
                        )
                        if execution_arn:
                            logger.info(f"Found execution ARN in subsegment: {execution_arn}")
                            return execution_arn

            return None

        except Exception as e:
            logger.error(f"Failed to extract Step Functions execution ARN from trace: {e}")
            return None
