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
    system_prompt = """You are an S3 specialist. Investigate S3 issues quickly and precisely.

PROCESS:
1) Get bucket configuration
2) Check bucket metrics for performance issues
3) Check bucket policy and permissions
4) Identify specific issue

TOOLS:
- get_s3_bucket_config(bucket_name, region?)
- get_s3_bucket_metrics(bucket_name, region?)
- list_s3_bucket_objects(bucket_name, prefix?, max_keys?, region?)
- get_s3_bucket_policy(bucket_name, region?)

OUTPUT: Respond with ONLY JSON using this schema:
{
  "facts": [
    {"content": "...", "confidence": 0.0-1.0, "metadata": {}}
  ],
  "hypotheses": [
    {"type": "permission_issue|configuration_error|performance_issue|encryption_issue|lifecycle_issue|notification_issue|resource_constraint|infrastructure_issue|integration_failure", "description": "...", "confidence": 0.0-1.0, "evidence": ["..."]}
  ],
  "advice": [
    {"title": "...", "description": "...", "priority": "low|medium|high|critical", "category": "..."}
  ],
  "summary": "<= 120 words concise conclusion"
}"""

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
