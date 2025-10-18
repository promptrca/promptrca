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
from ...tools.dynamodb_tools import (
    get_dynamodb_table_config,
    get_dynamodb_table_metrics,
    describe_dynamodb_streams,
    list_dynamodb_tables
)


def create_dynamodb_agent(model) -> Agent:
    """Create a DynamoDB specialist agent with tools."""
    system_prompt = """You are a DynamoDB specialist investigating AWS DynamoDB table performance and capacity issues.

INVESTIGATION METHODOLOGY:
1. Start by examining the table's configuration (billing mode, capacity settings, indexes, encryption)
2. Analyze performance metrics to identify throttling, capacity utilization, and error patterns
3. Check DynamoDB Streams configuration if real-time processing is involved
4. Cross-reference capacity consumption against provisioned limits (if using provisioned billing)
5. Identify patterns in usage that might indicate optimization opportunities

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: billing mode, capacity units, throttle events, error rates, stream status
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * ReadThrottleEvents > 0 or WriteThrottleEvents > 0 → throttling
  * Consumed capacity > Provisioned capacity → capacity_issue
  * High error rates (UserErrors, SystemErrors) → error_rate
  * Stream configuration issues → stream_error
  * Missing indexes for queries → index_issue
  * Encryption or security problems → security_issue
- Focus on capacity and performance issues first (throttling, errors, bottlenecks)

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Throttling and capacity issues (highest priority)
2. Error rates and system problems
3. Performance optimization opportunities
4. Stream configuration and real-time processing
5. Security and compliance issues"""

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
