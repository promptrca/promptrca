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

Contact: info@promptrca.com

"""

import requests
from typing import Dict, Any, List, Optional
from ..utils import get_logger
from ..utils.config import get_aws_knowledge_mcp_config

logger = get_logger(__name__)


class AWSKnowledgeMCPClient:
    """
    Client for AWS Knowledge MCP Server.
    
    Provides access to official AWS documentation, IAM permission requirements,
    integration patterns, and best practices via the AWS Knowledge MCP server.
    """

    def __init__(self, url: Optional[str] = None, timeout: Optional[int] = None):
        """
        Initialize AWS Knowledge MCP client.
        
        Args:
            url: MCP server URL (default: from config or https://knowledge-mcp.global.api.aws)
            timeout: Request timeout in seconds (default: from config or 30)
        """
        config = get_aws_knowledge_mcp_config()
        self.url = url or config["url"]
        self.timeout = timeout or config["timeout"]
        self.enabled = config["enabled"]
        
        if not self.enabled:
            logger.info("AWS Knowledge MCP is disabled")
    
    def search_documentation(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search AWS documentation for integration patterns, permissions, and best practices.
        
        Args:
            query: Search query (e.g., "API Gateway invoke Step Functions IAM permissions")
            max_results: Maximum number of results to return (default: 5)
            
        Returns:
            List of search results with title, snippet, and URL
            Returns empty list on failure (graceful degradation)
        """
        if not self.enabled:
            logger.debug("AWS Knowledge MCP disabled, skipping search")
            return []
        
        try:
            logger.info(f"Searching AWS documentation: '{query}'")
            
            # MCP protocol: tools/call with search_documentation tool
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_documentation",
                    "arguments": {
                        "query": query
                    }
                }
            }
            
            response = requests.post(
                f"{self.url}/mcp/v1",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract results from MCP response
            if "result" in data and "content" in data["result"]:
                content = data["result"]["content"]
                if isinstance(content, list):
                    # Parse MCP content blocks
                    results = []
                    for item in content[:max_results]:
                        if isinstance(item, dict) and item.get("type") == "text":
                            # MCP returns text content with embedded metadata
                            results.append({
                                "text": item.get("text", ""),
                                "type": "search_result"
                            })
                    
                    logger.info(f"Found {len(results)} AWS documentation results")
                    return results
            
            logger.warning("No results found in MCP response")
            return []
            
        except requests.exceptions.Timeout:
            logger.warning(f"AWS Knowledge MCP search timed out after {self.timeout}s")
            return []
        except requests.exceptions.RequestException as e:
            logger.warning(f"AWS Knowledge MCP search failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching AWS documentation: {e}")
            return []
    
    def read_documentation(self, url: str) -> str:
        """
        Read full AWS documentation page as markdown.
        
        Args:
            url: AWS documentation URL to read
            
        Returns:
            Documentation content as markdown string
            Returns empty string on failure (graceful degradation)
        """
        if not self.enabled:
            logger.debug("AWS Knowledge MCP disabled, skipping read")
            return ""
        
        try:
            logger.info(f"Reading AWS documentation: {url}")
            
            # MCP protocol: tools/call with read_documentation tool
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "read_documentation",
                    "arguments": {
                        "url": url
                    }
                }
            }
            
            response = requests.post(
                f"{self.url}/mcp/v1",
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract content from MCP response
            if "result" in data and "content" in data["result"]:
                content = data["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    first_item = content[0]
                    if isinstance(first_item, dict) and first_item.get("type") == "text":
                        doc_content = first_item.get("text", "")
                        logger.info(f"Retrieved AWS documentation ({len(doc_content)} chars)")
                        return doc_content
            
            logger.warning("No content found in MCP response")
            return ""
            
        except requests.exceptions.Timeout:
            logger.warning(f"AWS Knowledge MCP read timed out after {self.timeout}s")
            return ""
        except requests.exceptions.RequestException as e:
            logger.warning(f"AWS Knowledge MCP read failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"Unexpected error reading AWS documentation: {e}")
            return ""


# Global client instance (lazy initialized)
_mcp_client: Optional[AWSKnowledgeMCPClient] = None


def get_mcp_client() -> AWSKnowledgeMCPClient:
    """Get or create global AWS Knowledge MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = AWSKnowledgeMCPClient()
    return _mcp_client

