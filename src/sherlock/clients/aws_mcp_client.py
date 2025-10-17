"""
AWS API MCP Server Client

This module provides a client for communicating with the AWS API MCP Server
in read-only mode as a fallback for investigating uncommon AWS services.
"""

import json
import time
from typing import Dict, Any, Optional, List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..utils.config import get_aws_mcp_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AWSMCPClientError(Exception):
    """Custom exception for AWS MCP client errors."""
    pass


class AWSMCPClient:
    """Client for AWS API MCP Server (read-only)."""
    
    def __init__(self, server_url: str, timeout: int = 30):
        """
        Initialize AWS MCP client.
        
        Args:
            server_url: URL of the AWS API MCP server
            timeout: Request timeout in seconds
        """
        self.server_url = server_url
        self.timeout = timeout
        self.config = get_aws_mcp_config()
        
        # Create HTTP client with connection pooling
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )
        
        logger.info(f"Initialized AWS MCP client for server: {server_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(httpx.RequestError)
    )
    async def call_aws(self, service: str, operation: str, 
                      parameters: Dict[str, Any], 
                      region: Optional[str] = None,
                      query: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute AWS CLI command via MCP server.
        
        Args:
            service: AWS service name (e.g., 'backup', 'config')
            operation: Operation name (e.g., 'describe-backup-vault')
            parameters: Operation parameters
            region: AWS region (optional)
            query: JMESPath query to filter output (optional)
        
        Returns:
            Dict containing the operation results
            
        Raises:
            AWSMCPClientError: If the operation fails
        """
        start_time = time.time()
        
        try:
            # Validate service against allowlist
            if not self._is_service_allowed(service):
                raise AWSMCPClientError(f"Service '{service}' not in allowlist")
            
            # Validate operation against read-only patterns
            if not self._is_operation_allowed(operation):
                raise AWSMCPClientError(f"Operation '{operation}' not allowed (write operation)")
            
            # Construct AWS CLI command
            cli_command = self._build_cli_command(service, operation, parameters, region)
            
            # Call MCP server
            response = await self._call_mcp_server(cli_command)
            
            # Apply JMESPath query if provided
            if query:
                response = self._apply_jmespath_query(response, query)
            
            # Apply output size limits
            response = self._apply_output_limits(response)
            
            duration = time.time() - start_time
            logger.info(f"AWS MCP call completed: {service} {operation} in {duration:.2f}s")
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"AWS MCP call failed: {service} {operation} after {duration:.2f}s - {str(e)}")
            raise AWSMCPClientError(f"Failed to execute AWS command: {str(e)}")
    
    def _is_service_allowed(self, service: str) -> bool:
        """Check if service is in the allowlist."""
        allowed_services = set(self.config.get("allowed_services", []))
        return service in allowed_services
    
    def _is_operation_allowed(self, operation: str) -> bool:
        """Check if operation is read-only."""
        read_only_patterns = ['describe-', 'list-', 'get-', 'query-', 'show-']
        return any(operation.startswith(pattern) for pattern in read_only_patterns)
    
    def _build_cli_command(self, service: str, operation: str, 
                          parameters: Dict[str, Any], region: Optional[str]) -> str:
        """Build AWS CLI command string."""
        cmd_parts = ['aws', service, operation]
        
        # Add region if specified
        if region:
            cmd_parts.extend(['--region', region])
        
        # Add parameters
        for key, value in parameters.items():
            if value is not None:
                if isinstance(value, bool):
                    if value:
                        cmd_parts.append(f'--{key}')
                elif isinstance(value, (list, dict)):
                    cmd_parts.extend([f'--{key}', json.dumps(value)])
                else:
                    cmd_parts.extend([f'--{key}', str(value)])
        
        # Always request JSON output
        cmd_parts.extend(['--output', 'json'])
        
        return ' '.join(cmd_parts)
    
    async def _call_mcp_server(self, cli_command: str) -> Dict[str, Any]:
        """Call the MCP server with the CLI command."""
        try:
            response = await self.client.post(
                self.server_url,
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "call_aws",
                        "arguments": {
                            "command": cli_command
                        }
                    }
                }
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract the actual result from MCP response
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    return json.loads(content[0]["text"])
                else:
                    return {"error": "No content in MCP response"}
            else:
                return {"error": "Invalid MCP response format"}
                
        except httpx.HTTPStatusError as e:
            raise AWSMCPClientError(f"MCP server returned HTTP {e.response.status_code}: {e.response.text}")
        except httpx.RequestError as e:
            raise AWSMCPClientError(f"Request to MCP server failed: {str(e)}")
        except json.JSONDecodeError as e:
            raise AWSMCPClientError(f"Failed to parse MCP response: {str(e)}")
    
    def _apply_jmespath_query(self, data: Dict[str, Any], query: str) -> Dict[str, Any]:
        """Apply JMESPath query to filter the response."""
        try:
            import jmespath
            filtered = jmespath.search(query, data)
            return {"filtered_result": filtered, "query": query}
        except ImportError:
            logger.warning("JMESPath not available, returning unfiltered data")
            return data
        except Exception as e:
            logger.warning(f"JMESPath query failed: {str(e)}, returning unfiltered data")
            return data
    
    def _apply_output_limits(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply output size and pagination limits."""
        max_bytes = self.config.get("max_output_bytes", 10485760)  # 10MB
        max_pages = self.config.get("max_list_pages", 10)
        
        # Convert to JSON to check size
        json_str = json.dumps(data)
        if len(json_str) > max_bytes:
            logger.warning(f"Output size {len(json_str)} exceeds limit {max_bytes}, truncating")
            # Truncate large responses
            truncated_data = {
                "truncated": True,
                "original_size": len(json_str),
                "max_size": max_bytes,
                "data": json.loads(json_str[:max_bytes])
            }
            return truncated_data
        
        # Apply pagination limits for list operations
        if isinstance(data, dict) and "Contents" in data:
            # S3 list operations
            contents = data.get("Contents", [])
            if len(contents) > max_pages * 1000:  # Assume 1000 items per page
                data["Contents"] = contents[:max_pages * 1000]
                data["truncated"] = True
                data["max_pages"] = max_pages
        
        return data


# Global client instance (lazy initialization)
_mcp_client: Optional[AWSMCPClient] = None


async def get_mcp_client() -> Optional[AWSMCPClient]:
    """
    Get the global MCP client instance.
    
    Returns:
        AWSMCPClient instance or None if MCP is disabled
    """
    global _mcp_client
    
    config = get_aws_mcp_config()
    if not config.get("enabled", False):
        return None
    
    if _mcp_client is None:
        server_url = config.get("server_url", "http://localhost:8000/mcp")
        timeout = config.get("timeout", 30)
        _mcp_client = AWSMCPClient(server_url, timeout)
    
    return _mcp_client


async def close_mcp_client():
    """Close the global MCP client."""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
