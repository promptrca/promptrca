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

from strands import Agent
from ...tools.aws_tools import (
    get_iam_role_config,
    get_cloudwatch_logs
)


def create_iam_agent(model) -> Agent:
    """Create an IAM specialist agent with tools."""
    system_prompt = """You are an IAM specialist investigating AWS IAM permission and access control issues.

INVESTIGATION METHODOLOGY:
1. Start by examining the IAM role configuration (trust policy, attached policies, inline policies)
2. Analyze CloudWatch logs for AccessDenied errors and permission failures
3. Cross-reference required actions against allowed actions in policy statements
4. Identify missing permissions, overly broad permissions, or misconfigured trust relationships
5. Check for policy conflicts or resource-specific permission issues

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: policy statements, allowed actions, denied actions, trust relationships
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * "User X is not authorized to perform Y" in logs → permission_issue
  * Missing required action in policy → missing_permission
  * Overly broad permissions → overprivileged_role
  * Trust policy issues → trust_relationship_error
  * Resource-specific permission problems → resource_permission_issue
  * Policy conflicts → policy_conflict
- Focus on permission and access control problems first (denials, missing permissions)

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Access denied errors and missing permissions (highest priority)
2. Overly broad or insecure permissions
3. Trust relationship and policy configuration issues
4. Resource-specific permission problems
5. Policy optimization and security hardening"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_iam_role_config, get_cloudwatch_logs],
        trace_attributes={
            "service.name": "sherlock-iam-agent",
            "service.version": "1.0.0",
            "agent.type": "iam_specialist",
            "aws.service": "iam"
        }
    )


def create_iam_agent_tool(iam_agent: Agent):
    """Create a tool that wraps the IAM agent for use by orchestrators."""
    from strands import tool

    @tool
    def investigate_iam_permissions(role_name: str, investigation_context: str = "") -> str:
        import json
        try:
            prompt = f"""Investigate IAM role permissions: {role_name}

Context: {investigation_context}

Please analyze this IAM role for any permission issues, policy problems, or security concerns. Start by getting the role configuration, then check logs for IAM-related errors."""

            agent_result = iam_agent(prompt)
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
                "target": {"type": "iam_role", "role_name": role_name},
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
                "target": {"type": "iam_role", "role_name": role_name},
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })

    return investigate_iam_permissions

