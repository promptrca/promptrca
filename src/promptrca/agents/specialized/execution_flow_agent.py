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

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from ...models import Fact


class ExecutionFlowAgent:
    """Agent that analyzes execution flows to trace where failures occur."""
    
    def __init__(self, aws_client):
        """Initialize the execution flow agent."""
        self.aws_client = aws_client
    
    def analyze_execution_flow(self, investigation_target: Dict[str, Any]) -> List[Fact]:
        """Analyze the execution flow to trace where failures occur."""
        facts = []
        
        try:
            print(f"🌊 Debug: Analyzing execution flow for target: {investigation_target.get('type', 'unknown')}")
            
            # Extract flow components from investigation target
            flow_components = self._identify_flow_components(investigation_target)
            print(f"🌊 Debug: Identified {len(flow_components)} flow components")
            
            if not flow_components:
                facts.append(Fact(
                    source="execution_flow",
                    content="No execution flow components identified",
                    confidence=0.0,
                    metadata={"investigation_target": investigation_target}
                ))
                return facts
            
            # Trace the execution flow
            print(f"🌊 Debug: Tracing execution flow through {len(flow_components)} components")
            flow_trace = self._trace_execution_flow(flow_components)
            facts.extend(flow_trace)
            print(f"🌊 Debug: Generated {len(flow_trace)} flow trace facts")
            
            # Analyze failure points
            print(f"🌊 Debug: Analyzing failure points")
            failure_analysis = self._analyze_failure_points(flow_trace)
            facts.extend(failure_analysis)
            print(f"🌊 Debug: Generated {len(failure_analysis)} failure analysis facts")
            
            # Generate flow recommendations
            print(f"🌊 Debug: Generating flow recommendations")
            recommendations = self._generate_flow_recommendations(flow_trace, failure_analysis)
            facts.extend(recommendations)
            print(f"🌊 Debug: Generated {len(recommendations)} recommendation facts")
            
        except Exception as e:
            facts.append(Fact(
                source="execution_flow",
                content=f"Execution flow analysis failed: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "investigation_target": investigation_target}
            ))
        
        return facts
    
    def _identify_flow_components(self, investigation_target: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify components in the execution flow."""
        components = []
        
        # Start with the investigation target
        target_type = investigation_target.get('type', 'unknown')
        target_name = investigation_target.get('name', 'unknown')
        
        if target_type == 'stepfunctions':
            # For Step Functions, trace back to API Gateway and forward to Lambda
            components.extend([
                {
                    'type': 'apigateway',
                    'name': 'api-gateway-entry',
                    'role': 'entry_point',
                    'metadata': investigation_target.get('metadata', {})
                },
                {
                    'type': 'stepfunctions',
                    'name': target_name,
                    'role': 'orchestrator',
                    'metadata': investigation_target.get('metadata', {})
                },
                {
                    'type': 'lambda',
                    'name': 'target-lambda',
                    'role': 'executor',
                    'metadata': investigation_target.get('metadata', {})
                }
            ])
        elif target_type == 'lambda':
            # For Lambda, trace back to potential entry points
            components.extend([
                {
                    'type': 'lambda',
                    'name': target_name,
                    'role': 'executor',
                    'metadata': investigation_target.get('metadata', {})
                }
            ])
        
        return components
    
    def _trace_execution_flow(self, components: List[Dict[str, Any]]) -> List[Fact]:
        """Trace the execution flow through components."""
        facts = []
        
        try:
            # Create flow trace
            flow_trace = {
                'start_time': datetime.now(),
                'components': [],
                'transitions': [],
                'errors': []
            }
            
            for i, component in enumerate(components):
                component_status = self._analyze_component_status(component)
                flow_trace['components'].append({
                    'component': component,
                    'status': component_status,
                    'timestamp': datetime.now()
                })
                
                # Check for transitions between components
                if i > 0:
                    transition = self._analyze_transition(
                        flow_trace['components'][i-1], 
                        component_status
                    )
                    if transition:
                        flow_trace['transitions'].append(transition)
                
                # Generate facts for each component
                facts.append(Fact(
                    source="execution_flow",
                    content=f"Flow component {component['type']}:{component['name']} - {component_status['status']}",
                    confidence=0.9,
                    metadata={
                        'component_type': component['type'],
                        'component_name': component['name'],
                        'component_role': component['role'],
                        'status': component_status['status'],
                        'details': component_status.get('details', {})
                    }
                ))
            
            # Generate overall flow fact
            facts.append(Fact(
                source="execution_flow",
                content=f"Execution flow traced through {len(components)} components with {len(flow_trace['transitions'])} transitions",
                confidence=0.8,
                metadata={
                    'total_components': len(components),
                    'total_transitions': len(flow_trace['transitions']),
                    'flow_trace': flow_trace
                }
            ))
            
        except Exception as e:
            facts.append(Fact(
                source="execution_flow",
                content=f"Flow tracing failed: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
    
    def _analyze_component_status(self, component: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the status of a specific component."""
        component_type = component['type']
        component_name = component['name']
        
        try:
            if component_type == 'apigateway':
                return self._analyze_api_gateway_status(component_name)
            elif component_type == 'stepfunctions':
                return self._analyze_stepfunctions_status(component_name)
            elif component_type == 'lambda':
                return self._analyze_lambda_status(component_name)
            else:
                return {
                    'status': 'unknown',
                    'details': {'error': f'Unknown component type: {component_type}'}
                }
        except Exception as e:
            return {
                'status': 'error',
                'details': {'error': str(e)}
            }
    
    def _analyze_api_gateway_status(self, api_name: str) -> Dict[str, Any]:
        """Analyze API Gateway status."""
        try:
            # Get API Gateway info
            apis = self.aws_client._clients['apigateway'].get_rest_apis()
            api_info = None
            
            for api in apis.get('items', []):
                if api_name in api.get('name', '') or api_name == 'api-gateway-entry':
                    api_info = api
                    break
            
            if api_info:
                return {
                    'status': 'active',
                    'details': {
                        'api_id': api_info.get('id'),
                        'name': api_info.get('name'),
                        'created_date': api_info.get('createdDate')
                    }
                }
            else:
                return {
                    'status': 'not_found',
                    'details': {'error': f'API Gateway {api_name} not found'}
                }
        except Exception as e:
            return {
                'status': 'error',
                'details': {'error': str(e)}
            }
    
    def _analyze_stepfunctions_status(self, state_machine_name: str) -> Dict[str, Any]:
        """Analyze Step Functions status."""
        try:
            # Get state machine info
            state_machine_arn = f"arn:aws:states:{self.aws_client.region}:{self.aws_client.account_id}:stateMachine:{state_machine_name}"
            state_machine_info = self.aws_client._clients['stepfunctions'].describe_state_machine(
                stateMachineArn=state_machine_arn
            )
            
            # Get recent executions
            executions = self.aws_client.get_step_function_executions(state_machine_name)
            failed_executions = [ex for ex in executions if ex.get('status') == 'FAILED']
            
            return {
                'status': 'active' if state_machine_info.get('status') == 'ACTIVE' else 'inactive',
                'details': {
                    'state_machine_arn': state_machine_arn,
                    'status': state_machine_info.get('status'),
                    'role_arn': state_machine_info.get('roleArn'),
                    'total_executions': len(executions),
                    'failed_executions': len(failed_executions),
                    'recent_errors': [ex.get('error') for ex in failed_executions[:3]]
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'details': {'error': str(e)}
            }
    
    def _analyze_lambda_status(self, function_name: str) -> Dict[str, Any]:
        """Analyze Lambda function status."""
        try:
            # Get function info
            function_info = self.aws_client._clients['lambda'].get_function(
                FunctionName=function_name
            )
            
            # Get recent invocations and errors
            logs = self.aws_client.get_lambda_logs(function_name)
            error_events = [log for log in logs if 'ERROR' in log.get('message', '')]
            
            return {
                'status': 'active' if function_info['Configuration']['State'] == 'Active' else 'inactive',
                'details': {
                    'function_arn': function_info['Configuration']['FunctionArn'],
                    'runtime': function_info['Configuration']['Runtime'],
                    'memory': function_info['Configuration']['MemorySize'],
                    'timeout': function_info['Configuration']['Timeout'],
                    'role': function_info['Configuration']['Role'],
                    'recent_errors': len(error_events),
                    'last_modified': function_info['Configuration']['LastModified']
                }
            }
        except Exception as e:
            return {
                'status': 'error',
                'details': {'error': str(e)}
            }
    
    def _analyze_transition(self, from_component: Dict[str, Any], to_component: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Analyze transition between components."""
        from_status = from_component['status']['status']
        to_status = to_component['status']['status']
        
        # Check if there's a failure in the transition
        if from_status == 'active' and to_status == 'error':
            return {
                'from': from_component['component']['name'],
                'to': to_component['component']['name'],
                'status': 'failed',
                'error': to_component['status'].get('details', {}).get('error', 'Unknown error')
            }
        elif from_status == 'active' and to_status == 'active':
            return {
                'from': from_component['component']['name'],
                'to': to_component['component']['name'],
                'status': 'success'
            }
        
        return None
    
    def _analyze_failure_points(self, flow_trace: List[Fact]) -> List[Fact]:
        """Analyze failure points in the execution flow."""
        facts = []
        
        try:
            # Find components with errors
            error_components = []
            for fact in flow_trace:
                if fact.source == 'execution_flow' and 'error' in fact.metadata.get('details', {}):
                    error_components.append(fact)
            
            if error_components:
                facts.append(Fact(
                    source="execution_flow",
                    content=f"Found {len(error_components)} components with errors in execution flow",
                    confidence=0.9,
                    metadata={
                        'error_count': len(error_components),
                        'error_components': [comp.metadata for comp in error_components]
                    }
                ))
                
                # Analyze specific error patterns
                for error_comp in error_components:
                    error_details = error_comp.metadata.get('details', {})
                    error_msg = error_details.get('error', '')
                    
                    if 'not authorized' in error_msg.lower() or 'access denied' in error_msg.lower():
                        facts.append(Fact(
                            source="execution_flow",
                            content=f"IAM permission error detected in {error_comp.metadata['component_type']}:{error_comp.metadata['component_name']}",
                            confidence=0.95,
                            metadata={
                                'component_type': error_comp.metadata['component_type'],
                                'component_name': error_comp.metadata['component_name'],
                                'error_type': 'iam_permission',
                                'error_message': error_msg
                            }
                        ))
                    elif 'timeout' in error_msg.lower():
                        facts.append(Fact(
                            source="execution_flow",
                            content=f"Timeout error detected in {error_comp.metadata['component_type']}:{error_comp.metadata['component_name']}",
                            confidence=0.9,
                            metadata={
                                'component_type': error_comp.metadata['component_type'],
                                'component_name': error_comp.metadata['component_name'],
                                'error_type': 'timeout',
                                'error_message': error_msg
                            }
                        ))
            
        except Exception as e:
            facts.append(Fact(
                source="execution_flow",
                content=f"Failure point analysis failed: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
    
    def _generate_flow_recommendations(self, flow_trace: List[Fact], failure_analysis: List[Fact]) -> List[Fact]:
        """Generate recommendations based on flow analysis."""
        facts = []
        
        try:
            # Count different types of issues
            iam_issues = len([f for f in failure_analysis if f.metadata.get('error_type') == 'iam_permission'])
            timeout_issues = len([f for f in failure_analysis if f.metadata.get('error_type') == 'timeout'])
            
            if iam_issues > 0:
                facts.append(Fact(
                    source="execution_flow",
                    content=f"Recommendation: Check IAM permissions for {iam_issues} components with permission errors",
                    confidence=0.9,
                    metadata={
                        'recommendation_type': 'iam_permissions',
                        'issue_count': iam_issues,
                        'priority': 'high'
                    }
                ))
            
            if timeout_issues > 0:
                facts.append(Fact(
                    source="execution_flow",
                    content=f"Recommendation: Review timeout settings for {timeout_issues} components with timeout errors",
                    confidence=0.8,
                    metadata={
                        'recommendation_type': 'timeout_settings',
                        'issue_count': timeout_issues,
                        'priority': 'medium'
                    }
                ))
            
        except Exception as e:
            facts.append(Fact(
                source="execution_flow",
                content=f"Recommendation generation failed: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
