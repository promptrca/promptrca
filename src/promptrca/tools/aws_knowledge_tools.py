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

from strands import tool
from ..clients.mcp_client import get_mcp_client


@tool
def search_aws_documentation(query: str) -> str:
    """
    Search official AWS documentation for integration patterns, IAM permissions, and best practices.
    
    Use this to find:
    - Required IAM permissions for service integrations
    - Trust policy requirements
    - Best practices for AWS service configurations
    - Integration patterns between AWS services
    - API parameters and error codes
    
    Args:
        query: Search query (e.g., "API Gateway invoke Step Functions IAM permissions")
    
    Returns:
        Formatted search results with documentation snippets and URLs
        Returns "Documentation unavailable" on failure
    
    Example queries:
        - "API Gateway invoke Step Functions permissions"
        - "Lambda execution role DynamoDB access"
        - "Step Functions IAM policy states:StartExecution"
    """
    try:
        mcp_client = get_mcp_client()
        results = mcp_client.search_documentation(query, max_results=5)
        
        if not results:
            return "Documentation unavailable - AWS Knowledge MCP search returned no results"
        
        # Format results for agent consumption
        formatted_results = []
        formatted_results.append(f"AWS Documentation Search Results for: '{query}'\n")
        formatted_results.append("=" * 80 + "\n")
        
        for idx, result in enumerate(results, 1):
            text = result.get("text", "")
            formatted_results.append(f"\n[Result {idx}]")
            formatted_results.append(text)
            formatted_results.append("\n" + "-" * 80)
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Documentation unavailable - Error searching AWS Knowledge: {str(e)}"


@tool
def read_aws_documentation(url: str) -> str:
    """
    Read full AWS documentation page as markdown.
    
    Use this to get detailed information from a specific AWS documentation URL
    found via search_aws_documentation.
    
    Args:
        url: AWS documentation URL (e.g., from search results)
    
    Returns:
        Full documentation content as markdown
        Returns "Documentation unavailable" on failure
    
    Example:
        After searching and finding a relevant doc URL, use this to read the full content
        for detailed IAM policy examples, API parameters, or configuration guides.
    """
    try:
        mcp_client = get_mcp_client()
        content = mcp_client.read_documentation(url)
        
        if not content:
            return f"Documentation unavailable - Could not read content from {url}"
        
        # Format for agent consumption
        formatted = []
        formatted.append(f"AWS Documentation: {url}\n")
        formatted.append("=" * 80 + "\n")
        formatted.append(content)
        
        return "\n".join(formatted)
        
    except Exception as e:
        return f"Documentation unavailable - Error reading AWS documentation: {str(e)}"
