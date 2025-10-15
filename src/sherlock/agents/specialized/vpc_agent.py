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
from ...tools.vpc_tools import (
    get_vpc_config,
    get_subnet_config,
    get_security_group_config,
    get_network_interface_config,
    get_nat_gateway_config,
    get_internet_gateway_config
)


def create_vpc_agent(model) -> Agent:
    """Create a VPC specialist agent with tools."""
    system_prompt = """You are a VPC/Network specialist. Investigate VPC and networking issues quickly and precisely.

PROCESS:
1) Get VPC configuration
2) Check subnet and security group configurations
3) Check network interfaces and gateways
4) Identify specific issue

TOOLS:
- get_vpc_config(vpc_id, region?)
- get_subnet_config(subnet_id, region?)
- get_security_group_config(security_group_id, region?)
- get_network_interface_config(network_interface_id, region?)
- get_nat_gateway_config(nat_gateway_id, region?)
- get_internet_gateway_config(igw_id, region?)

OUTPUT: Respond with ONLY JSON using this schema:
{
  "facts": [
    {"content": "...", "confidence": 0.0-1.0, "metadata": {}}
  ],
  "hypotheses": [
    {"type": "connectivity_issue|security_group_issue|subnet_issue|gateway_issue|permission_issue|configuration_error|resource_constraint|infrastructure_issue|integration_failure", "description": "...", "confidence": 0.0-1.0, "evidence": ["..."]}
  ],
  "advice": [
    {"title": "...", "description": "...", "priority": "low|medium|high|critical", "category": "..."}
  ],
  "summary": "<= 120 words concise conclusion"
}"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_vpc_config, get_subnet_config, get_security_group_config, get_network_interface_config, get_nat_gateway_config, get_internet_gateway_config]
    )


def create_vpc_agent_tool(vpc_agent: Agent):
    """Create a tool that wraps the VPC agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_vpc_issue(issue_description: str) -> str:
        """
        Investigate VPC/Network issues using the VPC specialist agent.
        
        Args:
            issue_description: Description of the VPC/Network issue to investigate
        
        Returns:
            JSON string with investigation results
        """
        try:
            response = vpc_agent.run(issue_description)
            return response
        except Exception as e:
            return f'{{"error": "VPC investigation failed: {str(e)}"}}'
    
    return investigate_vpc_issue
