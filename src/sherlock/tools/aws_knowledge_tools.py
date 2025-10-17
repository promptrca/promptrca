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

AWS Knowledge MCP Tools - Integration with AWS Knowledge MCP Server
Provides access to official AWS documentation, best practices, and regional availability.
"""

from strands import tool
from typing import Dict, Any, Optional
import json
import asyncio
import httpx
from ..utils.config import get_mcp_config
from ..utils import get_logger

logger = get_logger(__name__)


async def _call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call AWS Knowledge MCP Server tool.
    
    Args:
        tool_name: Name of the MCP tool to call
        arguments: Arguments to pass to the tool
    
    Returns:
        Dict containing the response or error information
    """
    config = get_mcp_config()
    
    if not config["enabled"]:
        return {"error": "AWS Knowledge MCP is disabled", "tool": tool_name}
    
    try:
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                config["server_url"],
                json={
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }
            )
            
            if response.status_code == 429:
                # Rate limited
                return {
                    "error": "Rate limited by AWS Knowledge MCP server",
                    "tool": tool_name,
                    "retry_after": response.headers.get("Retry-After", "unknown")
                }
            elif response.status_code != 200:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "tool": tool_name
                }
            
            return response.json()
            
    except httpx.TimeoutException:
        return {
            "error": f"Timeout after {config['timeout']} seconds",
            "tool": tool_name
        }
    except httpx.ConnectError:
        return {
            "error": "Unable to connect to AWS Knowledge MCP server",
            "tool": tool_name
        }
    except Exception as e:
        return {
            "error": f"Unexpected error: {str(e)}",
            "tool": tool_name
        }


@tool
def search_aws_documentation(query: str) -> str:
    """
    Search AWS documentation for relevant information.
    
    Args:
        query: Search query for AWS documentation, blogs, best practices
    
    Returns:
        JSON string with search results from AWS documentation
    """
    try:
        result = asyncio.run(_call_mcp_tool("search_documentation", {"query": query}))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in search_aws_documentation: {e}")
        return json.dumps({"error": str(e), "query": query})


@tool
def read_aws_documentation(url: str) -> str:
    """
    Read and convert AWS documentation page to markdown.
    
    Args:
        url: URL of the AWS documentation page to read
    
    Returns:
        JSON string with markdown content of the documentation page
    """
    try:
        result = asyncio.run(_call_mcp_tool("read_documentation", {"url": url}))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in read_aws_documentation: {e}")
        return json.dumps({"error": str(e), "url": url})


@tool
def get_aws_documentation_recommendations(topic: str) -> str:
    """
    Get content recommendations for AWS documentation pages.
    
    Args:
        topic: Topic to get recommendations for
    
    Returns:
        JSON string with recommended AWS documentation content
    """
    try:
        result = asyncio.run(_call_mcp_tool("recommend", {"topic": topic}))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in get_aws_documentation_recommendations: {e}")
        return json.dumps({"error": str(e), "topic": topic})


@tool
def list_aws_regions() -> str:
    """
    Retrieve a list of all AWS regions, including their identifiers and names.
    
    Returns:
        JSON string with list of AWS regions and their details
    """
    try:
        result = asyncio.run(_call_mcp_tool("list_regions", {}))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in list_aws_regions: {e}")
        return json.dumps({"error": str(e)})


@tool
def get_service_regional_availability(service: str, region: str = None) -> str:
    """
    Retrieve AWS regional availability information for SDK service APIs and CloudFormation resources.
    
    Args:
        service: AWS service name (e.g., 'lambda', 'dynamodb', 's3')
        region: AWS region to check (optional, checks all regions if not provided)
    
    Returns:
        JSON string with regional availability information for the service
    """
    try:
        arguments = {"service": service}
        if region:
            arguments["region"] = region
            
        result = asyncio.run(_call_mcp_tool("get_regional_availability", arguments))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Error in get_service_regional_availability: {e}")
        return json.dumps({"error": str(e), "service": service, "region": region})
