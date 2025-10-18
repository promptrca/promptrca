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
    get_api_gateway_stage_config,
    get_iam_role_config,
    get_cloudwatch_logs
)


def create_apigateway_agent(model) -> Agent:
    """Create an API Gateway specialist agent with tools."""
    
    system_prompt = """You will be given detailed information about an AWS API Gateway incident, including stage configuration, integration settings, logs, and error messages. Your objective is to methodically analyze the incident and identify the root cause with evidence-based reasoning.

EXPERT ROLE: You are an experienced API Gateway specialist with deep knowledge of REST/HTTP APIs, integration patterns, authentication mechanisms, and request/response transformations. You are familiar with common API Gateway failure modes.

INVESTIGATION METHODOLOGY (follow these steps sequentially):
1. **Contextual Information**: Identify the API ID, stage name, region, relevant timestamps, and deployment history. Note the API type (REST/HTTP/WebSocket) and key integrations.

2. **Categorization**: Categorize the type of incident:
   - Integration failures (backend service errors)
   - Authentication/authorization issues
   - Request/response transformation problems
   - Throttling and quota issues
   - CORS configuration errors
   - Method/resource routing problems
   - WAF or security rule blocks

3. **Identify Symptoms**: List all symptoms explicitly mentioned:
   - HTTP status codes (4xx, 5xx)
   - Error messages from logs
   - Integration response codes
   - Latency measurements
   - Request patterns

4. **Detailed Historical Review**:
   - Check for similar past integration failures
   - Review recent API deployment history
   - Examine integration configuration change timeline
   - Identify correlated changes in backend services

5. **Environmental Variables and Changes**:
   - Analyze recent stage variable updates with timestamps
   - Evaluate integration URI changes
   - Check for IAM role or policy modifications
   - Review authorization configuration changes

6. **Analyze Patterns in Logs and Access Logs**:
   - Examine CloudWatch logs for recurring error patterns
   - Cross-verify integration responses against expected behavior
   - Look for specific error codes (e.g., 403 for auth, 502/504 for backend failures)
   - Validate request transformations and mappings
   - Check for CORS preflight failures

7. **Root Cause Analysis**:
   - Synthesize findings from logs, configuration, and backend service status
   - Clearly delineate between API Gateway issues vs backend service issues
   - Loop back to compare symptoms with integration configuration
   - Provide confidence score based on evidence strength

8. **Conclusion**: Present your final analysis with the root cause clearly wrapped between <RCA_START> and <RCA_END> tags.

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: integration types, target services, IAM roles, error patterns, HTTP status codes
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * 4xx HTTP errors in logs → client_error
  * 5xx HTTP errors in logs → server_error
  * Integration type mismatches → integration_error
  * Missing IAM permissions → permission_issue
  * Wrong integration URIs → configuration_error
  * Throttling (429 errors) → throttling
  * CORS errors → cors_issue
  * Authentication failures → auth_issue
- Focus on integration and routing problems first (errors, permissions, configuration)

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Integration errors and backend service failures (highest priority)
2. Authentication and permission issues
3. Configuration problems and routing issues
4. Performance and throttling problems
5. CORS and client-side issues

CRITICAL REQUIREMENTS:
- Be thorough and evidence-based in your analysis
- Eliminate personal biases
- Base your findings ENTIRELY on the provided details to ensure accuracy
- Use specific timestamps, HTTP status codes, and integration URIs when available
- Cross-reference all findings against actual tool outputs
- Distinguish between API Gateway issues and backend service issues"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_api_gateway_stage_config, get_iam_role_config, get_cloudwatch_logs],
        trace_attributes={
            "service.name": "promptrca-apigateway-agent",
            "service.version": "1.0.0",
            "agent.type": "apigateway_specialist",
            "aws.service": "apigateway"
        }
    )


def create_apigateway_agent_tool(apigateway_agent: Agent):
    """Create a tool that wraps the API Gateway agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_api_gateway(api_id: str, stage_name: str = "test", investigation_context: str = "") -> str:
        """
        Investigate an API Gateway for issues and problems.
        
        Args:
            api_id: The API Gateway REST API ID
            stage_name: The stage name (e.g., 'test', 'prod')
            investigation_context: Additional context about the investigation (e.g., error messages, trace IDs)
        
        Returns:
            JSON string with investigation results and findings
        """
        import json
        
        try:
            # Create investigation prompt
            prompt = f"""Investigate API Gateway: {api_id} (stage: {stage_name})
            
Context: {investigation_context}

Please analyze this API Gateway for any issues, errors, or problems. Start by getting the stage configuration, then check IAM permissions if integration issues are suspected, and examine logs for errors."""

            # Run the agent
            agent_result = apigateway_agent(prompt)
            
            # Extract the response content from AgentResult
            response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

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
            summary = data.get("summary") or (response[:500] + "..." if len(str(response)) > 500 else str(response))

            return json.dumps({
                "target": {"type": "api_gateway", "api_id": api_id, "stage_name": stage_name},
                "context": investigation_context,
                "status": "completed",
                "facts": data.get("facts") or [],
                "hypotheses": data.get("hypotheses") or [],
                "advice": data.get("advice") or [],
                "artifacts": {"raw_analysis": str(response)},
                "summary": summary
            })
            
        except Exception as e:
            return json.dumps({
                "target": {
                    "type": "api_gateway",
                    "api_id": api_id,
                    "stage_name": stage_name
                },
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })
    
    return investigate_api_gateway

