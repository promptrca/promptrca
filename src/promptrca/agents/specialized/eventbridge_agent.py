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
from ...tools.eventbridge_tools import (
    get_eventbridge_rule_config,
    get_eventbridge_targets,
    get_eventbridge_metrics,
    list_eventbridge_rules,
    get_eventbridge_bus_config
)


def create_eventbridge_agent(model) -> Agent:
    """Create an EventBridge specialist agent with tools."""
    system_prompt = """You are an EventBridge specialist. Analyze ONLY tool outputs.

TOOLS:
- get_eventbridge_rule_config(rule_name, region?) → rule settings, event pattern
- get_eventbridge_targets(rule_name, region?) → target configuration
- get_eventbridge_metrics(rule_name, region?) → execution success rate, errors

RULES:
- Call each tool ONCE
- Extract facts: rule settings, execution rates, target status
- Generate hypothesis from observations:
  - Low execution success rate → rule_execution_failure
  - Target errors → target_failure
  - Rule disabled → configuration_error
- NO speculation

OUTPUT: JSON {"facts": [...], "hypotheses": [...], "advice": [...], "summary": "1-2 sentences"}"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_eventbridge_rule_config, get_eventbridge_targets, get_eventbridge_metrics, list_eventbridge_rules, get_eventbridge_bus_config]
    )


def create_eventbridge_agent_tool(eventbridge_agent: Agent):
    """Create a tool that wraps the EventBridge agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_eventbridge_issue(issue_description: str) -> str:
        """
        Investigate EventBridge issues using the EventBridge specialist agent.
        
        Args:
            issue_description: Description of the EventBridge issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = eventbridge_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "EventBridge investigation failed: {str(e)}"}}'
    
    return investigate_eventbridge_issue
