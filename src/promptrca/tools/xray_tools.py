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
def get_xray_trace(trace_id: str) -> str:
    """
    Get X-Ray trace details.
    
    Args:
        trace_id: The X-Ray trace ID
    
    Returns:
        JSON string with trace details
    """
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('xray')
        response = client.batch_get_traces(TraceIds=[trace_id])
        
        if response.get('Traces'):
            trace = response['Traces'][0]
            config = {
                "trace_id": trace_id,
                "duration": trace.get('Duration'),
                "segments": trace.get('Segments', []),
                "is_partial": trace.get('IsPartial', False)
            }
            return json.dumps(config, indent=2)
        else:
            return json.dumps({"error": "Trace not found", "trace_id": trace_id})
    except Exception as e:
        return json.dumps({"error": str(e), "trace_id": trace_id})


def _parse_arn(arn: str) -> dict:
    """
    Parse AWS ARN to extract service and resource information.
    
    ARN format: arn:partition:service:region:account-id:resource-type/resource-id
    """
    if not arn or not arn.startswith('arn:'):
        return {}
    
    try:
        parts = arn.split(':')
        if len(parts) < 6:
            return {}
        
        return {
            'partition': parts[1],
            'service': parts[2], 
            'region': parts[3],
            'account_id': parts[4],
            'resource': ':'.join(parts[5:])  # Resource part may contain colons
        }
    except:
        return {}


@tool
def get_all_resources_from_trace(trace_id: str) -> str:
    """
    Extract ALL AWS resources involved in an X-Ray trace.
    This discovers Lambda functions, Step Functions, API Gateways, and other services.

    Args:
        trace_id: The X-Ray trace ID

    Returns:
        JSON string with all discovered resources and their metadata
    """

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('xray')
        response = client.batch_get_traces(TraceIds=[trace_id])

        if not response.get('Traces'):
            return json.dumps({"error": "Trace not found", "trace_id": trace_id})

        trace = response['Traces'][0]
        segments = trace.get('Segments', [])

        resources = []
        discovered = set()  # Avoid duplicates

        for segment in segments:
            segment_doc = segment.get('Document', {})

            # Parse JSON if needed
            if isinstance(segment_doc, str):
                try:
                    segment_doc = json.loads(segment_doc)
                except:
                    continue

            segment_name = segment_doc.get('name', '')
            origin = segment_doc.get('origin', '')
            resource_arn = segment_doc.get('resource_arn')

            # Parse ARN if available for additional context
            arn_info = _parse_arn(resource_arn) if resource_arn else {}

            # Extract resource info
            resource = None

            # Lambda detection (from origin, segment name, or ARN)
            if ('AWS::Lambda' in origin or 
                'lambda' in segment_name.lower() or 
                arn_info.get('service') == 'lambda'):
                
                func_name = segment_name
                
                # Extract function name from ARN if available and more reliable
                if resource_arn and 'function:' in resource_arn:
                    func_name = resource_arn.split('function:')[-1]
                elif arn_info.get('resource', '').startswith('function/'):
                    func_name = arn_info['resource'].split('function/')[-1]
                
                if func_name and func_name not in discovered:
                    resource = {
                        "type": "lambda",
                        "name": func_name,
                        "arn": resource_arn,
                        "region": arn_info.get('region'),
                        "segment_id": segment.get('Id')
                    }
                    discovered.add(func_name)

            # Step Functions detection
            elif 'AWS::STEPFUNCTIONS' in origin or 'STEPFUNCTIONS' in segment_name:
                aws_metadata = segment_doc.get('aws', {})
                execution_arn = aws_metadata.get('execution_arn')
                if execution_arn and execution_arn not in discovered:
                    resource = {
                        "type": "stepfunctions",
                        "name": "STEPFUNCTIONS",
                        "execution_arn": execution_arn,
                        "segment_id": segment.get('Id')
                    }
                    discovered.add(execution_arn)

            # API Gateway detection
            elif 'AWS::ApiGateway' in origin or '/' in segment_name:
                api_id = None
                stage = 'unknown'
                resource_arn = segment_doc.get('resource_arn')
                
                # Try to extract from ARN first
                if resource_arn and '/restapis/' in resource_arn:
                    # arn:aws:apigateway:region::/restapis/api-id/stages/stage-name
                    arn_parts = resource_arn.split('/')
                    if len(arn_parts) >= 4:
                        api_id = arn_parts[2]  # restapis/API_ID/stages/STAGE
                        if len(arn_parts) >= 5:
                            stage = arn_parts[4]
                
                # Fallback to segment name parsing
                if not api_id and segment_name:
                    parts = segment_name.split('/')
                    if len(parts) >= 1:
                        api_id = parts[0]
                        stage = parts[1] if len(parts) > 1 else 'unknown'
                
                if api_id:
                    key = f"{api_id}:{stage}"
                    if key not in discovered:
                        resource = {
                            "type": "apigateway",
                            "name": api_id,
                            "stage": stage,
                            "arn": resource_arn,
                            "segment_id": segment.get('Id')
                        }
                        discovered.add(key)

            if resource:
                resources.append(resource)

        return json.dumps({
            "trace_id": trace_id,
            "duration": trace.get('Duration'),
            "is_partial": trace.get('IsPartial', False),
            "resource_count": len(resources),
            "resources": resources
        }, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "trace_id": trace_id})


@tool
def get_xray_service_graph(service_name: str = None, hours_back: int = 1) -> str:
    """
    Get X-Ray service graph showing service dependencies.
    
    Args:
        service_name: Optional service name to filter by
        hours_back: Number of hours to look back (default: 1)
    
    Returns:
        JSON string with service graph data
    """
    
    from datetime import datetime, timedelta
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('xray')
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        response = client.get_service_graph(
            StartTime=start_time,
            EndTime=end_time,
            GroupName=service_name
        )
        
        config = {
            "service_name": service_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "start_time": response.get('StartTime'),
            "end_time": response.get('EndTime'),
            "services": response.get('Services', []),
            "next_token": response.get('NextToken')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "service_name": service_name})


@tool
def get_xray_trace_summaries(start_time: str, end_time: str, filter_expression: str = None) -> str:
    """
    Get X-Ray trace summaries for a time range.
    
    Args:
        start_time: Start time in ISO format (e.g., "2024-01-01T00:00:00Z")
        end_time: End time in ISO format (e.g., "2024-01-01T23:59:59Z")
        filter_expression: Optional filter expression
    
    Returns:
        JSON string with trace summaries
    """
    
    from datetime import datetime

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('xray')
        
        # Convert ISO strings to datetime objects
        start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        kwargs = {
            'StartTime': start_dt,
            'EndTime': end_dt,
            'MaxResults': 100
        }
        
        if filter_expression:
            kwargs['FilterExpression'] = filter_expression
        
        response = client.get_trace_summaries(**kwargs)
        
        config = {
            "time_range": {
                "start": start_time,
                "end": end_time
            },
            "filter_expression": filter_expression,
            "trace_count": len(response.get('TraceSummaries', [])),
            "trace_summaries": response.get('TraceSummaries', []),
            "next_token": response.get('NextToken')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "start_time": start_time, "end_time": end_time})
