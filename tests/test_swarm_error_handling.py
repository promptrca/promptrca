#!/usr/bin/env python3
"""
Unit tests for Swarm Orchestrator error handling improvements.

Tests the specific exception types and error handling logic
with realistic error scenarios.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock

from src.promptrca.core.swarm_orchestrator import (
    # Exception classes
    SpecialistToolError,
    ResourceDataError,
    InvestigationContextError,
    SpecialistAnalysisError,
    AWSClientContextError,
    
    # Helper functions
    _run_specialist_analysis,
    
    # Tools
    lambda_specialist_tool,
    apigateway_specialist_tool,
    stepfunctions_specialist_tool,
    trace_specialist_tool,
    
    # Constants
    SPECIALIST_TYPE_LAMBDA,
    SPECIALIST_TYPE_APIGATEWAY,
    SPECIALIST_TYPE_STEPFUNCTIONS,
    SPECIALIST_TYPE_TRACE
)
from src.promptrca.specialists import InvestigationContext


class TestExceptionHierarchy:
    """Test that custom exception classes are properly defined."""
    
    def test_specialist_tool_error_is_base_exception(self):
        """Test that SpecialistToolError is the base exception."""
        assert issubclass(SpecialistToolError, Exception)
        
        # Test instantiation
        error = SpecialistToolError("Test error")
        assert str(error) == "Test error"
    
    def test_specific_exceptions_inherit_from_base(self):
        """Test that specific exceptions inherit from SpecialistToolError."""
        specific_exceptions = [
            ResourceDataError,
            InvestigationContextError,
            SpecialistAnalysisError,
            AWSClientContextError
        ]
        
        for exception_class in specific_exceptions:
            assert issubclass(exception_class, SpecialistToolError)
            assert issubclass(exception_class, Exception)
            
            # Test instantiation
            error = exception_class("Test message")
            assert isinstance(error, SpecialistToolError)
            assert isinstance(error, Exception)
    
    def test_exception_messages_are_preserved(self):
        """Test that exception messages are properly preserved."""
        test_message = "This is a test error message"
        
        exceptions = [
            SpecialistToolError(test_message),
            ResourceDataError(test_message),
            InvestigationContextError(test_message),
            SpecialistAnalysisError(test_message),
            AWSClientContextError(test_message)
        ]
        
        for error in exceptions:
            assert str(error) == test_message


class TestRunSpecialistAnalysisErrorHandling:
    """Test error handling in the _run_specialist_analysis helper function."""
    
    def test_empty_resource_raises_specialist_analysis_error(self):
        """Test that empty resource raises SpecialistAnalysisError."""
        mock_specialist = Mock()
        mock_context = Mock()
        
        # Test with None resource
        with pytest.raises(SpecialistAnalysisError, match="Resource data is empty or None"):
            _run_specialist_analysis(mock_specialist, None, mock_context)
        
        # Test with empty dict resource
        with pytest.raises(SpecialistAnalysisError, match="Resource data is empty or None"):
            _run_specialist_analysis(mock_specialist, {}, mock_context)
    
    def test_empty_context_raises_specialist_analysis_error(self):
        """Test that empty context raises SpecialistAnalysisError."""
        mock_specialist = Mock()
        mock_resource = {"type": "lambda", "name": "test"}
        
        # Test with None context
        with pytest.raises(SpecialistAnalysisError, match="Investigation context is empty or None"):
            _run_specialist_analysis(mock_specialist, mock_resource, None)
    
    def test_specialist_analysis_exception_is_wrapped(self):
        """Test that specialist analysis exceptions are wrapped in SpecialistAnalysisError."""
        mock_specialist = Mock()
        mock_specialist.analyze = AsyncMock(side_effect=ValueError("Original error"))
        
        mock_resource = {"type": "lambda", "name": "test"}
        mock_context = Mock()
        
        with pytest.raises(SpecialistAnalysisError) as exc_info:
            _run_specialist_analysis(mock_specialist, mock_resource, mock_context)
        
        # Check that the original exception is preserved
        assert "Specialist analysis failed: Original error" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, ValueError)


class TestLambdaSpecialistToolErrorHandling:
    """Test error handling in the lambda_specialist_tool."""
    
    def test_invalid_resource_data_json_returns_error_response(self):
        """Test that invalid JSON in resource_data returns proper error response."""
        invalid_json = "invalid json data"
        valid_context = json.dumps({"region": "us-east-1", "trace_ids": []})
        
        result_json = lambda_specialist_tool(invalid_json, valid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_LAMBDA
        assert result["error_type"] == "ResourceDataError"
        assert "Invalid JSON in resource_data" in result["error"]
        assert result["facts"] == []
    
    def test_invalid_context_json_returns_error_response(self):
        """Test that invalid JSON in investigation_context returns proper error response."""
        valid_resource = json.dumps([{"type": "lambda", "name": "test"}])
        invalid_context = "invalid json context"
        
        result_json = lambda_specialist_tool(valid_resource, invalid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_LAMBDA
        assert result["error_type"] == "InvestigationContextError"
        assert "Invalid JSON in investigation_context" in result["error"]
        assert result["facts"] == []
    
    @patch('src.promptrca.core.swarm_orchestrator.LambdaSpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    def test_specialist_analysis_error_is_handled(self, mock_run_analysis, mock_specialist_class):
        """Test that SpecialistAnalysisError is properly handled."""
        # Setup mock to raise SpecialistAnalysisError
        mock_run_analysis.side_effect = SpecialistAnalysisError("Analysis failed")
        
        valid_resource = json.dumps([{"type": "lambda", "name": "test"}])
        valid_context = json.dumps({"region": "us-east-1", "trace_ids": []})
        
        result_json = lambda_specialist_tool(valid_resource, valid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_LAMBDA
        assert result["error_type"] == "SpecialistAnalysisError"
        assert "Analysis failed" in result["error"]
        assert result["facts"] == []
    
    @patch('src.promptrca.core.swarm_orchestrator.LambdaSpecialist')
    def test_unexpected_error_is_handled(self, mock_specialist_class):
        """Test that unexpected errors are properly handled."""
        # Setup mock to raise unexpected error
        mock_specialist_class.side_effect = RuntimeError("Unexpected runtime error")
        
        valid_resource = json.dumps([{"type": "lambda", "name": "test"}])
        valid_context = json.dumps({"region": "us-east-1", "trace_ids": []})
        
        result_json = lambda_specialist_tool(valid_resource, valid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_LAMBDA
        assert result["error_type"] == "UnexpectedError"
        assert "Unexpected error: Unexpected runtime error" in result["error"]
        assert result["facts"] == []


class TestAPIGatewaySpecialistToolErrorHandling:
    """Test error handling in the apigateway_specialist_tool."""
    
    def test_resource_data_error_handling(self):
        """Test ResourceDataError handling in API Gateway tool."""
        invalid_json = '{"invalid": json,}'
        valid_context = json.dumps({"region": "eu-west-1", "trace_ids": []})
        
        result_json = apigateway_specialist_tool(invalid_json, valid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_APIGATEWAY
        assert result["error_type"] == "ResourceDataError"
        assert "Invalid JSON in resource_data" in result["error"]
    
    def test_investigation_context_error_handling(self):
        """Test InvestigationContextError handling in API Gateway tool."""
        valid_resource = json.dumps([{"type": "apigateway", "name": "test-api"}])
        invalid_context = '{"region": "us-east-1", "trace_ids": [malformed}'
        
        result_json = apigateway_specialist_tool(valid_resource, invalid_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_APIGATEWAY
        assert result["error_type"] == "InvestigationContextError"
        assert "Invalid JSON in investigation_context" in result["error"]


class TestStepFunctionsSpecialistToolErrorHandling:
    """Test error handling in the stepfunctions_specialist_tool."""
    
    def test_consistent_error_handling_across_tools(self):
        """Test that all specialist tools handle errors consistently."""
        invalid_resource = "not json"
        valid_context = json.dumps({"region": "ap-southeast-1", "trace_ids": []})
        
        # Test all specialist tools with the same invalid input
        tools_and_types = [
            (lambda_specialist_tool, SPECIALIST_TYPE_LAMBDA),
            (apigateway_specialist_tool, SPECIALIST_TYPE_APIGATEWAY),
            (stepfunctions_specialist_tool, SPECIALIST_TYPE_STEPFUNCTIONS)
        ]
        
        for tool_func, expected_type in tools_and_types:
            result_json = tool_func(invalid_resource, valid_context)
            result = json.loads(result_json)
            
            # All tools should handle the error consistently
            assert result["specialist_type"] == expected_type
            assert result["error_type"] == "ResourceDataError"
            assert "Invalid JSON in resource_data" in result["error"]
            assert result["facts"] == []


class TestTraceSpecialistToolErrorHandling:
    """Test error handling in the trace_specialist_tool."""
    
    def test_missing_aws_client_raises_error(self):
        """Test that missing AWS client in invocation state raises AWSClientContextError."""
        from strands import ToolContext
        
        # Create mock tool context without AWS client
        mock_tool_context = Mock(spec=ToolContext)
        mock_tool_context.invocation_state = {}  # No AWS client
        
        valid_trace_ids = json.dumps(["1-abc123-def456"])
        valid_context = json.dumps({"region": "us-east-1"})
        
        result_json = trace_specialist_tool(valid_trace_ids, valid_context, mock_tool_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_TRACE
        assert result["error_type"] == "AWSClientContextError"
        assert "AWS client not found in invocation state" in result["error"]
    
    def test_invalid_trace_ids_json_handling(self):
        """Test that invalid JSON in trace_ids is handled properly."""
        from strands import ToolContext
        
        mock_tool_context = Mock(spec=ToolContext)
        mock_tool_context.invocation_state = {"aws_client": Mock()}
        
        invalid_trace_ids = "[invalid json"
        valid_context = json.dumps({"region": "us-east-1"})
        
        result_json = trace_specialist_tool(invalid_trace_ids, valid_context, mock_tool_context)
        result = json.loads(result_json)
        
        assert result["specialist_type"] == SPECIALIST_TYPE_TRACE
        assert result["error_type"] == "ResourceDataError"
        assert "Invalid JSON in trace_ids" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])