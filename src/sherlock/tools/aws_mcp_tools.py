"""
AWS API MCP Fallback Tools

This module provides fallback tools for investigating AWS services
not yet covered by native boto3 tools using the AWS API MCP Server.
"""

import json
import time
from typing import Dict, Any, Optional
from strands import tool

from ..clients.aws_mcp_client import get_mcp_client, AWSMCPClientError
from ..utils.config import get_aws_mcp_config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Allowlist of services that can use MCP fallback
ALLOWED_SERVICES = {
    'backup', 'config', 'sso', 'organizations', 
    'resource-groups', 'servicecatalog', 'workspaces',
    'datasync', 'transfer', 'fsx', 'efs', 'backup-gateway',
    'cloudtrail', 'cloudformation', 'cloudwatch', 'logs',
    'secretsmanager', 'kms', 'acm', 'route53', 'cloudfront',
    'wafv2', 'shield', 'guardduty', 'securityhub', 'inspector2'
}

# Read-only operation patterns
READ_ONLY_OPERATIONS = {
    'describe-', 'list-', 'get-', 'query-', 'show-', 'search-',
    'scan-', 'inventory-', 'status-', 'health-', 'metrics-'
}


@tool
async def aws_mcp_read(service: str, operation: str, 
                      parameters_json: str, 
                      region: str = None,
                      query: str = None) -> str:
    """
    Execute AWS CLI read operation for services not covered by native tools.
    
    This tool provides fallback access to AWS services not yet covered by
    native boto3 tools. It should only be used when no native tool exists
    for the specific service and operation.
    
    Args:
        service: AWS service name (e.g., 'backup', 'config', 'sso')
        operation: Operation name (e.g., 'describe-backup-vault', 'list-backup-vaults')
        parameters_json: JSON string of operation parameters (e.g., '{"backupVaultName": "my-vault"}')
        region: AWS region (optional, uses default from configuration)
        query: JMESPath query to filter output (optional, e.g., 'BackupVaults[].BackupVaultName')
    
    Returns:
        JSON string with operation results or error information
        
    Examples:
        # List backup vaults
        aws_mcp_read('backup', 'list-backup-vaults', '{}')
        
        # Describe specific backup vault
        aws_mcp_read('backup', 'describe-backup-vault', '{"backupVaultName": "my-vault"}')
        
        # List with JMESPath filter
        aws_mcp_read('backup', 'list-backup-vaults', '{}', query='BackupVaults[].BackupVaultName')
    """
    start_time = time.time()
    
    try:
        # Validate service is in allowlist
        if service not in ALLOWED_SERVICES:
            error_msg = f"Service '{service}' not in MCP allowlist. Allowed services: {sorted(ALLOWED_SERVICES)}"
            logger.warning(error_msg)
            return json.dumps({
                "error": error_msg,
                "tool": "aws_mcp_read",
                "service": service,
                "operation": operation
            })
        
        # Validate operation is read-only
        if not any(operation.startswith(pattern) for pattern in READ_ONLY_OPERATIONS):
            error_msg = f"Operation '{operation}' not allowed. Only read-only operations permitted."
            logger.warning(error_msg)
            return json.dumps({
                "error": error_msg,
                "tool": "aws_mcp_read",
                "service": service,
                "operation": operation
            })
        
        # Parse parameters
        try:
            parameters = json.loads(parameters_json) if parameters_json else {}
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in parameters: {str(e)}"
            logger.warning(error_msg)
            return json.dumps({
                "error": error_msg,
                "tool": "aws_mcp_read",
                "service": service,
                "operation": operation
            })
        
        # Get MCP client
        mcp_client = await get_mcp_client()
        if not mcp_client:
            error_msg = "AWS MCP fallback is disabled"
            logger.warning(error_msg)
            return json.dumps({
                "error": error_msg,
                "tool": "aws_mcp_read",
                "service": service,
                "operation": operation
            })
        
        # Execute AWS command via MCP
        result = await mcp_client.call_aws(
            service=service,
            operation=operation,
            parameters=parameters,
            region=region,
            query=query
        )
        
        # Add metadata
        duration = time.time() - start_time
        result["_metadata"] = {
            "tool": "aws_mcp_read",
            "service": service,
            "operation": operation,
            "region": region or "default",
            "duration_seconds": round(duration, 2),
            "query_applied": query is not None
        }
        
        logger.info(f"AWS MCP fallback completed: {service} {operation} in {duration:.2f}s")
        return json.dumps(result, indent=2)
        
    except AWSMCPClientError as e:
        duration = time.time() - start_time
        error_result = {
            "error": str(e),
            "tool": "aws_mcp_read",
            "service": service,
            "operation": operation,
            "duration_seconds": round(duration, 2)
        }
        logger.error(f"AWS MCP fallback failed: {service} {operation} - {str(e)}")
        return json.dumps(error_result, indent=2)
        
    except Exception as e:
        duration = time.time() - start_time
        error_result = {
            "error": f"Unexpected error: {str(e)}",
            "tool": "aws_mcp_read",
            "service": service,
            "operation": operation,
            "duration_seconds": round(duration, 2)
        }
        logger.error(f"AWS MCP fallback unexpected error: {service} {operation} - {str(e)}")
        return json.dumps(error_result, indent=2)


@tool
async def aws_mcp_suggest_commands(natural_language_query: str) -> str:
    """
    Suggest AWS CLI commands based on a natural language query.
    
    This tool helps discover appropriate AWS CLI commands for investigating
    specific AWS services or resources.
    
    Args:
        natural_language_query: Natural language description of what you want to do
                               (e.g., "list all backup vaults", "check config rules")
    
    Returns:
        JSON string with suggested AWS CLI commands and their parameters
    """
    start_time = time.time()
    
    try:
        # Get MCP client
        mcp_client = await get_mcp_client()
        if not mcp_client:
            error_msg = "AWS MCP fallback is disabled"
            logger.warning(error_msg)
            return json.dumps({
                "error": error_msg,
                "tool": "aws_mcp_suggest_commands"
            })
        
        # Call MCP server for command suggestions
        try:
            response = await mcp_client.client.post(
                mcp_client.server_url,
                json={
                    "method": "tools/call",
                    "params": {
                        "name": "suggest_aws_commands",
                        "arguments": {
                            "query": natural_language_query
                        }
                    }
                }
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Extract suggestions from MCP response
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                if isinstance(content, list) and len(content) > 0:
                    suggestions = json.loads(content[0]["text"])
                else:
                    suggestions = {"error": "No suggestions in MCP response"}
            else:
                suggestions = {"error": "Invalid MCP response format"}
            
            # Add metadata
            duration = time.time() - start_time
            suggestions["_metadata"] = {
                "tool": "aws_mcp_suggest_commands",
                "query": natural_language_query,
                "duration_seconds": round(duration, 2)
            }
            
            logger.info(f"AWS MCP command suggestions completed in {duration:.2f}s")
            return json.dumps(suggestions, indent=2)
            
        except Exception as e:
            # Fallback: return basic suggestions based on query
            suggestions = _generate_fallback_suggestions(natural_language_query)
            duration = time.time() - start_time
            suggestions["_metadata"] = {
                "tool": "aws_mcp_suggest_commands",
                "query": natural_language_query,
                "duration_seconds": round(duration, 2),
                "fallback": True
            }
            logger.warning(f"Using fallback suggestions for query: {natural_language_query}")
            return json.dumps(suggestions, indent=2)
        
    except Exception as e:
        duration = time.time() - start_time
        error_result = {
            "error": f"Failed to get command suggestions: {str(e)}",
            "tool": "aws_mcp_suggest_commands",
            "query": natural_language_query,
            "duration_seconds": round(duration, 2)
        }
        logger.error(f"AWS MCP command suggestions failed: {str(e)}")
        return json.dumps(error_result, indent=2)


def _generate_fallback_suggestions(query: str) -> Dict[str, Any]:
    """Generate fallback command suggestions based on query keywords."""
    query_lower = query.lower()
    
    suggestions = {
        "query": query,
        "suggestions": []
    }
    
    # Common service patterns
    if "backup" in query_lower:
        suggestions["suggestions"].extend([
            {
                "command": "aws backup list-backup-vaults",
                "description": "List all backup vaults",
                "parameters": {}
            },
            {
                "command": "aws backup describe-backup-vault",
                "description": "Describe a specific backup vault",
                "parameters": {"backupVaultName": "vault-name"}
            }
        ])
    
    if "config" in query_lower:
        suggestions["suggestions"].extend([
            {
                "command": "aws config describe-config-rules",
                "description": "List all Config rules",
                "parameters": {}
            },
            {
                "command": "aws config describe-configuration-recorders",
                "description": "List configuration recorders",
                "parameters": {}
            }
        ])
    
    if "sso" in query_lower:
        suggestions["suggestions"].extend([
            {
                "command": "aws sso list-accounts",
                "description": "List SSO accounts",
                "parameters": {}
            },
            {
                "command": "aws sso list-permission-sets",
                "description": "List SSO permission sets",
                "parameters": {}
            }
        ])
    
    if not suggestions["suggestions"]:
        suggestions["suggestions"] = [
            {
                "command": "aws help",
                "description": "Get general AWS CLI help",
                "parameters": {}
            }
        ]
    
    return suggestions
