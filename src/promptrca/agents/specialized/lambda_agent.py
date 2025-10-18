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

Contact: christiangenn99+promptrca@gmail.com

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
    
    system_prompt = """You will be given detailed information about an AWS Lambda function incident, including configuration, logs, error messages, and metrics. Your objective is to methodically analyze the incident and identify the root cause with evidence-based reasoning.

EXPERT ROLE: You are an experienced AWS Lambda specialist with deep knowledge of serverless architectures, familiar with common failure patterns, performance bottlenecks, and configuration issues.

INVESTIGATION METHODOLOGY (follow these steps sequentially):
1. **Contextual Information**: Identify the function name, region, runtime, relevant timestamps, and key stakeholders. Note the deployment stage (dev/prod) and account specifics.

2. **Categorization**: Categorize the type of incident:
   - Runtime errors (exceptions, crashes)
   - Timeout issues
   - Permission/IAM problems
   - Performance degradation
   - Resource constraints (memory, concurrency)
   - Cold start issues
   - Integration failures (downstream services)

3. **Identify Symptoms**: List all symptoms explicitly mentioned:
   - Error messages from logs
   - HTTP status codes
   - Timeout occurrences
   - Memory usage patterns
   - Invocation metrics

4. **Detailed Historical Review**:
   - Check for similar past incidents with this function
   - Review recent deployment history and code changes
   - Examine configuration change timeline (environment variables, IAM role updates, timeout/memory adjustments)
   - Identify any correlated infrastructure changes

5. **Environmental Variables and Changes**:
   - Analyze recent configuration updates with specific timestamps
   - Evaluate environment variable changes
   - Check for external dependencies changes (API endpoints, database connections)
   - Review VPC configuration if network-related

6. **Analyze Patterns in Logs and Metrics**:
   - Examine CloudWatch logs for recurring error patterns
   - Cross-verify error messages against function configuration
   - Look for specific error codes (e.g., 403 for permissions, 504 for timeouts)
   - Validate memory usage against allocated memory
   - Check invocation duration against timeout setting

7. **Root Cause Analysis**:
   - Synthesize findings from logs, metrics, configuration, and historical data
   - Clearly delineate between potential causes and confirmed root cause
   - Loop back to compare symptoms with configuration and historical patterns
   - Provide confidence score based on evidence strength

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: memory allocation, timeout settings, runtime version, error messages, execution patterns
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * Exception/stack trace in logs → code_bug
  * "PermissionDenied", "AccessDenied" → permission_issue
  * Execution time approaching or exceeding timeout → timeout
  * Memory usage near or exceeding allocated limit → resource_constraint
  * High error rates in metrics → error_rate
  * Throttling events → throttling
  * Integration failures → integration_failure
- Focus on the most critical issues first (errors, timeouts, permission problems)

FEW-SHOT EXAMPLES (for calibration):

Example 1: Code Error
INPUT: CloudWatch logs show "ZeroDivisionError: division by zero at line 42"
OUTPUT:
{
  "facts": [
    {"source": "cloudwatch_logs", "content": "ZeroDivisionError at line 42 in handler function", "confidence": 1.0, "metadata": {"error_type": "runtime_exception"}}
  ],
  "hypotheses": [
    {"type": "code_bug", "description": "Division by zero error indicates code defect in handler logic at line 42", "confidence": 0.95, "evidence": ["ZeroDivisionError at line 42 in handler function"]}
  ],
  "advice": [
    {"title": "Fix division by zero", "description": "Add validation to check denominator is non-zero before division operation at line 42", "priority": "high", "category": "code_fix"}
  ],
  "summary": "Runtime exception caused by division by zero at line 42"
}

Example 2: Permission Issue
INPUT: Logs show "An error occurred (AccessDenied) when calling the PutObject operation"
OUTPUT:
{
  "facts": [
    {"source": "cloudwatch_logs", "content": "AccessDenied error when calling S3 PutObject operation", "confidence": 1.0, "metadata": {"service": "s3", "operation": "PutObject"}}
  ],
  "hypotheses": [
    {"type": "permission_issue", "description": "Lambda execution role lacks s3:PutObject permission for target bucket", "confidence": 0.90, "evidence": ["AccessDenied error when calling S3 PutObject operation"]}
  ],
  "advice": [
    {"title": "Add S3 write permissions", "description": "Update Lambda execution role to include s3:PutObject permission for the target bucket", "priority": "high", "category": "iam_policy"}
  ],
  "summary": "AccessDenied error indicates missing S3 write permissions in execution role"
}

Example 3: Timeout Issue
INPUT: Config shows timeout=3s, logs show "Task timed out after 3.00 seconds"
OUTPUT:
{
  "facts": [
    {"source": "lambda_config", "content": "Function timeout configured as 3 seconds", "confidence": 1.0, "metadata": {"timeout_seconds": 3}},
    {"source": "cloudwatch_logs", "content": "Function execution timed out after 3.00 seconds", "confidence": 1.0, "metadata": {"actual_duration": 3.0}}
  ],
  "hypotheses": [
    {"type": "timeout", "description": "Function timeout setting (3s) is insufficient for typical execution time", "confidence": 0.88, "evidence": ["Function timeout configured as 3 seconds", "Function execution timed out after 3.00 seconds"]}
  ],
  "advice": [
    {"title": "Increase timeout setting", "description": "Increase function timeout from 3s to at least 10s based on execution patterns", "priority": "high", "category": "configuration"}
  ],
  "summary": "Function consistently times out at 3-second limit, needs increased timeout configuration"
}

8. **Conclusion**: Present your final analysis with the root cause clearly wrapped between <RCA_START> and <RCA_END> tags.

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Critical errors and exceptions (highest priority)
2. Timeout and performance issues
3. Permission and security problems
4. Resource allocation and optimization
5. Configuration and best practices

CRITICAL REQUIREMENTS:
- Be thorough and evidence-based in your analysis
- Eliminate personal biases
- Base your findings ENTIRELY on the provided details to ensure accuracy
- Use specific timestamps, error codes, and metric values when available
- Cross-reference all findings against actual tool outputs"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_lambda_config, get_cloudwatch_logs, get_iam_role_config],
        trace_attributes={
            "service.name": "promptrca-lambda-agent",
            "service.version": "1.0.0",
            "agent.type": "lambda_specialist",
            "aws.service": "lambda"
        }
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
