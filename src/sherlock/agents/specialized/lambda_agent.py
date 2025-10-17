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

from typing import List, Dict, Any
from strands import Agent
from ...models import Fact
from ...tools.aws_tools import (
    get_lambda_config, 
    get_cloudwatch_logs, 
    get_iam_role_config
)


def create_lambda_agent(model) -> Agent:
    """Create a Lambda specialist agent with tools."""
    
    system_prompt = """You are a Lambda specialist. Analyze ONLY tool outputs.

TOOLS:
- get_lambda_config(function_name, region?) → memory, timeout, runtime, IAM role
- get_cloudwatch_logs(log_group, region?) → recent logs, errors, exceptions
- get_iam_role_config(role_name, region?) → attached policies, permissions

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

CRITICAL RULES:
- Call each tool ONCE
- Extract facts: memory allocation, timeout setting, runtime version, error messages from logs
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  - Exception/stack trace in logs → code_bug
  - "PermissionDenied" → permission_issue
  - Execution time > configured timeout → timeout
  - Memory usage > allocated → resource_constraint
- NO speculation beyond tool outputs"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_lambda_config, get_cloudwatch_logs, get_iam_role_config]
    )


def create_lambda_agent_tool(lambda_agent: Agent):
    """Create a tool that wraps the Lambda agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_lambda_function(function_name: str, investigation_context: str = "") -> str:
        """
        Investigate a Lambda function for issues and problems.
        
        Args:
            function_name: The Lambda function name to investigate
            investigation_context: Additional context about the investigation (e.g., error messages, trace IDs)
        
        Returns:
            JSON string with investigation results and findings
        """
        import json
        
        try:
            # Create investigation prompt
            prompt = f"""Investigate Lambda function: {function_name}
            
Context: {investigation_context}

Please analyze this Lambda function for any issues, errors, or problems. Start by getting the function configuration, then check logs for errors, and examine IAM permissions if needed."""

            # Run the agent
            agent_result = lambda_agent(prompt)
            
            # Record token usage
            from ...utils.token_tracker import get_current_tracker, extract_model_id_from_bedrock_model
            token_tracker = get_current_tracker()
            if token_tracker and hasattr(agent_result, 'metrics'):
                model_id = extract_model_id_from_bedrock_model(lambda_agent.model)
                token_tracker.record_agent_invocation("lambda_agent", model_id, agent_result.metrics)
            
            # Extract the response content from AgentResult
            response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

            # Attempt to parse structured JSON from response
            def _extract_json(s: str):
                try:
                    import json as _json
                    text = s.strip()
                    if "```" in text:
                        if "```json" in text:
                            text = text.split("```json", 1)[1].split("```", 1)[0]
                        else:
                            text = text.split("```", 1)[1].split("```", 1)[0]
                    return _json.loads(text)
                except Exception:
                    return None

            data = _extract_json(response) or {}
            # Basic validation and normalization
            if isinstance(data.get("facts"), dict) or isinstance(data.get("facts"), str):
                data["facts"] = [data.get("facts")]
            if isinstance(data.get("hypotheses"), dict):
                data["hypotheses"] = [data.get("hypotheses")]
            if isinstance(data.get("advice"), dict):
                data["advice"] = [data.get("advice")]

            # Build structured response
            summary = data.get("summary") or (response[:500] + "..." if len(str(response)) > 500 else str(response))
            facts = data.get("facts") or []
            hypotheses = data.get("hypotheses") or []
            advice = data.get("advice") or []

            return json.dumps({
                "target": {"type": "lambda_function", "name": function_name},
                "context": investigation_context,
                "status": "completed",
                "facts": facts,
                "hypotheses": hypotheses,
                "advice": advice,
                "artifacts": {"raw_analysis": str(response)},
                "summary": summary
            })
            
        except Exception as e:
            return json.dumps({
                "target": {
                    "type": "lambda_function",
                    "name": function_name
                },
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })
    
    return investigate_lambda_function


    
    def _analyze_lambda_code_quality(self, function_name: str) -> List[Fact]:
        """Analyze Lambda function code quality."""
        facts = []
        
        try:
            # Download and analyze source code
            source_code = self.aws_client._download_lambda_code(function_name)
            code_analysis = self.aws_client._analyze_source_code(source_code, function_name)
            
            # Add code analysis facts
            for analysis in code_analysis:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=analysis.content,
                    confidence=analysis.confidence,
                    metadata=analysis.metadata
                ))
            
            # Additional code quality checks
            if source_code:
                lines = source_code.split('\n')
                total_lines = len(lines)
                
                # Check for proper error handling
                error_handling_patterns = ['try:', 'except:', 'finally:', 'raise']
                error_handling_count = sum(1 for line in lines if any(pattern in line for pattern in error_handling_patterns))
                
                if error_handling_count == 0 and total_lines > 10:
                    facts.append(Fact(
                        source="lambda_specialist",
                        content="No error handling patterns detected in code",
                        confidence=0.7,
                        metadata={"function_name": function_name, "total_lines": total_lines}
                    ))
                
                # Check for logging
                logging_patterns = ['print(', 'logger.', 'logging.', 'console.log']
                logging_count = sum(1 for line in lines if any(pattern in line for pattern in logging_patterns))
                
                if logging_count == 0:
                    facts.append(Fact(
                        source="lambda_specialist",
                        content="No logging statements detected in code",
                        confidence=0.6,
                        metadata={"function_name": function_name}
                    ))
        
        except Exception as e:
            facts.append(Fact(
                source="lambda_specialist",
                content=f"Could not analyze code quality: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
    
    def _analyze_lambda_performance(self, function_name: str) -> List[Fact]:
        """Analyze Lambda function performance."""
        facts = []
        
        try:
            # Get CloudWatch metrics for performance analysis
            metrics = self.aws_client.get_cloudwatch_metrics(function_name)
            
            # Analyze duration metrics
            duration_metrics = [m for m in metrics if 'duration' in m.get('content', '').lower()]
            if duration_metrics:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=f"Performance metrics available: {len(duration_metrics)} duration measurements",
                    confidence=0.8,
                    metadata={"function_name": function_name, "metric_count": len(duration_metrics)}
                ))
            
            # Analyze memory utilization
            memory_metrics = [m for m in metrics if 'memory' in m.get('content', '').lower()]
            if memory_metrics:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=f"Memory utilization metrics available: {len(memory_metrics)} measurements",
                    confidence=0.8,
                    metadata={"function_name": function_name, "metric_count": len(memory_metrics)}
                ))
        
        except Exception as e:
            facts.append(Fact(
                source="lambda_specialist",
                content=f"Could not analyze performance metrics: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
    
    def _analyze_lambda_errors(self, function_name: str) -> List[Fact]:
        """Analyze Lambda error patterns using enhanced log querying."""
        facts = []

        try:
            # Use enhanced log querying to get detailed failed invocations with inputs
            detailed_invocations = self.aws_client.get_lambda_failed_invocations_detailed(
                function_name, hours_back=24
            )
            facts.extend(detailed_invocations)

            # Get error patterns using Logs Insights
            error_patterns = self.aws_client.get_lambda_error_patterns(
                function_name, hours_back=24
            )
            facts.extend(error_patterns)

            # Fallback to basic CloudWatch logs if enhanced querying didn't return results
            if not detailed_invocations and not error_patterns:
                logs = self.aws_client.get_cloudwatch_logs(function_name)
                error_count = sum(1 for log in logs if 'ERROR' in str(log.get('message', '')))

                if error_count > 0:
                    facts.append(Fact(
                        source="lambda_specialist",
                        content=f"Found {error_count} recent errors in logs",
                        confidence=0.9,
                        metadata={"error_count": error_count, "function_name": function_name}
                    ))

                # Analyze error patterns
                error_logs = [log for log in logs if 'ERROR' in str(log.get('message', ''))]
                if error_logs:
                    # Group errors by type
                    error_types = {}
                    for log in error_logs:
                        message = str(log.get('message', ''))
                        if 'timeout' in message.lower():
                            error_types['timeout'] = error_types.get('timeout', 0) + 1
                        elif 'memory' in message.lower():
                            error_types['memory'] = error_types.get('memory', 0) + 1
                        elif 'permission' in message.lower():
                            error_types['permission'] = error_types.get('permission', 0) + 1
                        else:
                            error_types['other'] = error_types.get('other', 0) + 1

                    for error_type, count in error_types.items():
                        facts.append(Fact(
                            source="lambda_specialist",
                            content=f"Error pattern detected: {count} {error_type} errors",
                            confidence=0.8,
                            metadata={"error_type": error_type, "count": count, "function_name": function_name}
                        ))

        except Exception as e:
            facts.append(Fact(
                source="lambda_specialist",
                content=f"Could not analyze error patterns: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))

        return facts
    
    def _analyze_lambda_security(self, function_name: str) -> List[Fact]:
        """Analyze Lambda function security configuration."""
        facts = []
        
        try:
            # Get Lambda function details
            function_info = self.aws_client.get_lambda_function(function_name)
            config = function_info.get('Configuration', {})
            
            # IAM role analysis
            role_arn = config.get('Role', '')
            if role_arn:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=f"Function uses IAM role: {role_arn.split('/')[-1]}",
                    confidence=1.0,
                    metadata={"role_arn": role_arn, "function_name": function_name}
                ))
            
            # Environment variables security check
            env_vars = config.get('Environment', {}).get('Variables', {})
            sensitive_vars = []
            for key, value in env_vars.items():
                if any(sensitive in key.lower() for sensitive in ['password', 'secret', 'key', 'token']):
                    sensitive_vars.append(key)
            
            if sensitive_vars:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=f"Potentially sensitive environment variables: {', '.join(sensitive_vars)}",
                    confidence=0.7,
                    metadata={"sensitive_vars": sensitive_vars, "function_name": function_name}
                ))
            
            # Runtime analysis
            runtime = config.get('Runtime', '')
            if runtime:
                facts.append(Fact(
                    source="lambda_specialist",
                    content=f"Function uses runtime: {runtime}",
                    confidence=1.0,
                    metadata={"runtime": runtime, "function_name": function_name}
                ))
        
        except Exception as e:
            facts.append(Fact(
                source="lambda_specialist",
                content=f"Could not analyze security configuration: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e)}
            ))
        
        return facts
