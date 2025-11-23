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
    from ...utils.prompt_loader import load_prompt
    
    system_prompt = load_prompt("lambda_specialist")
    
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

            # Run the agent - let it return its natural response
            agent_result = lambda_agent(prompt)
            
            # Return the agent's response directly - no manual parsing or wrapping
            return str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)
            
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
