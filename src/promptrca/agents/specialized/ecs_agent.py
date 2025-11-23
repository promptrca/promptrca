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
from ...tools.ecs_tools import (
    get_ecs_cluster_config,
    get_ecs_service_config,
    get_ecs_task_definition,
    list_ecs_tasks,
    describe_ecs_tasks,
    get_ecs_cluster_metrics
)
from ...utils.prompt_loader import load_prompt


def create_ecs_agent(model) -> Agent:
    """
    Create an ECS/EKS specialist agent with comprehensive container orchestration tools.

    This agent investigates:
    - Container failures and exit codes
    - Task placement failures (insufficient capacity)
    - Service deployment issues (desired vs running count)
    - Resource exhaustion (CPU/memory)
    - IAM execution role problems
    - Image pull failures
    - Load balancer health check failures
    - Network configuration issues

    Args:
        model: The LLM model to use for this agent

    Returns:
        Agent configured for ECS/EKS investigation with all necessary tools
    """
    system_prompt = load_prompt("ecs_specialist")

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[
            get_ecs_cluster_config,
            get_ecs_service_config,
            get_ecs_task_definition,
            list_ecs_tasks,
            describe_ecs_tasks,
            get_ecs_cluster_metrics
        ],
        trace_attributes={
            "service.name": "promptrca-ecs-agent",
            "service.version": "1.0.0",
            "agent.type": "ecs_specialist",
            "aws.service": "ecs"
        }
    )


def create_ecs_agent_tool(ecs_agent: Agent):
    """
    Create a tool that wraps the ECS agent for use by orchestrators.

    This tool allows other agents or orchestrators to delegate ECS-specific
    investigations to the specialized ECS agent.

    Args:
        ecs_agent: The configured ECS specialist agent

    Returns:
        Callable tool function for investigating ECS issues
    """
    from strands import tool

    @tool
    def investigate_ecs_issue(issue_description: str) -> str:
        """
        Investigate ECS cluster, service, or task issues using the ECS specialist agent.

        Use this tool when you encounter:
        - Container failures or crashes
        - Tasks stuck in PENDING state
        - Service deployments not reaching desired count
        - "CannotPullContainerError" messages
        - Health check failures
        - Task placement errors

        Args:
            issue_description: Description of the ECS issue to investigate

        Returns:
            JSON string with investigation results including:
            - facts: Evidence-based findings from ECS configuration and metrics
            - hypotheses: Potential root causes with confidence scores
            - advice: Recommended remediation actions
            - summary: Brief description of the issue
        """
        try:
            response = ecs_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "ECS investigation failed: {str(e)}"}}'

    return investigate_ecs_issue
