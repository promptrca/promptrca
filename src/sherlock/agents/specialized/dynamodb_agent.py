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

from typing import Any
from strands import Agent
from ...tools.dynamodb_tools import (
    get_dynamodb_table_config,
    get_dynamodb_table_metrics,
    describe_dynamodb_streams,
    list_dynamodb_tables
)


def create_dynamodb_agent(model) -> Agent:
    """Create a DynamoDB specialist agent with tools."""
    system_prompt = """You are a DynamoDB specialist. Analyze ONLY tool outputs.

TOOLS:
- get_dynamodb_table_config(table_name, region?) → billing mode, capacity, indexes
- get_dynamodb_table_metrics(table_name, region?) → consumed/provisioned capacity, throttles
- describe_dynamodb_streams(table_name, region?) → stream status

RULES:
- Call each tool ONCE
- Extract facts: capacity mode, read/write units, throttle count
- Generate hypothesis from metrics:
  - ThrottledRequests > 0 → throttling
  - Consumed > Provisioned → capacity_issue
  - Stream errors in response → stream_error
- If on-demand mode → no capacity constraints
- NO speculation

OUTPUT: JSON {"facts": [...], "hypotheses": [...], "advice": [...], "summary": "1-2 sentences"}"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_dynamodb_table_config, get_dynamodb_table_metrics, describe_dynamodb_streams, list_dynamodb_tables]
    )


def create_dynamodb_agent_tool(dynamodb_agent: Agent):
    """Create a tool that wraps the DynamoDB agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_dynamodb_issue(issue_description: str) -> str:
        """
        Investigate DynamoDB issues using the DynamoDB specialist agent.
        
        Args:
            issue_description: Description of the DynamoDB issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = dynamodb_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "DynamoDB investigation failed: {str(e)}"}}'
    
    return investigate_dynamodb_issue
