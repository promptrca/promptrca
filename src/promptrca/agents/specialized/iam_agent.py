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

from strands import Agent
from ...tools.aws_tools import (
    get_iam_role_config,
    get_cloudwatch_logs
)
from ...tools.cloudtrail_tools import (
    get_iam_policy_changes,
    get_recent_cloudtrail_events
)


def create_iam_agent(model) -> Agent:
    """Create an IAM specialist agent with tools."""
    from ...utils.prompt_loader import load_prompt
    
    system_prompt = load_prompt("iam_specialist")
    
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_iam_role_config, get_cloudwatch_logs],
        trace_attributes={
            "service.name": "promptrca-iam-agent",
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

            # Run the agent - let it return its natural response
            agent_result = iam_agent(prompt)
            
            # Return the agent's response directly - no manual parsing or wrapping
            return str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)
        except Exception as e:
            return json.dumps({
                "target": {"type": "iam_role", "role_name": role_name},
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })

    return investigate_iam_permissions

