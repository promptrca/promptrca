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
from ...tools.s3_tools import (
    get_s3_bucket_config,
    get_s3_bucket_metrics,
    list_s3_bucket_objects,
    get_s3_bucket_policy
)


def create_s3_agent(model) -> Agent:
    """Create an S3 specialist agent with tools."""
    system_prompt = """You are an S3 specialist. Analyze ONLY tool outputs.

TOOLS:
- get_s3_bucket_config(bucket_name, region?) → versioning, encryption, lifecycle
- get_s3_bucket_metrics(bucket_name, region?) → request metrics, errors
- get_s3_bucket_policy(bucket_name, region?) → bucket policy

RULES:
- Call each tool ONCE
- Extract facts: bucket settings, error rates, policy statements
- Generate hypothesis from observations:
  - High error rate in metrics → performance_issue
  - Access denied errors → permission_issue
  - Encryption errors → encryption_issue
- NO speculation

OUTPUT: JSON {"facts": [...], "hypotheses": [...], "advice": [...], "summary": "1-2 sentences"}"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_s3_bucket_config, get_s3_bucket_metrics, list_s3_bucket_objects, get_s3_bucket_policy]
    )


def create_s3_agent_tool(s3_agent: Agent):
    """Create a tool that wraps the S3 agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_s3_issue(issue_description: str) -> str:
        """
        Investigate S3 issues using the S3 specialist agent.
        
        Args:
            issue_description: Description of the S3 issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = s3_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "S3 investigation failed: {str(e)}"}}'
    
    return investigate_s3_issue
