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

from typing import Any
from strands import Agent
from ...tools.sqs_tools import (
    get_sqs_queue_config,
    get_sqs_queue_metrics,
    get_sqs_dead_letter_queue,
    list_sqs_queues
)


def create_sqs_agent(model) -> Agent:
    """Create an SQS specialist agent with tools."""
    system_prompt = """You are an SQS specialist. Analyze ONLY tool outputs.

TOOLS:
- get_sqs_queue_config(queue_url, region?) → visibility timeout, DLQ settings
- get_sqs_queue_metrics(queue_name, region?) → message count, age, errors
- get_sqs_dead_letter_queue(queue_url, region?) → DLQ configuration

RULES:
- Call each tool ONCE
- Extract facts: queue settings, message counts, error rates
- Generate hypothesis from observations:
  - High message age → visibility_timeout
  - Messages in DLQ → dlq_issue
  - Throttling errors → performance_issue
- NO speculation

OUTPUT: JSON {"facts": [...], "hypotheses": [...], "advice": [...], "summary": "1-2 sentences"}"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_sqs_queue_config, get_sqs_queue_metrics, get_sqs_dead_letter_queue, list_sqs_queues]
    )


def create_sqs_agent_tool(sqs_agent: Agent):
    """Create a tool that wraps the SQS agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_sqs_issue(issue_description: str) -> str:
        """
        Investigate SQS issues using the SQS specialist agent.
        
        Args:
            issue_description: Description of the SQS issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = sqs_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "SQS investigation failed: {str(e)}"}}'
    
    return investigate_sqs_issue
