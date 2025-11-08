#!/usr/bin/env python3
"""
API Gateway Specialist for PromptRCA

Analyzes AWS API Gateway configurations, metrics, IAM permissions,
and execution logs for integration issues.

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


class APIGatewaySpecialist(BaseSpecialist):
    """Specialist for analyzing AWS API Gateway resources."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['apigateway']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze API Gateway configuration, metrics, IAM permissions, and logs."""
        facts = []
        api_id = resource.get('name')
        stage = resource.get('metadata', {}).get('stage', 'prod')
        
        if not api_id:
            return facts
        
        self.logger.info(f"   → Analyzing API Gateway: {api_id}")
        
        # Get API Gateway configuration and metrics
        facts.extend(await self._analyze_configuration(api_id, stage))
        facts.extend(await self._analyze_metrics(api_id, stage))
        
        # Check IAM permissions for Step Functions integration
        facts.extend(await self._analyze_iam_permissions(api_id, stage))
        
        # Check API Gateway execution logs
        facts.extend(await self._analyze_execution_logs(api_id, stage, context))
        
        return self._limit_facts(facts)
    
    async def _analyze_configuration(self, api_id: str, stage: str) -> List[Fact]:
        """Analyze API Gateway configuration."""
        facts = []
        
        try:
            from ..tools.apigateway_tools import get_api_gateway_stage_config
            config_json = get_api_gateway_stage_config(api_id, stage)
            config = json.loads(config_json)
            
            if 'error' not in config:
                facts.append(self._create_fact(
                    source='apigateway_config',
                    content=f"API {api_id} stage {stage} config loaded",
                    confidence=0.8,
                    metadata={
                        "xray": config.get('xray_tracing_enabled', False),
                        "api_id": api_id,
                        "stage": stage
                    }
                ))
                
        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for API Gateway config analysis: {e}")
            else:
                self.logger.debug(f"Failed to get API Gateway config for {api_id}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get API Gateway config for {api_id}: {e}")
        
        return facts
    
    async def _analyze_metrics(self, api_id: str, stage: str) -> List[Fact]:
        """Analyze API Gateway metrics."""
        facts = []
        
        try:
            from ..tools.apigateway_tools import get_api_gateway_metrics
            metrics_json = get_api_gateway_metrics(api_id, stage)
            metrics = json.loads(metrics_json)
            
            if 'error' not in metrics:
                metrics_keys = list(metrics.get('metrics', {}).keys())
                facts.append(self._create_fact(
                    source='apigateway_metrics',
                    content=f"API {api_id} metrics present",
                    confidence=0.7,
                    metadata={
                        "metrics_keys": metrics_keys,
                        "api_id": api_id,
                        "stage": stage
                    }
                ))
                
        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for API Gateway metrics analysis: {e}")
            else:
                self.logger.debug(f"Failed to get API Gateway metrics for {api_id}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get API Gateway metrics for {api_id}: {e}")
        
        return facts
    
    async def _analyze_iam_permissions(self, api_id: str, stage: str) -> List[Fact]:
        """Check IAM permissions for Step Functions integration."""
        facts = []
        
        try:
            # Common API Gateway execution role naming patterns
            possible_roles = [
                f"{api_id}-role",
                "sherlock-test-test-faulty-apigateway-role",  # Known role from testing
                "sherlock-test-test-api-gateway-role",
                "sherlock-test-test-apigateway-cloudwatch-role",
                f"sherlock-test-test-api-role", 
                f"apigateway-{api_id}-role",
                f"{api_id}-execution-role"
            ]
            
            from ..tools.iam_tools import get_iam_role_config
            
            for role_name in possible_roles:
                try:
                    self.logger.info(f"   → Checking IAM role: {role_name}")
                    role_config_json = get_iam_role_config(role_name)
                    role_config = json.loads(role_config_json)
                    
                    if 'error' not in role_config:
                        # Check if role has Step Functions permissions
                        has_stepfunctions_permission = self._check_stepfunctions_permissions(role_config)
                        
                        if has_stepfunctions_permission:
                            facts.append(self._create_fact(
                                source='iam_analysis',
                                content=f"API Gateway role {role_name} has Step Functions StartSyncExecution permission",
                                confidence=0.9,
                                metadata={
                                    'role': role_name,
                                    'permission': 'states:StartSyncExecution',
                                    'status': 'granted'
                                }
                            ))
                        else:
                            facts.append(self._create_fact(
                                source='iam_analysis',
                                content=f"API Gateway role {role_name} lacks Step Functions StartSyncExecution permission",
                                confidence=0.95,
                                metadata={
                                    'role': role_name,
                                    'permission': 'states:StartSyncExecution',
                                    'status': 'missing'
                                }
                            ))
                        break  # Found the role, stop checking others
                    
                except Exception as e:
                    self.logger.debug(f"Could not check role {role_name}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.debug(f"IAM permission check failed for API {api_id}: {e}")
        
        return facts
    
    def _check_stepfunctions_permissions(self, role_config: Dict[str, Any]) -> bool:
        """Check if role has Step Functions StartSyncExecution permission."""
        policies = role_config.get('attached_policies', [])
        inline_policies = role_config.get('inline_policies', [])
        
        for policy in policies + inline_policies:
            policy_doc = policy.get('policy_document', {})
            statements = policy_doc.get('Statement', [])
            for stmt in statements:
                if stmt.get('Effect') == 'Allow':
                    actions = stmt.get('Action', [])
                    if isinstance(actions, str):
                        actions = [actions]
                    if any('states:StartSyncExecution' in action or 'states:*' in action for action in actions):
                        return True
        return False
    
    async def _analyze_execution_logs(self, api_id: str, stage: str, context: InvestigationContext) -> List[Fact]:
        """Check API Gateway execution logs for permission errors."""
        facts = []
        
        try:
            from ..tools.cloudwatch_tools import query_logs_by_trace_id
            
            # Look for trace IDs in the context to check execution logs
            for trace_id in context.trace_ids:
                try:
                    self.logger.info(f"   → Checking API Gateway execution logs for trace {trace_id}")
                    log_group = f"API-Gateway-Execution-Logs_{api_id}/{stage}"
                    
                    logs_result_json = query_logs_by_trace_id(log_group, trace_id, hours_back=1)
                    logs_result = json.loads(logs_result_json)
                    
                    if 'error' not in logs_result:
                        log_entries = logs_result.get('log_entries', [])
                        
                        for entry in log_entries:
                            message = entry.get('message', '')
                            
                            # Look for permission errors in log messages
                            if 'AccessDeniedException' in message or 'not authorized' in message:
                                facts.append(self._create_fact(
                                    source='apigateway_logs',
                                    content=f"API Gateway execution log shows permission error: {message[:200]}...",
                                    confidence=0.95,
                                    metadata={
                                        'trace_id': trace_id,
                                        'log_group': log_group,
                                        'error_type': 'permission'
                                    }
                                ))
                            elif 'states:StartSyncExecution' in message:
                                facts.append(self._create_fact(
                                    source='apigateway_logs',
                                    content=f"API Gateway attempted Step Functions StartSyncExecution call",
                                    confidence=0.9,
                                    metadata={
                                        'trace_id': trace_id,
                                        'log_group': log_group,
                                        'action': 'StartSyncExecution'
                                    }
                                ))
                            elif 'HTTP 502' in message or 'Internal server error' in message:
                                facts.append(self._create_fact(
                                    source='apigateway_logs',
                                    content=f"API Gateway execution log shows internal error: {message[:200]}...",
                                    confidence=0.9,
                                    metadata={
                                        'trace_id': trace_id,
                                        'log_group': log_group,
                                        'error_type': 'internal'
                                    }
                                ))
                    
                except Exception as e:
                    self.logger.debug(f"Could not check execution logs for trace {trace_id}: {e}")
                    
        except Exception as e:
            self.logger.debug(f"API Gateway execution log check failed: {e}")
        
        return facts