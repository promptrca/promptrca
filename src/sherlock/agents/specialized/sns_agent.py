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
from ...tools.sns_tools import (
    get_sns_topic_config,
    get_sns_topic_metrics,
    get_sns_subscriptions,
    list_sns_topics
)
from ...prompts.loader import load_prompt, load_prompt_with_vars


def create_sns_agent(model) -> Agent:
    """Create an SNS specialist agent with tools."""
    system_prompt = load_prompt("specialized/sns_agent")

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_sns_topic_config, get_sns_topic_metrics, get_sns_subscriptions, list_sns_topics]
    )


def create_sns_agent_tool(sns_agent: Agent):
    """Create a tool that wraps the SNS agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_sns_issue(issue_description: str) -> str:
        """
        Investigate SNS issues using the SNS specialist agent.
        
        Args:
            issue_description: Description of the SNS issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = sns_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "SNS investigation failed: {str(e)}"}}'
    
    return investigate_sns_issue
