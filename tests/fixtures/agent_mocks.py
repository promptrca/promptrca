#!/usr/bin/env python3
"""
Reusable pytest fixtures for agent testing.

Provides mocked AWS clients, tool contexts, and specialist responses
for testing agents without requiring real AWS credentials.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import json
from unittest.mock import Mock, MagicMock
from typing import Dict, Any, List

from strands import ToolContext

from src.promptrca.models import Fact


# Mock AWS Client
def create_mock_aws_client(region: str = "us-east-1", account_id: str = "123456789012") -> Mock:
    """Create a mock AWS client for testing."""
    client = Mock()
    client.region = region
    client.account_id = account_id
    return client


# Mock Tool Context
def create_mock_tool_context(aws_client: Mock = None) -> Mock:
    """Create a mock ToolContext with AWS client."""
    if aws_client is None:
        aws_client = create_mock_aws_client()
    
    context = Mock(spec=ToolContext)
    context.invocation_state = {"aws_client": aws_client}
    return context


# Mock Specialist Facts
def create_mock_specialist_facts(source: str = "test_specialist", count: int = 2) -> List[Fact]:
    """Create sample fact data for specialists."""
    facts = []
    for i in range(count):
        facts.append(
            Fact(
                source=source,
                content=f"Test fact {i+1} from {source}",
                confidence=0.8 + (i * 0.1),
                metadata={"fact_index": i, "test": True}
            )
        )
    return facts


# Mock Trace Data
def create_mock_trace_data(trace_id: str = "1-67890123-abcdef1234567890abcdef12") -> Dict[str, Any]:
    """Create sample X-Ray trace data."""
    return {
        "TraceId": trace_id,
        "Duration": 1.234,
        "Segments": [
            {
                "Id": "segment-1",
                "Name": "test-function",
                "StartTime": 1234567890.0,
                "EndTime": 1234567891.0,
                "Http": {
                    "ResponseStatus": 200
                },
                "Aws": {
                    "function_name": "test-function",
                    "region": "us-east-1"
                }
            }
        ],
        "HasError": False,
        "HasFault": False,
        "HasThrottle": False
    }


# Mock Lambda Configuration
def create_mock_lambda_config(function_name: str = "test-function") -> Dict[str, Any]:
    """Create sample Lambda configuration."""
    return {
        "FunctionName": function_name,
        "FunctionArn": f"arn:aws:lambda:us-east-1:123456789012:function:{function_name}",
        "Runtime": "python3.11",
        "Role": "arn:aws:iam::123456789012:role/lambda-role",
        "Handler": "index.handler",
        "CodeSize": 1024,
        "Description": "Test function",
        "Timeout": 30,
        "MemorySize": 512,
        "LastModified": "2025-01-01T00:00:00.000Z",
        "CodeSha256": "abc123",
        "Version": "$LATEST",
        "Environment": {
            "Variables": {
                "ENV": "test"
            }
        }
    }


# Mock API Gateway Configuration
def create_mock_apigateway_config(api_id: str = "api-123", stage: str = "prod") -> Dict[str, Any]:
    """Create sample API Gateway configuration."""
    return {
        "id": api_id,
        "name": "test-api",
        "description": "Test API Gateway",
        "createdDate": "2025-01-01T00:00:00.000Z",
        "apiKeySource": "HEADER",
        "endpointConfiguration": {
            "types": ["REGIONAL"]
        },
        "stages": [
            {
                "stageName": stage,
                "deploymentId": "deployment-123",
                "createdDate": "2025-01-01T00:00:00.000Z",
                "lastUpdatedDate": "2025-01-01T00:00:00.000Z"
            }
        ]
    }


# Mock Step Functions Execution
def create_mock_stepfunctions_execution(
    execution_arn: str = "arn:aws:states:us-east-1:123456789012:execution:test-state-machine:exec-123"
) -> Dict[str, Any]:
    """Create sample Step Functions execution data."""
    return {
        "executionArn": execution_arn,
        "stateMachineArn": "arn:aws:states:us-east-1:123456789012:stateMachine:test-state-machine",
        "name": "exec-123",
        "status": "FAILED",
        "startDate": "2025-01-01T00:00:00.000Z",
        "stopDate": "2025-01-01T00:00:05.000Z",
        "input": json.dumps({"key": "value"}),
        "output": None,
        "error": "States.TaskFailed",
        "cause": "Lambda function error"
    }


# Mock Resource Data
def create_mock_resource_data(resource_type: str = "lambda", resource_name: str = "test-function") -> str:
    """Create sample resource data JSON string."""
    data = [{
        "type": resource_type,
        "name": resource_name,
        "region": "us-east-1"
    }]
    
    if resource_type == "lambda":
        data[0]["arn"] = f"arn:aws:lambda:us-east-1:123456789012:function:{resource_name}"
    elif resource_type == "apigateway":
        data[0]["id"] = resource_name
    elif resource_type == "stepfunctions":
        data[0]["arn"] = f"arn:aws:states:us-east-1:123456789012:stateMachine:{resource_name}"
    
    return json.dumps(data)


# Mock Investigation Context
def create_mock_investigation_context(
    trace_ids: List[str] = None,
    region: str = "us-east-1"
) -> str:
    """Create sample investigation context JSON string."""
    if trace_ids is None:
        trace_ids = ["1-67890123-abcdef1234567890abcdef12"]
    
    context = {
        "trace_ids": trace_ids,
        "region": region,
        "parsed_inputs": {
            "investigation_id": "test-123"
        }
    }
    
    return json.dumps(context)


# Mock Swarm Result
def create_mock_swarm_result(
    content: str = "Investigation completed successfully",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    cycles: List[Dict[str, Any]] = None
) -> Mock:
    """Create a mock Swarm execution result."""
    result = Mock()
    result.content = content
    result.accumulated_usage = {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens
    }
    
    if cycles is None:
        cycles = [
            {
                "agent": "trace_specialist",
                "content": "Trace analyzed",
                "tool_calls": [
                    {
                        "tool_name": "trace_specialist_tool",
                        "status": "success"
                    }
                ]
            }
        ]
    
    result.cycles = cycles
    return result
