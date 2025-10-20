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
from ...tools.lambda_tools import (
    get_lambda_metrics,
    get_lambda_logs,
    get_lambda_layers,
    get_lambda_failed_invocations,
    get_lambda_version_history
)
from ...tools.cloudtrail_tools import (
    get_recent_cloudtrail_events,
    get_iam_policy_changes
)
from ...tools.aws_health_tools import (
    check_aws_service_health
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
   - **USE get_recent_cloudtrail_events() to check for recent Lambda configuration changes**
   - Check for similar past incidents with this function
   - Review recent deployment history and code changes (UpdateFunctionCode, UpdateFunctionConfiguration)
   - Examine configuration change timeline (environment variables, IAM role updates, timeout/memory adjustments)
   - Identify any correlated infrastructure changes
   - **USE get_iam_policy_changes() if permission errors detected**

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
        tools=[
            get_lambda_config,
            get_lambda_logs,
            get_lambda_metrics,
            get_lambda_layers,
            get_lambda_failed_invocations,
            get_lambda_version_history,
            get_iam_role_config
        ],
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

Investigation steps:
1. Get function configuration to understand current settings
2. Check version history to correlate with incident timeline
3. Examine logs for errors and exceptions
4. Review failed invocations for patterns
5. Check metrics for performance issues
6. Verify IAM permissions if needed

Focus on temporal correlation - if there was a recent deployment, compare timing with issue start."""

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
