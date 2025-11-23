#!/usr/bin/env python3
"""
VPC Specialist for PromptRCA

Analyzes AWS VPC networking to identify connectivity issues, security group blocks,
routing problems, and DNS failures.

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

Contact: info@promptrca.com
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class VPCSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS VPC networking configuration."""

    @property
    def supported_resource_types(self) -> List[str]:
        return ['vpc', 'security_group', 'subnet', 'network_interface', 'nat_gateway', 'internet_gateway']

    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze VPC networking configuration and identify connectivity issues."""
        facts = []
        resource_type = resource.get('type')
        resource_id = resource.get('id') or resource.get('name')

        if not resource_id:
            return facts

        self.logger.info(f"   → Analyzing VPC resource: {resource_type} - {resource_id}")

        # Route to appropriate analysis based on resource type
        if resource_type in ['vpc']:
            facts.extend(await self._analyze_vpc(resource_id))
        elif resource_type in ['security_group']:
            facts.extend(await self._analyze_security_group(resource_id))
        elif resource_type in ['subnet']:
            facts.extend(await self._analyze_subnet(resource_id))
        elif resource_type in ['network_interface']:
            facts.extend(await self._analyze_network_interface(resource_id))
        elif resource_type in ['nat_gateway']:
            facts.extend(await self._analyze_nat_gateway(resource_id))
        elif resource_type in ['internet_gateway']:
            facts.extend(await self._analyze_internet_gateway(resource_id))

        return self._limit_facts(facts)

    async def _analyze_vpc(self, vpc_id: str) -> List[Fact]:
        """Analyze VPC configuration."""
        facts = []

        try:
            from ..tools.vpc_tools import get_vpc_config
            config_json = get_vpc_config(vpc_id)
            config = json.loads(config_json)

            if 'error' not in config:
                vpc_state = config.get('state')
                cidr_block = config.get('cidr_block')
                is_default = config.get('is_default', False)

                facts.append(self._create_fact(
                    source='vpc_config',
                    content=f"VPC config loaded for {vpc_id}",
                    confidence=0.9,
                    metadata={
                        "vpc_id": vpc_id,
                        "state": vpc_state,
                        "cidr_block": cidr_block,
                        "is_default": is_default
                    }
                ))

                # Check VPC state
                if vpc_state != 'available':
                    facts.append(self._create_fact(
                        source='vpc_config',
                        content=f"VPC is not available: {vpc_state}",
                        confidence=0.95,
                        metadata={
                            "vpc_id": vpc_id,
                            "state": vpc_state,
                            "potential_issue": "vpc_unavailable"
                        }
                    ))

            else:
                facts.append(self._create_fact(
                    source='vpc_config',
                    content=f"Failed to retrieve VPC config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"vpc_id": vpc_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing VPC {vpc_id}: {str(e)}")
            facts.append(self._create_fact(
                source='vpc_config',
                content=f"Exception while analyzing VPC: {str(e)}",
                confidence=0.5,
                metadata={"vpc_id": vpc_id, "error": str(e)}
            ))

        return facts

    async def _analyze_security_group(self, security_group_id: str) -> List[Fact]:
        """Analyze security group rules."""
        facts = []

        try:
            from ..tools.vpc_tools import get_security_group_config
            config_json = get_security_group_config(security_group_id)
            config = json.loads(config_json)

            if 'error' not in config:
                group_name = config.get('group_name')
                vpc_id = config.get('vpc_id')
                inbound_rules = config.get('inbound_rules', [])
                outbound_rules = config.get('outbound_rules', [])

                facts.append(self._create_fact(
                    source='security_group_config',
                    content=f"Security group config loaded for {security_group_id}",
                    confidence=0.9,
                    metadata={
                        "security_group_id": security_group_id,
                        "group_name": group_name,
                        "vpc_id": vpc_id,
                        "inbound_rule_count": len(inbound_rules),
                        "outbound_rule_count": len(outbound_rules)
                    }
                ))

                # Check for empty inbound rules (blocks all incoming traffic)
                if len(inbound_rules) == 0:
                    facts.append(self._create_fact(
                        source='security_group_config',
                        content=f"Security group {security_group_id} has NO inbound rules, blocking all incoming traffic",
                        confidence=0.95,
                        metadata={
                            "security_group_id": security_group_id,
                            "group_name": group_name,
                            "potential_issue": "no_inbound_rules"
                        }
                    ))

                # Check for overly permissive rules (0.0.0.0/0)
                for rule in inbound_rules:
                    cidr_blocks = rule.get('cidr_blocks', [])
                    protocol = rule.get('protocol', 'unknown')
                    from_port = rule.get('from_port', 'unknown')
                    to_port = rule.get('to_port', 'unknown')

                    if '0.0.0.0/0' in cidr_blocks or '::/0' in cidr_blocks:
                        facts.append(self._create_fact(
                            source='security_group_config',
                            content=f"Overly permissive inbound rule: {protocol} ports {from_port}-{to_port} from 0.0.0.0/0",
                            confidence=0.8,
                            metadata={
                                "security_group_id": security_group_id,
                                "protocol": protocol,
                                "from_port": from_port,
                                "to_port": to_port,
                                "potential_issue": "overly_permissive"
                            }
                        ))

            else:
                facts.append(self._create_fact(
                    source='security_group_config',
                    content=f"Failed to retrieve security group config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"security_group_id": security_group_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing security group {security_group_id}: {str(e)}")
            facts.append(self._create_fact(
                source='security_group_config',
                content=f"Exception while analyzing security group: {str(e)}",
                confidence=0.5,
                metadata={"security_group_id": security_group_id, "error": str(e)}
            ))

        return facts

    async def _analyze_subnet(self, subnet_id: str) -> List[Fact]:
        """Analyze subnet configuration."""
        facts = []

        try:
            from ..tools.vpc_tools import get_subnet_config
            config_json = get_subnet_config(subnet_id)
            config = json.loads(config_json)

            if 'error' not in config:
                vpc_id = config.get('vpc_id')
                cidr_block = config.get('cidr_block')
                availability_zone = config.get('availability_zone')
                available_ip_count = config.get('available_ip_address_count', 0)
                state = config.get('state')
                map_public_ip = config.get('map_public_ip_on_launch', False)

                facts.append(self._create_fact(
                    source='subnet_config',
                    content=f"Subnet config loaded for {subnet_id}",
                    confidence=0.9,
                    metadata={
                        "subnet_id": subnet_id,
                        "vpc_id": vpc_id,
                        "cidr_block": cidr_block,
                        "availability_zone": availability_zone,
                        "available_ip_count": available_ip_count,
                        "state": state,
                        "map_public_ip": map_public_ip
                    }
                ))

                # Check subnet state
                if state != 'available':
                    facts.append(self._create_fact(
                        source='subnet_config',
                        content=f"Subnet is not available: {state}",
                        confidence=0.95,
                        metadata={
                            "subnet_id": subnet_id,
                            "state": state,
                            "potential_issue": "subnet_unavailable"
                        }
                    ))

                # Check for low available IPs
                if available_ip_count < 10:
                    facts.append(self._create_fact(
                        source='subnet_config',
                        content=f"Subnet has low available IP addresses: {available_ip_count}",
                        confidence=0.9,
                        metadata={
                            "subnet_id": subnet_id,
                            "available_ip_count": available_ip_count,
                            "potential_issue": "low_available_ips"
                        }
                    ))

            else:
                facts.append(self._create_fact(
                    source='subnet_config',
                    content=f"Failed to retrieve subnet config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"subnet_id": subnet_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing subnet {subnet_id}: {str(e)}")
            facts.append(self._create_fact(
                source='subnet_config',
                content=f"Exception while analyzing subnet: {str(e)}",
                confidence=0.5,
                metadata={"subnet_id": subnet_id, "error": str(e)}
            ))

        return facts

    async def _analyze_network_interface(self, network_interface_id: str) -> List[Fact]:
        """Analyze network interface configuration."""
        facts = []

        try:
            from ..tools.vpc_tools import get_network_interface_config
            config_json = get_network_interface_config(network_interface_id)
            config = json.loads(config_json)

            if 'error' not in config:
                status = config.get('status')
                subnet_id = config.get('subnet_id')
                vpc_id = config.get('vpc_id')
                private_ip = config.get('private_ip_address')
                security_groups = config.get('security_groups', [])

                facts.append(self._create_fact(
                    source='network_interface_config',
                    content=f"Network interface config loaded for {network_interface_id}",
                    confidence=0.9,
                    metadata={
                        "network_interface_id": network_interface_id,
                        "status": status,
                        "subnet_id": subnet_id,
                        "vpc_id": vpc_id,
                        "private_ip": private_ip,
                        "security_group_count": len(security_groups)
                    }
                ))

                # Check ENI status
                if status != 'in-use':
                    facts.append(self._create_fact(
                        source='network_interface_config',
                        content=f"Network interface is not in-use: {status}",
                        confidence=0.8,
                        metadata={
                            "network_interface_id": network_interface_id,
                            "status": status,
                            "potential_issue": "eni_not_in_use"
                        }
                    ))

            else:
                facts.append(self._create_fact(
                    source='network_interface_config',
                    content=f"Failed to retrieve network interface config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"network_interface_id": network_interface_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing network interface {network_interface_id}: {str(e)}")
            facts.append(self._create_fact(
                source='network_interface_config',
                content=f"Exception while analyzing network interface: {str(e)}",
                confidence=0.5,
                metadata={"network_interface_id": network_interface_id, "error": str(e)}
            ))

        return facts

    async def _analyze_nat_gateway(self, nat_gateway_id: str) -> List[Fact]:
        """Analyze NAT gateway configuration and state."""
        facts = []

        try:
            from ..tools.vpc_tools import get_nat_gateway_config
            config_json = get_nat_gateway_config(nat_gateway_id)
            config = json.loads(config_json)

            if 'error' not in config:
                state = config.get('state')
                subnet_id = config.get('subnet_id')
                vpc_id = config.get('vpc_id')
                nat_gateway_addresses = config.get('nat_gateway_addresses', [])

                facts.append(self._create_fact(
                    source='nat_gateway_config',
                    content=f"NAT gateway config loaded for {nat_gateway_id}",
                    confidence=0.9,
                    metadata={
                        "nat_gateway_id": nat_gateway_id,
                        "state": state,
                        "subnet_id": subnet_id,
                        "vpc_id": vpc_id,
                        "address_count": len(nat_gateway_addresses)
                    }
                ))

                # Check NAT gateway state
                if state != 'available':
                    facts.append(self._create_fact(
                        source='nat_gateway_config',
                        content=f"NAT gateway is not available: {state}",
                        confidence=0.95,
                        metadata={
                            "nat_gateway_id": nat_gateway_id,
                            "state": state,
                            "potential_issue": "nat_gateway_unavailable"
                        }
                    ))

            else:
                facts.append(self._create_fact(
                    source='nat_gateway_config',
                    content=f"Failed to retrieve NAT gateway config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"nat_gateway_id": nat_gateway_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing NAT gateway {nat_gateway_id}: {str(e)}")
            facts.append(self._create_fact(
                source='nat_gateway_config',
                content=f"Exception while analyzing NAT gateway: {str(e)}",
                confidence=0.5,
                metadata={"nat_gateway_id": nat_gateway_id, "error": str(e)}
            ))

        return facts

    async def _analyze_internet_gateway(self, igw_id: str) -> List[Fact]:
        """Analyze internet gateway configuration."""
        facts = []

        try:
            from ..tools.vpc_tools import get_internet_gateway_config
            config_json = get_internet_gateway_config(igw_id)
            config = json.loads(config_json)

            if 'error' not in config:
                attachments = config.get('attachments', [])
                attached_vpcs = [att.get('VpcId') for att in attachments if att.get('State') == 'attached']

                facts.append(self._create_fact(
                    source='internet_gateway_config',
                    content=f"Internet gateway config loaded for {igw_id}",
                    confidence=0.9,
                    metadata={
                        "internet_gateway_id": igw_id,
                        "attachment_count": len(attachments),
                        "attached_vpcs": attached_vpcs
                    }
                ))

                # Check if IGW is detached
                if len(attached_vpcs) == 0:
                    facts.append(self._create_fact(
                        source='internet_gateway_config',
                        content=f"Internet gateway is not attached to any VPC",
                        confidence=0.95,
                        metadata={
                            "internet_gateway_id": igw_id,
                            "potential_issue": "igw_detached"
                        }
                    ))

            else:
                facts.append(self._create_fact(
                    source='internet_gateway_config',
                    content=f"Failed to retrieve internet gateway config: {config.get('error')}",
                    confidence=0.7,
                    metadata={"internet_gateway_id": igw_id, "error": config.get('error')}
                ))

        except Exception as e:
            self.logger.error(f"Error analyzing internet gateway {igw_id}: {str(e)}")
            facts.append(self._create_fact(
                source='internet_gateway_config',
                content=f"Exception while analyzing internet gateway: {str(e)}",
                confidence=0.5,
                metadata={"internet_gateway_id": igw_id, "error": str(e)}
            ))

        return facts
