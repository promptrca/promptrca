#!/usr/bin/env python3
"""
Trace Specialist for PromptRCA

Analyzes AWS X-Ray traces to extract service interactions, timing information,
and error patterns across distributed systems.

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

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class TraceSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS X-Ray traces."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['xray_trace']  # Special type for trace analysis
    
    async def analyze_trace(self, trace_id: str, context: InvestigationContext) -> List[Fact]:
        """
        Analyze a specific X-Ray trace for service interactions and errors.
        
        This is the main entry point for trace analysis, separate from the
        standard resource analysis interface.
        """
        facts = []
        
        self.logger.info(f"   → Analyzing trace {trace_id} deeply...")
        
        try:
            from ..tools.xray_tools import get_xray_trace, get_all_resources_from_trace
            self.logger.info(f"     → Getting trace data for {trace_id}...")

            trace_json = get_xray_trace(trace_id)
            self.logger.info(f"     → Trace JSON length: {len(trace_json) if trace_json else 0}")

            trace_data = json.loads(trace_json)
            self.logger.info(f"     → Parsed trace data keys: {list(trace_data.keys())}")

            if "error" in trace_data:
                self.logger.info(f"     → Error in trace data: {trace_data['error']}")
                facts.append(self._create_fact(
                    source='xray_trace',
                    content=f"Failed to retrieve trace {trace_id}: {trace_data['error']}",
                    confidence=0.9,
                    metadata={'trace_id': trace_id, 'error': True}
                ))
                return facts

            # Handle both AWS format (Traces key) and tool format (trace_id key)
            self.logger.info(f"     → Checking trace data format...")

            if "Traces" in trace_data and len(trace_data["Traces"]) > 0:
                # AWS batch_get_traces format
                self.logger.info(f"     → Found {len(trace_data['Traces'])} traces (AWS format)")
                trace = trace_data["Traces"][0]
                duration = trace.get('Duration', 0)
                segments = trace.get("Segments", [])
            elif "trace_id" in trace_data and "segments" in trace_data:
                # get_xray_trace tool format
                self.logger.info(f"     → Found trace data (tool format)")
                duration = trace_data.get('duration', 0)
                segments = trace_data.get("segments", [])
            else:
                self.logger.info(f"     → No valid trace data found")
                return facts

            # Add duration fact
            facts.append(self._create_fact(
                source='xray_trace',
                content=f"Trace {trace_id} duration: {duration:.3f}s",
                confidence=0.9,
                metadata={'trace_id': trace_id, 'duration': duration}
            ))
            self.logger.info(f"     → Added duration fact: {duration:.3f}s")

            # CRITICAL ENHANCEMENT: Extract resource identifiers from trace
            # This discovers Lambda functions, API Gateways, Step Functions, etc.
            self.logger.info(f"     → Extracting resources from trace {trace_id}...")
            try:
                resources_json = get_all_resources_from_trace(trace_id)
                resources_data = json.loads(resources_json)

                if "error" not in resources_data and "resources" in resources_data:
                    discovered_resources = resources_data.get("resources", [])
                    self.logger.info(f"     → Discovered {len(discovered_resources)} resources in trace")

                    # Add facts for each discovered resource with identifiers
                    for resource in discovered_resources:
                        resource_type = resource.get("type")
                        resource_name = resource.get("name")

                        if resource_type == "lambda":
                            lambda_arn = resource.get("arn")
                            facts.append(self._create_fact(
                                source='xray_trace_resource_discovery',
                                content=f"Discovered Lambda function: {resource_name}",
                                confidence=0.95,
                                metadata={
                                    'trace_id': trace_id,
                                    'resource_type': 'lambda',
                                    'function_name': resource_name,
                                    'function_arn': lambda_arn,
                                    'region': resource.get('region')
                                }
                            ))
                            self.logger.info(f"       • Lambda: {resource_name} (ARN: {lambda_arn})")

                        elif resource_type == "apigateway":
                            api_id = resource.get("name")
                            stage = resource.get("stage")
                            api_arn = resource.get("arn")
                            facts.append(self._create_fact(
                                source='xray_trace_resource_discovery',
                                content=f"Discovered API Gateway: {api_id} (stage: {stage})",
                                confidence=0.95,
                                metadata={
                                    'trace_id': trace_id,
                                    'resource_type': 'apigateway',
                                    'api_id': api_id,
                                    'stage': stage,
                                    'api_arn': api_arn
                                }
                            ))
                            self.logger.info(f"       • API Gateway: {api_id} stage={stage}")

                        elif resource_type == "stepfunctions":
                            execution_arn = resource.get("execution_arn")
                            facts.append(self._create_fact(
                                source='xray_trace_resource_discovery',
                                content=f"Discovered Step Functions execution",
                                confidence=0.95,
                                metadata={
                                    'trace_id': trace_id,
                                    'resource_type': 'stepfunctions',
                                    'execution_arn': execution_arn
                                }
                            ))
                            self.logger.info(f"       • Step Functions execution: {execution_arn}")

                else:
                    self.logger.info(f"     → No resources discovered in trace (may be minimal trace data)")

            except Exception as e:
                self.logger.warning(f"     → Failed to extract resources from trace: {e}")
                # Don't fail the entire analysis if resource extraction fails

            # Analyze segments for service interactions and errors
            facts.extend(self._analyze_segments(segments, trace_id))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for trace analysis: {e}")
                facts.append(self._create_fact(
                    source='xray_trace',
                    content=f"AWS client context not available for trace analysis",
                    confidence=0.9,
                    metadata={'trace_id': trace_id, 'error': 'aws_client_context_missing'}
                ))
            else:
                self.logger.error(f"Failed to analyze trace {trace_id}: {e}")
                facts.append(self._create_fact(
                    source='xray_trace',
                    content=f"Trace analysis failed for {trace_id}: {str(e)}",
                    confidence=0.8,
                    metadata={'trace_id': trace_id, 'error': True}
                ))
        except Exception as e:
            self.logger.error(f"Failed to analyze trace {trace_id}: {e}")
            self.logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
            facts.append(self._create_fact(
                source='xray_trace',
                content=f"Trace analysis failed for {trace_id}: {str(e)}",
                confidence=0.8,
                metadata={'trace_id': trace_id, 'error': True}
            ))

        self.logger.info(f"     → Returning {len(facts)} trace facts")
        return facts
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Standard interface - not used for trace analysis."""
        # Trace analysis uses analyze_trace method instead
        return []
    
    def _analyze_segments(self, segments: List[Dict[str, Any]], trace_id: str) -> List[Fact]:
        """Analyze trace segments for service interactions and errors."""
        facts = []
        error_segments = []
        fault_segments = []
        
        for segment_doc in segments:
            try:
                segment = json.loads(segment_doc["Document"])
                segment_name = segment.get('name', 'unknown')
                
                # Check for faults
                if segment.get('fault'):
                    fault_segments.append(segment_name)
                    
                # Check for errors
                if segment.get('error'):
                    error_segments.append(segment_name)
                    
                # Check HTTP status
                http_status = segment.get('http', {}).get('response', {}).get('status')
                if http_status and http_status >= 400:
                    facts.append(self._create_fact(
                        source='xray_trace',
                        content=f"Service {segment_name} returned HTTP {http_status}",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'service': segment_name, 'http_status': http_status}
                    ))
                
                # Check for cause/exception - KEY for permission errors
                if segment.get('cause'):
                    cause = segment.get('cause', {})
                    exception_id = cause.get('id')
                    message = cause.get('message', 'Unknown error')
                    facts.append(self._create_fact(
                        source='xray_trace',
                        content=f"Service {segment_name} error: {message}",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'service': segment_name, 'exception_id': exception_id, 'error_message': message}
                    ))
                    
                # Analyze subsegments for service interactions
                facts.extend(self._analyze_subsegments(segment, trace_id))
                            
            except Exception as e:
                self.logger.debug(f"Failed to parse segment: {e}")

        # Add summary facts
        if fault_segments:
            facts.append(self._create_fact(
                source='xray_trace',
                content=f"Faulted services in trace: {', '.join(fault_segments)}",
                confidence=0.95,
                metadata={'trace_id': trace_id, 'faulted_services': fault_segments}
            ))
        
        if error_segments:
            facts.append(self._create_fact(
                source='xray_trace',
                content=f"Services with errors in trace: {', '.join(error_segments)}",
                confidence=0.95,
                metadata={'trace_id': trace_id, 'error_services': error_segments}
            ))

        return facts
    
    def _analyze_subsegments(self, segment: Dict[str, Any], trace_id: str) -> List[Fact]:
        """Analyze subsegments for service-to-service interactions."""
        facts = []
        subsegments = segment.get('subsegments', [])
        
        # Extract AWS metadata from parent segment (like API Gateway role, account, etc.)
        aws_metadata = segment.get('aws', {})
        parent_account_id = aws_metadata.get('account_id')
        parent_resource_arn = segment.get('resource_arn')
        
        # Check for API Gateway metadata in parent segment
        if 'api_gateway' in aws_metadata or segment.get('origin') == 'AWS::ApiGateway::Stage':
            api_gateway_data = aws_metadata.get('api_gateway', {}) or segment.get('http', {})
            api_id = api_gateway_data.get('api_id') or api_gateway_data.get('request_id', '')
            
            if parent_account_id:
                # Construct likely execution role ARN for API Gateway
                # API Gateway typically uses a role named ApiGatewayExecutionRole or similar
                facts.append(self._create_fact(
                    source='xray_trace',
                    content=f"API Gateway in account {parent_account_id} made downstream calls",
                    confidence=0.9,
                    metadata={
                        'trace_id': trace_id,
                        'account_id': parent_account_id,
                        'api_id': api_id if api_id else 'unknown',
                        'requires_iam_check': True,
                        'resource_type': 'apigateway'
                    }
                ))
        
        for subsegment in subsegments:
            subsegment_name = subsegment.get('name', 'unknown')
            
            # Check for AWS service calls and extract actual findings
            http_req = subsegment.get('http', {}).get('request', {})
            http_url = http_req.get('url', '')
            
            # Extract AWS metadata from subsegment
            sub_aws_metadata = subsegment.get('aws', {})
            
            # Record service interaction (generic)
            if http_url:
                # Build metadata with AWS context
                call_metadata = {
                    'trace_id': trace_id, 
                    'subsegment': subsegment_name, 
                    'url': http_url
                }
                
                # Add AWS-specific metadata if available
                if sub_aws_metadata:
                    if 'account_id' in sub_aws_metadata:
                        call_metadata['account_id'] = sub_aws_metadata['account_id']
                    if 'operation' in sub_aws_metadata:
                        call_metadata['operation'] = sub_aws_metadata['operation']
                    if 'region' in sub_aws_metadata:
                        call_metadata['region'] = sub_aws_metadata['region']
                
                facts.append(self._create_fact(
                    source='xray_trace',
                    content=f"Service call to {subsegment_name}: {http_url}",
                    confidence=0.9,
                    metadata=call_metadata
                ))
                
                # Check response status
                sub_http_status = subsegment.get('http', {}).get('response', {}).get('status')
                if sub_http_status:
                    status_metadata = {
                        'trace_id': trace_id, 
                        'http_status': sub_http_status, 
                        'subsegment': subsegment_name
                    }
                    
                    # Flag potential IAM issues for AWS service integrations with HTTP 200
                    # This is common when API Gateway calls Step Functions/Lambda without proper permissions
                    if sub_http_status == 200 and ('states' in http_url.lower() or 'lambda' in http_url.lower()):
                        status_metadata['requires_iam_check'] = True
                        status_metadata['integration_type'] = 'aws_service'
                        if parent_account_id:
                            status_metadata['caller_account'] = parent_account_id
                    
                    facts.append(self._create_fact(
                        source='xray_trace',
                        content=f"{subsegment_name} returned HTTP {sub_http_status}",
                        confidence=0.9,
                        metadata=status_metadata
                    ))
            
            # Check for errors in subsegments
            if subsegment.get('fault') or subsegment.get('error'):
                if subsegment.get('cause'):
                    sub_cause = subsegment.get('cause', {})
                    sub_message = sub_cause.get('message', 'Unknown subsegment error')
                    
                    # Check for specific IAM/permission error patterns
                    is_permission_error = any(keyword in sub_message.lower() for keyword in [
                        'accessdenied', 'unauthorized', 'forbidden', 
                        'permission', 'not authorized', 'insufficient'
                    ])
                    
                    if is_permission_error:
                        facts.append(self._create_fact(
                            source='xray_trace',
                            content=f"IAM Permission Error in {subsegment_name}: {sub_message}",
                            confidence=0.98,
                            metadata={
                                'trace_id': trace_id,
                                'subsegment': subsegment_name,
                                'error_type': 'iam_permission',
                                'error_message': sub_message
                            }
                        ))
                    else:
                        facts.append(self._create_fact(
                            source='xray_trace',
                            content=f"Subsegment {subsegment_name} error: {sub_message}",
                            confidence=0.95,
                            metadata={'trace_id': trace_id, 'subsegment': subsegment_name, 'error_message': sub_message}
                        ))
        
        return facts