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

from strands import tool
from typing import Dict, Any
import json
from ..utils.config import get_region


@tool
def get_vpc_config(vpc_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get VPC configuration and details.
    
    Args:
        vpc_id: The VPC ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with VPC configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_vpcs(VpcIds=[vpc_id])
        vpc = response['Vpcs'][0]
        
        config = {
            "vpc_id": vpc.get('VpcId'),
            "cidr_block": vpc.get('CidrBlock'),
            "state": vpc.get('State'),
            "is_default": vpc.get('IsDefault', False),
            "instance_tenancy": vpc.get('InstanceTenancy'),
            "ipv6_cidr_block_association_set": vpc.get('Ipv6CidrBlockAssociationSet', []),
            "cidr_block_association_set": vpc.get('CidrBlockAssociationSet', []),
            "dhcp_options_id": vpc.get('DhcpOptionsId'),
            "tags": vpc.get('Tags', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "vpc_id": vpc_id})


@tool
def get_subnet_config(subnet_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get subnet configuration and details.
    
    Args:
        subnet_id: The subnet ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with subnet configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_subnets(SubnetIds=[subnet_id])
        subnet = response['Subnets'][0]
        
        config = {
            "subnet_id": subnet.get('SubnetId'),
            "vpc_id": subnet.get('VpcId'),
            "cidr_block": subnet.get('CidrBlock'),
            "availability_zone": subnet.get('AvailabilityZone'),
            "availability_zone_id": subnet.get('AvailabilityZoneId'),
            "available_ip_address_count": subnet.get('AvailableIpAddressCount'),
            "state": subnet.get('State'),
            "map_public_ip_on_launch": subnet.get('MapPublicIpOnLaunch', False),
            "map_customer_owned_ip_on_launch": subnet.get('MapCustomerOwnedIpOnLaunch', False),
            "customer_owned_ipv4_pool": subnet.get('CustomerOwnedIpv4Pool'),
            "default_for_az": subnet.get('DefaultForAz', False),
            "ipv6_cidr_block_association_set": subnet.get('Ipv6CidrBlockAssociationSet', []),
            "assign_ipv6_address_on_creation": subnet.get('AssignIpv6AddressOnCreation', False),
            "tags": subnet.get('Tags', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "subnet_id": subnet_id})


@tool
def get_security_group_config(security_group_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get security group configuration and rules.
    
    Args:
        security_group_id: The security group ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with security group configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_security_groups(GroupIds=[security_group_id])
        sg = response['SecurityGroups'][0]
        
        config = {
            "security_group_id": sg.get('GroupId'),
            "group_name": sg.get('GroupName'),
            "description": sg.get('Description'),
            "vpc_id": sg.get('VpcId'),
            "owner_id": sg.get('OwnerId'),
            "ip_permissions": sg.get('IpPermissions', []),
            "ip_permissions_egress": sg.get('IpPermissionsEgress', []),
            "tags": sg.get('Tags', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "security_group_id": security_group_id})


@tool
def get_network_interface_config(network_interface_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get network interface (ENI) configuration.
    
    Args:
        network_interface_id: The network interface ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with network interface configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_network_interfaces(NetworkInterfaceIds=[network_interface_id])
        eni = response['NetworkInterfaces'][0]
        
        config = {
            "network_interface_id": eni.get('NetworkInterfaceId'),
            "subnet_id": eni.get('SubnetId'),
            "vpc_id": eni.get('VpcId'),
            "availability_zone": eni.get('AvailabilityZone'),
            "description": eni.get('Description', ''),
            "owner_id": eni.get('OwnerId'),
            "requester_id": eni.get('RequesterId'),
            "requester_managed": eni.get('RequesterManaged', False),
            "status": eni.get('Status'),
            "mac_address": eni.get('MacAddress'),
            "private_ip_address": eni.get('PrivateIpAddress'),
            "private_dns_name": eni.get('PrivateDnsName'),
            "source_dest_check": eni.get('SourceDestCheck'),
            "groups": eni.get('Groups', []),
            "attachment": eni.get('Attachment', {}),
            "association": eni.get('Association', {}),
            "tag_set": eni.get('TagSet', []),
            "private_ip_addresses": eni.get('PrivateIpAddresses', []),
            "ipv6_addresses": eni.get('Ipv6Addresses', []),
            "interface_type": eni.get('InterfaceType')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "network_interface_id": network_interface_id})


@tool
def get_nat_gateway_config(nat_gateway_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get NAT Gateway configuration.
    
    Args:
        nat_gateway_id: The NAT Gateway ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with NAT Gateway configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_nat_gateways(NatGatewayIds=[nat_gateway_id])
        nat_gw = response['NatGateways'][0]
        
        config = {
            "nat_gateway_id": nat_gw.get('NatGatewayId'),
            "vpc_id": nat_gw.get('VpcId'),
            "subnet_id": nat_gw.get('SubnetId'),
            "state": nat_gw.get('State'),
            "create_time": str(nat_gw.get('CreateTime')),
            "delete_time": str(nat_gw.get('DeleteTime')) if nat_gw.get('DeleteTime') else None,
            "nat_gateway_addresses": nat_gw.get('NatGatewayAddresses', []),
            "tags": nat_gw.get('Tags', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "nat_gateway_id": nat_gateway_id})


@tool
def get_internet_gateway_config(igw_id: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get Internet Gateway configuration.
    
    Args:
        igw_id: The Internet Gateway ID
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with Internet Gateway configuration
    """
    import boto3
    
    try:
        client = boto3.client('ec2', region_name=region)
        
        response = client.describe_internet_gateways(InternetGatewayIds=[igw_id])
        igw = response['InternetGateways'][0]
        
        config = {
            "internet_gateway_id": igw.get('InternetGatewayId'),
            "owner_id": igw.get('OwnerId'),
            "attachments": igw.get('Attachments', []),
            "tags": igw.get('Tags', [])
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "igw_id": igw_id})
