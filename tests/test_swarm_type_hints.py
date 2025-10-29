#!/usr/bin/env python3
"""
Unit tests for Swarm Orchestrator type hints and documentation.

Tests that type hints are properly defined and functions work
with the expected types.
"""

import pytest
import json
from typing import get_type_hints
from unittest.mock import Mock

from src.promptrca.core.swarm_orchestrator import (
    # Type definitions
    SpecialistResult,
    SpecialistErrorResult,
    TraceResult,
    ResourceType,
    SpecialistType,
    
    # Helper functions
    _extract_resource_from_data,
    _run_specialist_analysis,
    _format_specialist_results,
    
    # Constants
    SPECIALIST_TYPE_LAMBDA,
    SPECIALIST_TYPE_APIGATEWAY,
    SPECIALIST_TYPE_STEPFUNCTIONS,
    SPECIALIST_TYPE_TRACE,
    RESOURCE_TYPE_LAMBDA,
    RESOURCE_TYPE_APIGATEWAY,
    RESOURCE_TYPE_STEPFUNCTIONS
)
from src.promptrca.models import Fact


class TestTypeDefinitions:
    """Test that TypedDict classes are properly defined."""
    
    def test_specialist_result_type_structure(self):
        """Test SpecialistResult TypedDict structure."""
        # Create a valid SpecialistResult
        result: SpecialistResult = {
            "specialist_type": "lambda",
            "resource_name": "test-function",
            "facts": [
                {
                    "source": "lambda_config",
                    "content": "Test fact",
                    "confidence": 0.9,
                    "metadata": {"key": "value"}
                }
            ],
            "analysis_summary": "Test summary"
        }
        
        # Verify all required keys are present
        assert "specialist_type" in result
        assert "resource_name" in result
        assert "facts" in result
        assert "analysis_summary" in result
        
        # Verify types
        assert isinstance(result["specialist_type"], str)
        assert isinstance(result["resource_name"], str)
        assert isinstance(result["facts"], list)
        assert isinstance(result["analysis_summary"], str)
    
    def test_specialist_error_result_type_structure(self):
        """Test SpecialistErrorResult TypedDict structure."""
        # Create a valid SpecialistErrorResult
        error_result: SpecialistErrorResult = {
            "specialist_type": "lambda",
            "error": "Test error message",
            "error_type": "ResourceDataError",
            "facts": []
        }
        
        # Verify all required keys are present
        assert "specialist_type" in error_result
        assert "error" in error_result
        assert "error_type" in error_result
        assert "facts" in error_result
        
        # Verify types
        assert isinstance(error_result["specialist_type"], str)
        assert isinstance(error_result["error"], str)
        assert isinstance(error_result["error_type"], str)
        assert isinstance(error_result["facts"], list)
        assert len(error_result["facts"]) == 0  # Always empty for errors
    
    def test_trace_result_type_structure(self):
        """Test TraceResult TypedDict structure."""
        # Create a valid TraceResult
        trace_result: TraceResult = {
            "specialist_type": "trace",
            "trace_count": 2,
            "facts": [
                {
                    "source": "trace_analysis",
                    "content": "Test trace fact",
                    "confidence": 0.8,
                    "metadata": {"trace_id": "1-abc123-def456"}
                }
            ],
            "analysis_summary": "Analyzed 2 traces - found 1 facts"
        }
        
        # Verify all required keys are present
        assert "specialist_type" in trace_result
        assert "trace_count" in trace_result
        assert "facts" in trace_result
        assert "analysis_summary" in trace_result
        
        # Verify types
        assert isinstance(trace_result["specialist_type"], str)
        assert isinstance(trace_result["trace_count"], int)
        assert isinstance(trace_result["facts"], list)
        assert isinstance(trace_result["analysis_summary"], str)


class TestLiteralTypes:
    """Test that Literal types work correctly."""
    
    def test_resource_type_literals(self):
        """Test ResourceType literal values."""
        # Valid resource types
        valid_types = ["lambda", "apigateway", "stepfunctions"]
        
        for resource_type in valid_types:
            # These should be valid ResourceType values
            assert resource_type in ["lambda", "apigateway", "stepfunctions"]
    
    def test_specialist_type_literals(self):
        """Test SpecialistType literal values."""
        # Valid specialist types
        valid_types = ["lambda", "apigateway", "stepfunctions", "trace"]
        
        for specialist_type in valid_types:
            # These should be valid SpecialistType values
            assert specialist_type in ["lambda", "apigateway", "stepfunctions", "trace"]
    
    def test_constants_match_literal_types(self):
        """Test that constants match the literal type definitions."""
        # Resource type constants should match ResourceType literals
        assert RESOURCE_TYPE_LAMBDA == "lambda"
        assert RESOURCE_TYPE_APIGATEWAY == "apigateway"
        assert RESOURCE_TYPE_STEPFUNCTIONS == "stepfunctions"
        
        # Specialist type constants should match SpecialistType literals
        assert SPECIALIST_TYPE_LAMBDA == "lambda"
        assert SPECIALIST_TYPE_APIGATEWAY == "apigateway"
        assert SPECIALIST_TYPE_STEPFUNCTIONS == "stepfunctions"
        assert SPECIALIST_TYPE_TRACE == "trace"


class TestFunctionTypeHints:
    """Test that functions have proper type hints."""
    
    def test_extract_resource_from_data_type_hints(self):
        """Test _extract_resource_from_data function type hints."""
        # Get type hints for the function
        type_hints = get_type_hints(_extract_resource_from_data)
        
        # Verify parameter types are hinted
        assert 'resource_data_parsed' in type_hints
        assert 'resource_type' in type_hints
        assert 'context_data' in type_hints
        assert 'return' in type_hints
        
        # Test function works with correct types
        resource_list = [{"type": "lambda", "name": "test-func"}]
        context = {"region": "us-east-1"}
        
        result = _extract_resource_from_data(resource_list, "lambda", context)
        assert isinstance(result, dict)
        assert result["type"] == "lambda"
    
    def test_run_specialist_analysis_type_hints(self):
        """Test _run_specialist_analysis function type hints."""
        # Get type hints for the function
        type_hints = get_type_hints(_run_specialist_analysis)
        
        # Verify parameter types are hinted (specialist is typed as Any)
        assert 'resource' in type_hints
        assert 'context' in type_hints
        assert 'return' in type_hints
    
    def test_format_specialist_results_type_hints(self):
        """Test _format_specialist_results function type hints."""
        # Get type hints for the function
        type_hints = get_type_hints(_format_specialist_results)
        
        # Verify parameter types are hinted
        assert 'specialist_type' in type_hints
        assert 'resource_name' in type_hints
        assert 'facts' in type_hints
        assert 'return' in type_hints
        
        # Test function works with correct types
        facts = [
            Fact(
                source="test_source",
                content="test content",
                confidence=0.9,
                metadata={"key": "value"}
            )
        ]
        
        result = _format_specialist_results("lambda", "test-resource", facts)
        
        # Verify result matches SpecialistResult structure
        assert "specialist_type" in result
        assert "resource_name" in result
        assert "facts" in result
        assert "analysis_summary" in result
        
        assert result["specialist_type"] == "lambda"
        assert result["resource_name"] == "test-resource"
        assert len(result["facts"]) == 1
        assert "found 1 facts" in result["analysis_summary"]


class TestTypeCompatibility:
    """Test that types work correctly with actual data."""
    
    def test_specialist_result_json_serialization(self):
        """Test that SpecialistResult can be JSON serialized."""
        result: SpecialistResult = {
            "specialist_type": "lambda",
            "resource_name": "test-function",
            "facts": [
                {
                    "source": "lambda_config",
                    "content": "Memory: 128MB",
                    "confidence": 0.9,
                    "metadata": {"memory": 128, "timeout": 30}
                }
            ],
            "analysis_summary": "Analyzed lambda test-function - found 1 facts"
        }
        
        # Should be able to serialize to JSON
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["specialist_type"] == "lambda"
        assert deserialized["resource_name"] == "test-function"
        assert len(deserialized["facts"]) == 1
    
    def test_error_result_json_serialization(self):
        """Test that SpecialistErrorResult can be JSON serialized."""
        error_result: SpecialistErrorResult = {
            "specialist_type": "apigateway",
            "error": "Invalid JSON in resource_data: Expecting ',' delimiter",
            "error_type": "ResourceDataError",
            "facts": []
        }
        
        # Should be able to serialize to JSON
        json_str = json.dumps(error_result)
        assert isinstance(json_str, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["specialist_type"] == "apigateway"
        assert deserialized["error_type"] == "ResourceDataError"
        assert deserialized["facts"] == []
    
    def test_trace_result_json_serialization(self):
        """Test that TraceResult can be JSON serialized."""
        trace_result: TraceResult = {
            "specialist_type": "trace",
            "trace_count": 3,
            "facts": [
                {
                    "source": "trace_analysis",
                    "content": "Lambda cold start detected",
                    "confidence": 0.85,
                    "metadata": {
                        "trace_id": "1-abc123-def456",
                        "service": "lambda",
                        "duration_ms": 2500
                    }
                }
            ],
            "analysis_summary": "Analyzed 3 traces - found 1 facts"
        }
        
        # Should be able to serialize to JSON
        json_str = json.dumps(trace_result)
        assert isinstance(json_str, str)
        
        # Should be able to deserialize back
        deserialized = json.loads(json_str)
        assert deserialized["specialist_type"] == "trace"
        assert deserialized["trace_count"] == 3
        assert len(deserialized["facts"]) == 1


class TestDocumentationExamples:
    """Test that documentation examples work correctly."""
    
    def test_extract_resource_documentation_examples(self):
        """Test examples from _extract_resource_from_data docstring."""
        # Example 1: Extract Lambda from list
        data = [{"type": "lambda", "name": "my-func", "arn": "arn:aws:lambda:..."}]
        result = _extract_resource_from_data(data, "lambda", {"region": "us-east-1"})
        assert result["name"] == "my-func"
        
        # Example 2: Create placeholder when resource not found
        data = [{"type": "apigateway", "name": "my-api"}]
        result = _extract_resource_from_data(data, "lambda", {"region": "eu-west-1"})
        expected = {"type": "lambda", "name": "unknown", "id": "unknown", "region": "eu-west-1"}
        assert result == expected
        
        # Example 3: Handle single resource
        data = {"type": "stepfunctions", "name": "my-sm", "arn": "arn:aws:states:..."}
        result = _extract_resource_from_data(data, "stepfunctions", {})
        assert result["name"] == "my-sm"
    
    def test_format_results_documentation_examples(self):
        """Test examples from _format_specialist_results docstring."""
        # Example 1: Format Lambda analysis results
        facts = [
            Fact(
                source="lambda_config",
                content="Timeout: 30s",
                confidence=0.9,
                metadata={"timeout": 30}
            )
        ]
        result = _format_specialist_results("lambda", "my-function", facts)
        assert result["specialist_type"] == "lambda"
        assert result["analysis_summary"] == "Analyzed lambda my-function - found 1 facts"
        
        # Example 2: Handle empty facts
        result = _format_specialist_results("apigateway", "my-api", [])
        assert result["facts"] == []
        assert "found 0 facts" in result["analysis_summary"]


class TestTypeHintConsistency:
    """Test that type hints are consistent across the codebase."""
    
    def test_specialist_type_consistency(self):
        """Test that specialist types are used consistently."""
        # All specialist type constants should be valid SpecialistType values
        specialist_constants = [
            SPECIALIST_TYPE_LAMBDA,
            SPECIALIST_TYPE_APIGATEWAY,
            SPECIALIST_TYPE_STEPFUNCTIONS,
            SPECIALIST_TYPE_TRACE
        ]
        
        valid_specialist_types = ["lambda", "apigateway", "stepfunctions", "trace"]
        
        for constant in specialist_constants:
            assert constant in valid_specialist_types
    
    def test_resource_type_consistency(self):
        """Test that resource types are used consistently."""
        # All resource type constants should be valid ResourceType values
        resource_constants = [
            RESOURCE_TYPE_LAMBDA,
            RESOURCE_TYPE_APIGATEWAY,
            RESOURCE_TYPE_STEPFUNCTIONS
        ]
        
        valid_resource_types = ["lambda", "apigateway", "stepfunctions"]
        
        for constant in resource_constants:
            assert constant in valid_resource_types
    
    def test_function_return_types_match_typeddict(self):
        """Test that function return types match TypedDict definitions."""
        # _format_specialist_results should return SpecialistResult-compatible dict
        facts = [
            Fact(
                source="test_source",
                content="test content",
                confidence=0.8,
                metadata={}
            )
        ]
        
        result = _format_specialist_results("lambda", "test", facts)
        
        # Should have all SpecialistResult keys
        required_keys = ["specialist_type", "resource_name", "facts", "analysis_summary"]
        for key in required_keys:
            assert key in result
        
        # Should have correct types
        assert isinstance(result["specialist_type"], str)
        assert isinstance(result["resource_name"], str)
        assert isinstance(result["facts"], list)
        assert isinstance(result["analysis_summary"], str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])