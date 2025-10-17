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
    system_prompt = """You are a VPC specialist. Analyze ONLY tool outputs.

TOOLS:
- get_vpc_config(vpc_id, region?) → VPC settings, CIDR blocks
- get_subnet_config(subnet_id, region?) → subnet settings, availability zone
- get_security_group_config(security_group_id, region?) → inbound/outbound rules
- get_network_interface_config(network_interface_id, region?) → interface status
- get_nat_gateway_config(nat_gateway_id, region?) → NAT gateway status
- get_internet_gateway_config(igw_id, region?) → IGW status

RULES:
- Call each tool ONCE
- Extract facts: network configuration, security rules, gateway status
- Generate hypothesis from observations:
  - Security group blocks traffic → security_group_issue
  - Subnet has no route to IGW → connectivity_issue
  - NAT gateway failed → gateway_issue
- NO speculation

OUTPUT: JSON {"facts": [...], "hypotheses": [...], "advice": [...], "summary": "1-2 sentences"}"""

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
