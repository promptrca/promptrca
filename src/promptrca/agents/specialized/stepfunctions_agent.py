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

from typing import Any
from strands import Agent
from ...tools.aws_tools import (
    get_stepfunctions_definition,
    get_iam_role_config,
    get_cloudwatch_logs
)
from ...tools.stepfunctions_tools import (
    get_stepfunctions_execution_details,
    list_recent_stepfunctions_executions
)


def create_stepfunctions_agent(model) -> Agent:
    """Create a Step Functions specialist agent with tools."""
    from ...utils.prompt_loader import load_prompt
    
    system_prompt = load_prompt("stepfunctions_specialist")
    
    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[
            get_stepfunctions_definition,
            get_stepfunctions_execution_details,
            list_recent_stepfunctions_executions,
            get_iam_role_config,
            get_cloudwatch_logs
        ],
        trace_attributes={
            "service.name": "promptrca-stepfunctions-agent",
            "service.version": "1.0.0",
            "agent.type": "stepfunctions_specialist",
            "aws.service": "stepfunctions"
        }
    )


def create_stepfunctions_agent_tool(stepfunctions_agent: Agent):
    """Create a tool that wraps the Step Functions agent for use by orchestrators."""
    from strands import tool

    @tool
    def investigate_stepfunctions(state_machine_arn: str = "", execution_arn: str = "", investigation_context: str = "") -> str:
        """
        Investigate Step Functions state machine or specific execution for failures and issues.

        Args:
            state_machine_arn: State machine ARN (for general investigation)
            execution_arn: Execution ARN (for specific execution failure investigation)
            investigation_context: Additional context about the investigation

        Returns:
            JSON string with investigation results
        """
        import json
        try:
            # Build investigation prompt based on what's provided
            if execution_arn:
                prompt = f"""Investigate failed Step Functions execution: {execution_arn}

Context: {investigation_context}

Investigation steps:
1. Get execution details to see which state failed and error details
2. List recent executions to see if this is a pattern
3. Get state machine definition to understand workflow
4. Check IAM permissions if States.Permissions error
5. Examine logs for additional context"""
            else:
                prompt = f"""Investigate Step Functions state machine: {state_machine_arn}

Context: {investigation_context}

Investigation steps:
1. List recent failed executions to identify patterns
2. Get execution details for failed executions
3. Get state machine definition to review configuration
4. Check IAM permissions if execution issues suspected
5. Examine logs for errors"""

            # Run the agent - let it return its natural response
            agent_result = stepfunctions_agent(prompt)
            
            # Return the agent's response directly - no manual parsing or wrapping
            return str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)
        except Exception as e:
            # Build target info for error case too
            target_info = {"type": "step_functions"}
            if execution_arn:
                target_info["execution_arn"] = execution_arn
                target_info["state_machine_arn"] = state_machine_arn
            else:
                target_info["state_machine_arn"] = state_machine_arn

            return json.dumps({
                "target": target_info,
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })

    return investigate_stepfunctions

