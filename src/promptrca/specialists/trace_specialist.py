#!/usr/bin/env python3
"""
Trace Specialist for PromptRCA

Analyzes AWS X-Ray traces to extract service interactions, timing information,
and error patterns across distributed systems.
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
            from ..tools.xray_tools import get_xray_trace
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
        
        for subsegment in subsegments:
            subsegment_name = subsegment.get('name', 'unknown')
            
            # Check for Step Functions calls specifically
            if subsegment_name == 'STEPFUNCTIONS':
                http_req = subsegment.get('http', {}).get('request', {})
                if 'StartSyncExecution' in http_req.get('url', ''):
                    facts.append(self._create_fact(
                        source='xray_trace',
                        content=f"API Gateway invoked Step Functions StartSyncExecution",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'service_call': 'stepfunctions', 'action': 'StartSyncExecution'}
                    ))
                    
                    # Check response status
                    sub_http_status = subsegment.get('http', {}).get('response', {}).get('status')
                    if sub_http_status:
                        facts.append(self._create_fact(
                            source='xray_trace',
                            content=f"Step Functions call returned HTTP {sub_http_status}",
                            confidence=0.9,
                            metadata={'trace_id': trace_id, 'http_status': sub_http_status}
                        ))
            
            # Check for errors in subsegments
            if subsegment.get('fault') or subsegment.get('error'):
                if subsegment.get('cause'):
                    sub_cause = subsegment.get('cause', {})
                    sub_message = sub_cause.get('message', 'Unknown subsegment error')
                    facts.append(self._create_fact(
                        source='xray_trace',
                        content=f"Subsegment {subsegment_name} error: {sub_message}",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'subsegment': subsegment_name, 'error_message': sub_message}
                    ))
        
        return facts