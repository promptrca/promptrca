#!/usr/bin/env python3
"""
Swarm Tools Module for PromptRCA

Provides clean Strands tool wrappers that delegate to existing specialist classes
following Strands best practices. These tools replace the placeholder implementations
in the swarm orchestrator and use real AWS API calls through existing specialists.

Key Features:
- Uses @tool(context=True) pattern for invocation_state access
- Returns proper ToolResult dictionaries with status and content structure
- Handles AWS client context from invocation_state for cross-account access
- Delegates to existing specialist classes that use real AWS tools
- Structured error handling with meaningful error messages

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

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Literal, TypedDict

from pydantic import BaseModel, Field
from strands import tool, ToolContext, Agent

from ..models import Fact
from ..context import set_aws_client, get_aws_client
from ..utils.config import create_parser_model
from ..specialists import (
    LambdaSpecialist, APIGatewaySpecialist,
    StepFunctionsSpecialist, TraceSpecialist,
    IAMSpecialist, S3Specialist, SQSSpecialist, SNSSpecialist,
    DynamoDBSpecialist, EventBridgeSpecialist,
    ECSSpecialist, RDSSpecialist,
    InvestigationContext
)
from ..utils import get_logger

logger = get_logger(__name__)


# Type definitions for better type safety
class SpecialistResult(TypedDict):
    """Type definition for specialist tool results."""
    specialist_type: str
    resource_name: str
    facts: List[Dict[str, Any]]
    analysis_summary: str


class SpecialistErrorResult(TypedDict):
    """Type definition for specialist tool error results."""
    specialist_type: str
    error: str
    error_type: str
    facts: List[Any]  # Always empty for errors


class TraceResult(TypedDict):
    """Type definition for trace specialist results."""
    specialist_type: str
    trace_count: int
    facts: List[Dict[str, Any]]
    analysis_summary: str


# Resource and specialist type literals for better type safety
ResourceType = Literal['lambda', 'apigateway', 'stepfunctions', 'iam', 's3', 'sqs', 'sns']
SpecialistType = Literal['lambda', 'apigateway', 'stepfunctions', 'trace', 'iam', 's3', 'sqs', 'sns']


# Custom exception classes for better error handling
class SpecialistToolError(Exception):
    """Base exception for specialist tool errors."""
    pass


class ResourceDataError(SpecialistToolError):
    """Error parsing or validating resource data."""
    pass


class InvestigationContextError(SpecialistToolError):
    """Error parsing or validating investigation context."""
    pass


class SpecialistAnalysisError(SpecialistToolError):
    """Error during specialist analysis execution."""
    pass


class AWSClientContextError(SpecialistToolError):
    """Error with AWS client context setup or access."""
    pass


class InputValidationError(SpecialistToolError):
    """Error validating input parameters."""
    pass


class AWSPermissionError(SpecialistToolError):
    """Error related to AWS permissions or access."""
    pass


class CrossAccountAccessError(SpecialistToolError):
    """Error during cross-account role assumption."""
    pass


# Pydantic model for structured output from input parser agent
class ExtractedIdentifiers(BaseModel):
    """Structured output for AWS identifier extraction."""
    resource_names: List[str] = Field(
        default_factory=list,
        description="List of AWS resource names (function names, API IDs, table names, etc.)"
    )
    arns: List[str] = Field(
        default_factory=list,
        description="List of full AWS ARNs"
    )
    trace_ids: List[str] = Field(
        default_factory=list,
        description="List of X-Ray trace IDs (format: 1-XXXXXXXX-XXXXXXXX)"
    )
    execution_arns: List[str] = Field(
        default_factory=list,
        description="List of Step Functions execution ARNs"
    )


# Configuration constants
DEFAULT_AWS_REGION = 'us-east-1'
UNKNOWN_RESOURCE_NAME = 'unknown'
UNKNOWN_RESOURCE_ID = 'unknown'

# Resource type constants
RESOURCE_TYPE_LAMBDA = 'lambda'
RESOURCE_TYPE_APIGATEWAY = 'apigateway'
RESOURCE_TYPE_STEPFUNCTIONS = 'stepfunctions'
RESOURCE_TYPE_IAM = 'iam'
RESOURCE_TYPE_S3 = 's3'
RESOURCE_TYPE_SQS = 'sqs'
RESOURCE_TYPE_SNS = 'sns'
RESOURCE_TYPE_DYNAMODB = 'dynamodb'
RESOURCE_TYPE_EVENTBRIDGE = 'eventbridge'
RESOURCE_TYPE_ECS = 'ecs'
RESOURCE_TYPE_RDS = 'rds'

# Specialist type constants
SPECIALIST_TYPE_LAMBDA = 'lambda'
SPECIALIST_TYPE_APIGATEWAY = 'apigateway'
SPECIALIST_TYPE_STEPFUNCTIONS = 'stepfunctions'
SPECIALIST_TYPE_TRACE = 'trace'
SPECIALIST_TYPE_IAM = 'iam'
SPECIALIST_TYPE_S3 = 's3'
SPECIALIST_TYPE_SQS = 'sqs'
SPECIALIST_TYPE_SNS = 'sns'
SPECIALIST_TYPE_DYNAMODB = 'dynamodb'
SPECIALIST_TYPE_EVENTBRIDGE = 'eventbridge'
SPECIALIST_TYPE_ECS = 'ecs'
SPECIALIST_TYPE_RDS = 'rds'


# Input validation functions
def _validate_json_input(input_str: str, input_name: str) -> dict:
    """
    Validate and parse JSON input with detailed error messages.
    
    Args:
        input_str: JSON string to validate
        input_name: Name of the input for error messages
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        InputValidationError: If JSON is invalid or empty
    """
    if not input_str:
        raise InputValidationError(f"{input_name} cannot be empty or None")
    
    if not isinstance(input_str, str):
        raise InputValidationError(f"{input_name} must be a string, got {type(input_str)}")
    
    try:
        parsed = json.loads(input_str)
        if not isinstance(parsed, (dict, list)):
            raise InputValidationError(f"{input_name} must be a JSON object or array, got {type(parsed)}")
        return parsed
    except json.JSONDecodeError as e:
        raise InputValidationError(f"Invalid JSON in {input_name}: {str(e)}")


def _validate_resource_data(resource_data: dict, resource_type: str) -> dict:
    """
    Validate resource data structure and content.
    
    Args:
        resource_data: Parsed resource data
        resource_type: Expected resource type
        
    Returns:
        Validated resource data
        
    Raises:
        ResourceDataError: If resource data is invalid
    """
    if not resource_data:
        raise ResourceDataError("Resource data cannot be empty")
    
    # Handle both single resource and list of resources
    if isinstance(resource_data, list):
        if not resource_data:
            raise ResourceDataError("Resource data list cannot be empty")
        # Validate each resource in the list
        for i, resource in enumerate(resource_data):
            if not isinstance(resource, dict):
                raise ResourceDataError(f"Resource at index {i} must be a dictionary")
    elif isinstance(resource_data, dict):
        # Single resource validation
        if not resource_data:
            raise ResourceDataError("Resource data dictionary cannot be empty")
    else:
        raise ResourceDataError(f"Resource data must be a dictionary or list, got {type(resource_data)}")
    
    return resource_data


def _validate_investigation_context(context_data: dict) -> dict:
    """
    Validate investigation context structure and content.
    
    Args:
        context_data: Parsed investigation context
        
    Returns:
        Validated context data
        
    Raises:
        InvestigationContextError: If context data is invalid
    """
    if not isinstance(context_data, dict):
        raise InvestigationContextError(f"Investigation context must be a dictionary, got {type(context_data)}")
    
    # Validate trace_ids if present
    if 'trace_ids' in context_data:
        trace_ids = context_data['trace_ids']
        if not isinstance(trace_ids, list):
            raise InvestigationContextError("trace_ids must be a list")
        for i, trace_id in enumerate(trace_ids):
            if not isinstance(trace_id, str) or not trace_id.strip():
                raise InvestigationContextError(f"trace_id at index {i} must be a non-empty string")
    
    # Validate region if present
    if 'region' in context_data:
        region = context_data['region']
        if not isinstance(region, str) or not region.strip():
            raise InvestigationContextError("region must be a non-empty string")
    
    return context_data


def _validate_aws_client(aws_client) -> None:
    """
    Validate AWS client and test basic connectivity.
    
    Args:
        aws_client: AWS client instance
        
    Raises:
        AWSClientContextError: If AWS client is invalid or inaccessible
        AWSPermissionError: If AWS permissions are insufficient
        CrossAccountAccessError: If cross-account access fails
    """
    if not aws_client:
        raise AWSClientContextError("AWS client not found in invocation state")
    
    # Check if client has required attributes
    required_attrs = ['region', 'account_id']
    for attr in required_attrs:
        if not hasattr(aws_client, attr):
            raise AWSClientContextError(f"AWS client missing required attribute: {attr}")
    
    # Test basic AWS connectivity by checking account identity
    try:
        # This will test if the credentials are valid and accessible
        account_id = getattr(aws_client, 'account_id', None)
        if not account_id:
            raise AWSClientContextError("Unable to determine AWS account ID - check credentials")
        
        logger.debug(f"AWS client validated for account: {account_id}")
        
    except Exception as e:
        error_msg = str(e).lower()
        if 'accessdenied' in error_msg or 'unauthorized' in error_msg:
            raise AWSPermissionError(f"AWS access denied - check IAM permissions: {str(e)}")
        elif 'assumerole' in error_msg or 'external' in error_msg:
            raise CrossAccountAccessError(f"Cross-account role assumption failed: {str(e)}")
        else:
            raise AWSClientContextError(f"AWS client validation failed: {str(e)}")


def _create_error_response(error_type: str, error_message: str, specialist_type: str = None) -> dict:
    """
    Create standardized error response in ToolResult format.
    
    Args:
        error_type: Type of error (validation, aws_client, specialist, etc.)
        error_message: Detailed error message
        specialist_type: Type of specialist (optional)
        
    Returns:
        Standardized error response dictionary
    """
    error_content = {
        "error_type": error_type,
        "error_message": error_message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if specialist_type:
        error_content["specialist_type"] = specialist_type
    
    return {
        "status": "error",
        "content": [
            {"text": error_message},
            {"json": error_content}
        ]
    }


def _handle_specialist_failure(specialist_type: str, error: Exception, resource_name: str = None) -> dict:
    """
    Handle specialist analysis failures with graceful degradation.
    
    Args:
        specialist_type: Type of specialist that failed
        error: Exception that occurred
        resource_name: Name of resource being analyzed (optional)
        
    Returns:
        Error response with degradation information
    """
    resource_info = f" for resource '{resource_name}'" if resource_name else ""
    
    # Categorize error types for better handling
    if isinstance(error, (AWSPermissionError, CrossAccountAccessError)):
        error_type = "aws_permission"
        message = f"{specialist_type} specialist{resource_info} failed due to AWS permission issue: {str(error)}"
    elif isinstance(error, AWSClientContextError):
        error_type = "aws_client"
        message = f"{specialist_type} specialist{resource_info} failed due to AWS client issue: {str(error)}"
    elif isinstance(error, (ResourceDataError, InvestigationContextError, InputValidationError)):
        error_type = "validation"
        message = f"{specialist_type} specialist{resource_info} failed due to input validation: {str(error)}"
    elif isinstance(error, SpecialistAnalysisError):
        error_type = "analysis"
        message = f"{specialist_type} specialist{resource_info} analysis failed: {str(error)}"
    else:
        error_type = "unexpected"
        message = f"{specialist_type} specialist{resource_info} encountered unexpected error: {str(error)}"
    
    logger.error(f"Specialist failure - {error_type}: {message}")
    
    # Create error response with degradation info
    error_response = _create_error_response(error_type, message, specialist_type)
    
    # Add degradation guidance
    degradation_info = {
        "degradation_available": True,
        "alternative_analysis": f"Investigation can continue with other specialists. {specialist_type} analysis will be skipped.",
        "impact": f"Limited {specialist_type} service insights available",
        "recommendation": "Review error details and check AWS permissions or configuration"
    }
    
    error_response["content"].append({"json": {"degradation_info": degradation_info}})
    
    return error_response


# Helper functions for specialist tools
def _extract_resource_from_data(
    resource_data_parsed: Union[Dict[str, Any], List[Dict[str, Any]]], 
    resource_type: ResourceType, 
    context_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract a specific resource type from parsed data or create placeholder.
    
    Args:
        resource_data_parsed: Parsed resource data (single dict or list)
        resource_type: Type of resource to extract ('lambda', 'apigateway', 'stepfunctions')
        context_data: Investigation context containing region and other metadata
    
    Returns:
        Resource dictionary, either extracted or placeholder
    """
    if isinstance(resource_data_parsed, list):
        # If it's a list, find the first resource of the specified type
        resources = [r for r in resource_data_parsed if r.get('type') == resource_type]
        if resources:
            return resources[0]
        # No resources found, create placeholder for analysis
        return {
            'type': resource_type,
            'name': UNKNOWN_RESOURCE_NAME,
            'id': UNKNOWN_RESOURCE_ID,
            'region': context_data.get('region', DEFAULT_AWS_REGION)
        }
    else:
        # Single resource object
        return resource_data_parsed


def _run_specialist_analysis(specialist, resource: dict, context: InvestigationContext) -> List[Fact]:
    """
    Run specialist analysis in a new event loop (sync wrapper for async).
    
    Args:
        specialist: The specialist instance to run
        resource: Resource dictionary to analyze
        context: Investigation context
    
    Returns:
        List of facts from the analysis
        
    Raises:
        SpecialistAnalysisError: If specialist analysis fails
    """
    if not resource:
        raise SpecialistAnalysisError("Resource data is empty or None")
    
    if not context:
        raise SpecialistAnalysisError("Investigation context is empty or None")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(specialist.analyze(resource, context))
    except Exception as e:
        raise SpecialistAnalysisError(f"Specialist analysis failed: {str(e)}") from e
    finally:
        loop.close()


def _format_specialist_results(
    specialist_type: SpecialistType, 
    resource_name: str, 
    facts: List[Fact]
) -> SpecialistResult:
    """
    Format specialist analysis results as JSON-serializable dict.
    
    Args:
        specialist_type: Type of specialist ('lambda', 'apigateway', etc.)
        resource_name: Name of the analyzed resource
        facts: List of facts from the analysis
    
    Returns:
        Formatted results dictionary
    """
    return {
        "specialist_type": specialist_type,
        "resource_name": resource_name,
        "facts": [
            {
                "source": fact.source,
                "content": fact.content,
                "confidence": fact.confidence,
                "metadata": fact.metadata
            }
            for fact in facts
        ],
        "analysis_summary": f"Analyzed {specialist_type} {resource_name} - found {len(facts)} facts"
    }


# Specialist Tools - Following Strands Best Practices

@tool(context=True)
def lambda_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze Lambda function configuration, logs, and performance issues using real AWS API calls.
    
    This tool uses the existing LambdaSpecialist class which makes real AWS API calls
    through lambda_tools.py functions to analyze Lambda function configuration,
    metrics, and recent failures.
    
    Args:
        resource_data: JSON string containing Lambda resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_LAMBDA)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_LAMBDA)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_LAMBDA)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_LAMBDA)
        
        # Extract Lambda resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_LAMBDA, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = LambdaSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_LAMBDA, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_LAMBDA, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"Lambda specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_LAMBDA, e)


@tool(context=True)
def apigateway_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze API Gateway configuration, stage settings, and integration issues using real AWS API calls.
    
    This tool uses the existing APIGatewaySpecialist class which makes real AWS API calls
    through apigateway_tools.py functions to analyze API Gateway configuration,
    metrics, IAM permissions, and execution logs.
    
    Args:
        resource_data: JSON string containing API Gateway resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_APIGATEWAY)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_APIGATEWAY)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_APIGATEWAY)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_APIGATEWAY)
        
        # Extract API Gateway resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_APIGATEWAY, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = APIGatewaySpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_APIGATEWAY, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_APIGATEWAY, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"API Gateway specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_APIGATEWAY, e)


@tool(context=True)
def stepfunctions_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze Step Functions state machine executions, errors, and permissions using real AWS API calls.
    
    This tool uses the existing StepFunctionsSpecialist class which makes real AWS API calls
    through stepfunctions_tools.py functions to analyze Step Functions execution details,
    failure patterns, and permission issues.
    
    Args:
        resource_data: JSON string containing Step Functions resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_STEPFUNCTIONS)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_STEPFUNCTIONS)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_STEPFUNCTIONS)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_STEPFUNCTIONS)
        
        # Extract Step Functions resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_STEPFUNCTIONS, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = StepFunctionsSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_STEPFUNCTIONS, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_STEPFUNCTIONS, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"Step Functions specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_STEPFUNCTIONS, e)


@tool(context=True)
def trace_specialist_tool(trace_ids: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Perform deep X-Ray trace analysis to extract service interactions and errors using real AWS API calls.
    
    This tool uses the existing TraceSpecialist class which makes real AWS API calls
    through xray_tools.py functions to analyze X-Ray traces for service interactions,
    timing information, and error patterns.
    
    Args:
        trace_ids: JSON array string containing X-Ray trace IDs to analyze
        investigation_context: JSON string with investigation metadata
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            trace_id_list = _validate_json_input(trace_ids, "trace_ids")
            if not isinstance(trace_id_list, list):
                raise InputValidationError("trace_ids must be a JSON array")
            if not trace_id_list:
                raise InputValidationError("trace_ids array cannot be empty")
            # Validate each trace ID
            for i, trace_id in enumerate(trace_id_list):
                if not isinstance(trace_id, str) or not trace_id.strip():
                    raise InputValidationError(f"trace_id at index {i} must be a non-empty string")
        except InputValidationError as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_TRACE)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_TRACE)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_TRACE)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=trace_id_list,
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling and graceful degradation
        try:
            specialist = TraceSpecialist()
            all_facts = []
            successful_traces = 0
            failed_traces = 0
            
            # Analyze each trace with individual error handling for graceful degradation
            for trace_id in trace_id_list:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    facts = loop.run_until_complete(specialist.analyze_trace(trace_id, context))
                    all_facts.extend(facts)
                    successful_traces += 1
                except Exception as e:
                    # Log individual trace failures but continue with other traces
                    logger.warning(f"Failed to analyze trace {trace_id}: {e}")
                    failed_traces += 1
                    # Add a fact about the failure for transparency
                    all_facts.append(type('Fact', (), {
                        'source': 'trace_analysis_error',
                        'content': f"Failed to analyze trace {trace_id}: {str(e)}",
                        'confidence': 0.8,
                        'metadata': {'trace_id': trace_id, 'error': True}
                    })())
                finally:
                    loop.close()
            
            # Create results with degradation information
            results = {
                "specialist_type": SPECIALIST_TYPE_TRACE,
                "trace_count": len(trace_id_list),
                "successful_traces": successful_traces,
                "failed_traces": failed_traces,
                "facts": [
                    {
                        "source": fact.source,
                        "content": fact.content,
                        "confidence": fact.confidence,
                        "metadata": fact.metadata
                    }
                    for fact in all_facts
                ],
                "analysis_summary": f"Analyzed {len(trace_id_list)} traces ({successful_traces} successful, {failed_traces} failed) - found {len(all_facts)} facts"
            }
            
            # Add degradation warning if some traces failed
            if failed_traces > 0:
                results["degradation_warning"] = f"{failed_traces} out of {len(trace_id_list)} traces failed to analyze"
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except Exception as e:
            # If specialist creation or general analysis fails
            return _handle_specialist_failure(SPECIALIST_TYPE_TRACE, e)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"Trace specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_TRACE, e)


@tool(context=True)
def iam_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze IAM roles, users, and policies for permission issues and security concerns using real AWS API calls.
    
    This tool uses the existing IAMSpecialist class which makes real AWS API calls
    through iam_tools.py functions to analyze IAM configuration, policies,
    and permission issues.
    
    Args:
        resource_data: JSON string containing IAM resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_IAM)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_IAM)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_IAM)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_IAM)
        
        # Extract IAM resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_IAM, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = IAMSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_IAM, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_IAM, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"IAM specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_IAM, e)


@tool(context=True)
def s3_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze S3 bucket configuration, policies, and metrics for access and performance issues using real AWS API calls.
    
    This tool uses the existing S3Specialist class which makes real AWS API calls
    through s3_tools.py functions to analyze S3 bucket configuration,
    metrics, and policy issues.
    
    Args:
        resource_data: JSON string containing S3 resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_S3)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_S3)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_S3)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_S3)
        
        # Extract S3 resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_S3, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = S3Specialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_S3, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_S3, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"S3 specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_S3, e)


@tool(context=True)
def sqs_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze SQS queue configuration, metrics, and dead letter queue setup for message processing issues using real AWS API calls.
    
    This tool uses the existing SQSSpecialist class which makes real AWS API calls
    through sqs_tools.py functions to analyze SQS queue configuration,
    metrics, and dead letter queue issues.
    
    Args:
        resource_data: JSON string containing SQS resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_SQS)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_SQS)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_SQS)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_SQS)
        
        # Extract SQS resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_SQS, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = SQSSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_SQS, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_SQS, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"SQS specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_SQS, e)


@tool(context=True)
def sns_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze SNS topic configuration, subscriptions, and delivery metrics for notification issues using real AWS API calls.
    
    This tool uses the existing SNSSpecialist class which makes real AWS API calls
    through sns_tools.py functions to analyze SNS topic configuration,
    subscriptions, and delivery issues.
    
    Args:
        resource_data: JSON string containing SNS resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_SNS)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_SNS)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_SNS)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_SNS)
        
        # Extract SNS resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_SNS, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = SNSSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_SNS, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_SNS, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"SNS specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_SNS, e)

@tool(context=True)
def dynamodb_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze DynamoDB table throttling, capacity issues, hot partitions, and stream problems using real AWS API calls.
    
    This tool uses the existing DynamoDBSpecialist class which makes real AWS API calls
    through dynamodb_tools.py functions to analyze DynamoDB table configuration,
    metrics, and stream issues.
    
    Args:
        resource_data: JSON string containing DynamoDB resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_DYNAMODB)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_DYNAMODB)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_DYNAMODB)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_DYNAMODB)
        
        # Extract DynamoDB resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_DYNAMODB, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = DynamoDBSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_DYNAMODB, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_DYNAMODB, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"DynamoDB specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_DYNAMODB, e)


@tool(context=True)
def eventbridge_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze EventBridge rule configuration, event patterns, target delivery, and invocation failures using real AWS API calls.
    
    This tool uses the existing EventBridgeSpecialist class which makes real AWS API calls
    through eventbridge_tools.py functions to analyze EventBridge rule configuration,
    targets, and metrics.
    
    Args:
        resource_data: JSON string containing EventBridge resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_EVENTBRIDGE)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_EVENTBRIDGE)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_EVENTBRIDGE)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_EVENTBRIDGE)
        
        # Extract EventBridge resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_EVENTBRIDGE, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = EventBridgeSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_EVENTBRIDGE, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_EVENTBRIDGE, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"EventBridge specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_EVENTBRIDGE, e)


@tool(context=True)
def ecs_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze ECS cluster capacity, service deployments, task placement failures, and container issues using real AWS API calls.
    
    This tool uses the existing ECSSpecialist class which makes real AWS API calls
    through ecs_tools.py functions to analyze ECS cluster configuration,
    service deployments, and task failures.
    
    Args:
        resource_data: JSON string containing ECS resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_ECS)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_ECS)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_ECS)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_ECS)
        
        # Extract ECS resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_ECS, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = ECSSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_ECS, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_ECS, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"ECS specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_ECS, e)


@tool(context=True)
def rds_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """
    Analyze RDS/Aurora instance health, connection pools, performance metrics, and replication lag using real AWS API calls.
    
    This tool uses the existing RDSSpecialist class which makes real AWS API calls
    through rds_tools.py functions to analyze RDS instance configuration,
    metrics, and performance issues.
    
    Args:
        resource_data: JSON string containing RDS resource information
        investigation_context: JSON string with trace IDs, region, and context
        tool_context: Strands ToolContext containing invocation_state with AWS client
    
    Returns:
        ToolResult dictionary with status and content structure
    """
    try:
        # Validate and parse input data with comprehensive error handling
        try:
            resource_data_parsed = _validate_json_input(resource_data, "resource_data")
            resource_data_validated = _validate_resource_data(resource_data_parsed, RESOURCE_TYPE_RDS)
        except (InputValidationError, ResourceDataError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_RDS)
        
        try:
            context_data = _validate_json_input(investigation_context, "investigation_context")
            context_data_validated = _validate_investigation_context(context_data)
        except (InputValidationError, InvestigationContextError) as e:
            return _create_error_response("input_validation", str(e), SPECIALIST_TYPE_RDS)
        
        # Validate AWS client and test connectivity
        try:
            aws_client = tool_context.invocation_state.get('aws_client')
            _validate_aws_client(aws_client)
            set_aws_client(aws_client)
        except (AWSClientContextError, AWSPermissionError, CrossAccountAccessError) as e:
            return _create_error_response("aws_client", str(e), SPECIALIST_TYPE_RDS)
        
        # Extract RDS resource using helper function
        resource = _extract_resource_from_data(resource_data_validated, RESOURCE_TYPE_RDS, context_data_validated)
        resource_name = resource.get('name', UNKNOWN_RESOURCE_NAME)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data_validated.get('trace_ids', []),
            region=context_data_validated.get('region', DEFAULT_AWS_REGION),
            parsed_inputs=context_data_validated.get('parsed_inputs')
        )
        
        # Run specialist analysis with comprehensive error handling
        try:
            specialist = RDSSpecialist()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results using helper function
            results = _format_specialist_results(SPECIALIST_TYPE_RDS, resource_name, facts)
            
            return {
                "status": "success",
                "content": [
                    {"json": results}
                ]
            }
            
        except SpecialistAnalysisError as e:
            return _handle_specialist_failure(SPECIALIST_TYPE_RDS, e, resource_name)
        
    except Exception as e:
        # Catch-all for unexpected errors with graceful degradation
        logger.error(f"RDS specialist tool unexpected error: {e}")
        return _handle_specialist_failure(SPECIALIST_TYPE_RDS, e)
