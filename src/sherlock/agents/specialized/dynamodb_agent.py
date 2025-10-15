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
    system_prompt = """You are a DynamoDB specialist. Investigate DynamoDB issues quickly and precisely.

PROCESS:
1) Get table configuration
2) Check table metrics for performance issues
3) Check streams if configured
4) Identify specific issue

TOOLS:
- get_dynamodb_table_config(table_name, region?)
- get_dynamodb_table_metrics(table_name, region?)
- describe_dynamodb_streams(table_name, region?)
- list_dynamodb_tables(region?)

OUTPUT: Respond with ONLY JSON using this schema:
{
  "facts": [
    {"content": "...", "confidence": 0.0-1.0, "metadata": {}}
  ],
  "hypotheses": [
    {"type": "throttling|capacity_issue|stream_error|configuration_error|permission_issue|resource_constraint|timeout|infrastructure_issue|integration_failure", "description": "...", "confidence": 0.0-1.0, "evidence": ["..."]}
  ],
  "advice": [
    {"title": "...", "description": "...", "priority": "low|medium|high|critical", "category": "..."}
  ],
  "summary": "<= 120 words concise conclusion"
}"""

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
