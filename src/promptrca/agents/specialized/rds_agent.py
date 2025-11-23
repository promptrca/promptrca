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
from ...tools.rds_tools import (
    get_rds_instance_config,
    get_rds_cluster_config,
    get_rds_instance_metrics,
    list_rds_instances
)
from ...utils.prompt_loader import load_prompt


def create_rds_agent(model) -> Agent:
    """
    Create an RDS/Aurora specialist agent with comprehensive database investigation tools.

    This agent investigates:
    - Connection pool exhaustion
    - High CPU/memory utilization
    - Storage space issues
    - Replication lag (read replicas)
    - Instance availability problems
    - Performance degradation
    - Slow queries and I/O bottlenecks
    - Database connection timeouts

    Args:
        model: The LLM model to use for this agent

    Returns:
        Agent configured for RDS/Aurora investigation with all necessary tools
    """
    system_prompt = load_prompt("rds_specialist")

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[
            get_rds_instance_config,
            get_rds_cluster_config,
            get_rds_instance_metrics,
            list_rds_instances
        ],
        trace_attributes={
            "service.name": "promptrca-rds-agent",
            "service.version": "1.0.0",
            "agent.type": "rds_specialist",
            "aws.service": "rds"
        }
    )


def create_rds_agent_tool(rds_agent: Agent):
    """
    Create a tool that wraps the RDS agent for use by orchestrators.

    This tool allows other agents or orchestrators to delegate RDS-specific
    investigations to the specialized RDS agent.

    Args:
        rds_agent: The configured RDS specialist agent

    Returns:
        Callable tool function for investigating RDS issues
    """
    from strands import tool

    @tool
    def investigate_rds_issue(issue_description: str) -> str:
        """
        Investigate RDS/Aurora database issues using the RDS specialist agent.

        Use this tool when you encounter:
        - Database connection timeouts
        - High CPU or memory utilization
        - Storage space warnings
        - Replication lag alerts
        - "too many connections" errors
        - Slow query performance
        - Database instance unavailability

        Args:
            issue_description: Description of the RDS issue to investigate

        Returns:
            JSON string with investigation results including:
            - facts: Evidence-based findings from RDS configuration and metrics
            - hypotheses: Potential root causes with confidence scores
            - advice: Recommended remediation actions
            - summary: Brief description of the issue
        """
        try:
            response = rds_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "RDS investigation failed: {str(e)}"}}'

    return investigate_rds_issue
