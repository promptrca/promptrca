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
from ...tools.sqs_tools import (
    get_sqs_queue_config,
    get_sqs_queue_metrics,
    get_sqs_dead_letter_queue,
    list_sqs_queues
)


def create_sqs_agent(model) -> Agent:
    """Create an SQS specialist agent with tools."""
    system_prompt = """You are an SQS specialist. Investigate SQS issues quickly and precisely.

PROCESS:
1) Get queue configuration
2) Check queue metrics for performance issues
3) Check dead letter queue configuration
4) Identify specific issue

TOOLS:
- get_sqs_queue_config(queue_url, region?)
- get_sqs_queue_metrics(queue_name, region?)
- get_sqs_dead_letter_queue(queue_url, region?)
- list_sqs_queues(prefix?, region?)

OUTPUT: Respond with ONLY JSON using this schema:
{
  "facts": [
    {"content": "...", "confidence": 0.0-1.0, "metadata": {}}
  ],
  "hypotheses": [
    {"type": "visibility_timeout|message_retention|dlq_issue|permission_issue|configuration_error|performance_issue|resource_constraint|infrastructure_issue|integration_failure", "description": "...", "confidence": 0.0-1.0, "evidence": ["..."]}
  ],
  "advice": [
    {"title": "...", "description": "...", "priority": "low|medium|high|critical", "category": "..."}
  ],
  "summary": "<= 120 words concise conclusion"
}"""

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
