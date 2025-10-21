#!/usr/bin/env python3
"""
Lambda Specialist for PromptRCA

Analyzes AWS Lambda functions for configuration issues, performance problems,
and execution failures.
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class LambdaSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS Lambda functions."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['lambda']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze Lambda function configuration, metrics, and recent failures."""
        facts = []
        function_name = resource.get('name')
        
        if not function_name:
            return facts
        
        self.logger.info(f"   → Analyzing Lambda function: {function_name}")
        
        # Get Lambda configuration
        facts.extend(await self._analyze_configuration(function_name))
        
        # Get Lambda metrics
        facts.extend(await self._analyze_metrics(function_name))
        
        # Get recent failed invocations
        facts.extend(await self._analyze_failed_invocations(function_name))
        
        return self._limit_facts(facts)
    
    async def _analyze_configuration(self, function_name: str) -> List[Fact]:
        """Analyze Lambda function configuration."""
        facts = []
        
        try:
            from ..tools.lambda_tools import get_lambda_config
            config_json = get_lambda_config(function_name)
            config = json.loads(config_json)
            
            if 'error' not in config:
                timeout = config.get('timeout')
                memory_size = config.get('memory_size')
                
                facts.append(self._create_fact(
                    source='lambda_config',
                    content=f"Lambda config loaded for {function_name}",
                    confidence=0.9,
                    metadata={
                        "timeout": timeout,
                        "memory_size": memory_size,
                        "function_name": function_name
                    }
                ))
                
                # Check for potential timeout issues
                if timeout and timeout <= 30:
                    facts.append(self._create_fact(
                        source='lambda_config',
                        content=f"Lambda function has short timeout: {timeout}s",
                        confidence=0.8,
                        metadata={
                            "timeout": timeout,
                            "function_name": function_name,
                            "potential_issue": "timeout"
                        }
                    ))
                    
        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for Lambda config analysis: {e}")
            else:
                self.logger.debug(f"Failed to get Lambda config for {function_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get Lambda config for {function_name}: {e}")
        
        return facts
    
    async def _analyze_metrics(self, function_name: str) -> List[Fact]:
        """Analyze Lambda function metrics."""
        facts = []
        
        try:
            from ..tools.lambda_tools import get_lambda_metrics
            metrics_json = get_lambda_metrics(function_name)
            metrics = json.loads(metrics_json)
            
            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})
                errors_count = len(metrics_data.get('Errors', []))
                invocations_count = len(metrics_data.get('Invocations', []))
                
                facts.append(self._create_fact(
                    source='lambda_metrics',
                    content=f"Metrics available for {function_name}",
                    confidence=0.8,
                    metadata={
                        "errors_points": errors_count,
                        "invocations_points": invocations_count,
                        "function_name": function_name
                    }
                ))
                
                # Check for high error rates
                if errors_count > 0 and invocations_count > 0:
                    error_rate = errors_count / invocations_count
                    if error_rate > 0.1:  # More than 10% error rate
                        facts.append(self._create_fact(
                            source='lambda_metrics',
                            content=f"High error rate detected for {function_name}: {error_rate:.1%}",
                            confidence=0.9,
                            metadata={
                                "error_rate": error_rate,
                                "function_name": function_name,
                                "issue_type": "high_error_rate"
                            }
                        ))
                        
        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for Lambda metrics analysis: {e}")
            else:
                self.logger.debug(f"Failed to get Lambda metrics for {function_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get Lambda metrics for {function_name}: {e}")
        
        return facts
    
    async def _analyze_failed_invocations(self, function_name: str) -> List[Fact]:
        """Analyze recent failed Lambda invocations."""
        facts = []
        
        try:
            from ..tools.lambda_tools import get_lambda_failed_invocations
            failures_json = get_lambda_failed_invocations(function_name, hours_back=24, limit=5)
            failures = json.loads(failures_json)
            
            if 'error' not in failures:
                failure_count = failures.get('failure_count', 0)
                
                if failure_count > 0:
                    facts.append(self._create_fact(
                        source='lambda_logs',
                        content=f"Found {failure_count} failed invocations",
                        confidence=0.85,
                        metadata={
                            "failed_invocations": failures.get('failed_invocations', []),
                            "failure_count": failure_count,
                            "function_name": function_name
                        }
                    ))
                    
                    # Analyze failure patterns
                    failed_invocations = failures.get('failed_invocations', [])
                    for failure in failed_invocations[:3]:  # Analyze top 3 failures
                        error_message = failure.get('message', '')
                        if 'timeout' in error_message.lower():
                            facts.append(self._create_fact(
                                source='lambda_logs',
                                content=f"Lambda function timeout detected: {error_message[:100]}...",
                                confidence=0.9,
                                metadata={
                                    "error_type": "timeout",
                                    "function_name": function_name,
                                    "error_message": error_message
                                }
                            ))
                        elif 'memory' in error_message.lower():
                            facts.append(self._create_fact(
                                source='lambda_logs',
                                content=f"Lambda memory issue detected: {error_message[:100]}...",
                                confidence=0.9,
                                metadata={
                                    "error_type": "memory",
                                    "function_name": function_name,
                                    "error_message": error_message
                                }
                            ))
                            
        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for Lambda failed invocations analysis: {e}")
            else:
                self.logger.debug(f"Failed to get Lambda failed invocations for {function_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get Lambda failed invocations for {function_name}: {e}")
        
        return facts