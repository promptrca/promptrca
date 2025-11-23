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
import json
from typing import Dict, Any, List, Optional
from ..utils import get_logger
from ..utils.config import get_aws_knowledge_mcp_config

logger = get_logger(__name__)

# Try to import MCP client if available
try:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client, create_mcp_http_client
    MCP_AVAILABLE = True
except ImportError:
    try:
        # Fallback: try SSE client
        from mcp.client.sse import sse_client
        MCP_AVAILABLE = True
    except ImportError:
        MCP_AVAILABLE = False
        logger.debug("MCP library HTTP transport not available - using direct HTTP calls")


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
        
        # Try using MCP protocol first if available
        if MCP_AVAILABLE:
            try:
                return self._search_via_mcp_protocol(query, max_results)
            except Exception as e:
                logger.warning(f"MCP protocol search failed, falling back to HTTP: {e}")
        
        # Fallback to HTTP (may not work, but graceful degradation)
        try:
            logger.info(f"Searching AWS documentation via HTTP: '{query}'")
            
            # Try AWS Knowledge MCP HTTP API (if it exists)
            # Note: The HTTP endpoint may not be available
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_documentation",
                    "arguments": {
                        "search_phrase": query,
                        "limit": max_results
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
            
            # Check for error response
            if "error" in data:
                logger.warning(f"MCP HTTP API error: {data.get('error', {}).get('message', 'Unknown error')}")
                return []
            
            # Extract results from MCP response
            if "result" in data:
                result = data["result"]
                # Try different response formats
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list):
                        results = []
                        for item in content[:max_results]:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    results.append({
                                        "text": item.get("text", ""),
                                        "type": "search_result"
                                    })
                        if results:
                            logger.info(f"Found {len(results)} AWS documentation results")
                            return results
                
                # Try alternative format with direct result list
                if isinstance(result, list):
                    results = []
                    for item in result[:max_results]:
                        if isinstance(item, dict):
                            results.append({
                                "text": f"{item.get('title', '')}: {item.get('context', '')}",
                                "url": item.get("url", ""),
                                "type": "search_result"
                            })
                    if results:
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
    
    def _search_via_mcp_protocol(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search using MCP protocol over Streamable HTTP (SSE)."""
        try:
            # AWS Knowledge MCP Server uses Streamable HTTP transport
            # Reference: https://awslabs.github.io/mcp/servers/aws-knowledge-mcp-server
            import asyncio
            
            async def _async_search():
                try:
                    # Try streamable HTTP client first (preferred for AWS Knowledge MCP)
                    from mcp.client.streamable_http import streamablehttp_client
                    
                    async with streamablehttp_client(url=self.url, timeout=self.timeout) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            
                            # Call the search_documentation tool
                            # According to AWS docs, tool name is "search_documentation"
                            result = await session.call_tool(
                                "search_documentation",
                                {
                                    "search_phrase": query,
                                    "limit": max_results
                                }
                            )
                            
                            # Parse MCP response - result.content is a list of content blocks
                            if result and result.content:
                                results = []
                                for content_block in result.content:
                                    if hasattr(content_block, 'text') and content_block.text:
                                        text = content_block.text
                                        # The response might be JSON string with search results
                                        try:
                                            data = json.loads(text)
                                            # AWS Knowledge MCP returns results in content.result format
                                            if isinstance(data, dict) and "content" in data:
                                                content_data = data["content"]
                                                if isinstance(content_data, dict) and "result" in content_data:
                                                    for item in content_data["result"]:
                                                        results.append({
                                                            "text": f"{item.get('title', '')}: {item.get('context', '')}",
                                                            "url": item.get("url", ""),
                                                            "type": "search_result"
                                                        })
                                            elif isinstance(data, list):
                                                for item in data:
                                                    results.append({
                                                        "text": f"{item.get('title', '')}: {item.get('context', '')}",
                                                        "url": item.get("url", ""),
                                                        "type": "search_result"
                                                    })
                                        except (json.JSONDecodeError, AttributeError):
                                            # If not JSON, use as plain text
                                            results.append({
                                                "text": str(text),
                                                "type": "search_result"
                                            })
                                
                                if results:
                                    logger.info(f"Found {len(results)} AWS documentation results via MCP")
                                    return results[:max_results]
                                    
                except ImportError:
                    # Fallback to SSE client if streamable HTTP not available
                    try:
                        from mcp.client.sse import sse_client
                        # SSE client might need different parameters
                        logger.debug("Streamable HTTP not available, trying SSE client")
                    except ImportError:
                        pass
                except Exception as e:
                    logger.debug(f"MCP streamable HTTP client error: {e}")
                
                return []
            
            # Run async function
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an async context, we can't use get_event_loop()
                    logger.debug("Already in async context, skipping MCP protocol")
                    return []
                else:
                    return loop.run_until_complete(_async_search())
            except RuntimeError:
                # No event loop, create new one
                return asyncio.run(_async_search())
                
        except Exception as e:
            logger.debug(f"MCP protocol search failed: {e}")
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
        
        # Try using MCP protocol first if available
        if MCP_AVAILABLE:
            try:
                return self._read_via_mcp_protocol(url)
            except Exception as e:
                logger.warning(f"MCP protocol read failed, falling back to HTTP: {e}")
        
        # Fallback to HTTP (may not work, but graceful degradation)
        try:
            logger.info(f"Reading AWS documentation via HTTP: {url}")
            
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
            
            # Check for error response
            if "error" in data:
                logger.warning(f"MCP HTTP API error: {data.get('error', {}).get('message', 'Unknown error')}")
                return ""
            
            # Extract content from MCP response
            if "result" in data:
                result = data["result"]
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and len(content) > 0:
                        first_item = content[0]
                        if isinstance(first_item, dict) and first_item.get("type") == "text":
                            doc_content = first_item.get("text", "")
                            logger.info(f"Retrieved AWS documentation ({len(doc_content)} chars)")
                            return doc_content
                    elif isinstance(content, str):
                        logger.info(f"Retrieved AWS documentation ({len(content)} chars)")
                        return content
            
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
    
    def _read_via_mcp_protocol(self, url: str) -> str:
        """Read documentation using MCP protocol over Streamable HTTP (SSE)."""
        try:
            import asyncio
            
            async def _async_read():
                try:
                    # Use streamable HTTP client for AWS Knowledge MCP
                    from mcp.client.streamable_http import streamablehttp_client
                    
                    async with streamablehttp_client(url=self.url, timeout=self.timeout) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            
                            result = await session.call_tool(
                                "read_documentation",
                                {"url": url}
                            )
                            
                            if result and result.content:
                                # Extract markdown content from content blocks
                                for content_block in result.content:
                                    if hasattr(content_block, 'text') and content_block.text:
                                        content = content_block.text
                                        if content:
                                            logger.info(f"Retrieved AWS documentation via MCP ({len(content)} chars)")
                                            return content
                except ImportError:
                    # Fallback to SSE if streamable HTTP not available
                    logger.debug("Streamable HTTP not available for read")
                except Exception as e:
                    logger.debug(f"MCP streamable HTTP client error: {e}")
                
                return ""
            
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    logger.debug("Already in async context, skipping MCP protocol")
                    return ""
                else:
                    return loop.run_until_complete(_async_read())
            except RuntimeError:
                return asyncio.run(_async_read())
                
        except Exception as e:
            logger.debug(f"MCP protocol read failed: {e}")
            return ""


# Global client instance (lazy initialized)
_mcp_client: Optional[AWSKnowledgeMCPClient] = None


def get_mcp_client() -> AWSKnowledgeMCPClient:
    """Get or create global AWS Knowledge MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = AWSKnowledgeMCPClient()
    return _mcp_client

