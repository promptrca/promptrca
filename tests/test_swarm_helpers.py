#!/usr/bin/env python3
"""
Unit tests for Swarm Orchestrator helper functions.

Tests the refactored helper functions with realistic mocked responses
without using AI or AWS services.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import List

from src.promptrca.core.swarm_orchestrator import (
    _extract_resource_from_data,
    _run_specialist_analysis,
    _format_specialist_results
)
from src.promptrca.models import Fact
from src.promptrca.specialists import InvestigationContext


class TestExtractResourceFromData:
    """Test the _extract_resource_from_data helper function."""
    
    def test_extract_lambda_from_list(self):
        """Test extracting Lambda resource from a list of resources."""
        # Arrange
        resource_data = [
            {"type": "apigateway", "name": "my-api", "id": "abc123"},
            {"type": "lambda", "name": "my-function", "id": "func-456"},
            {"type": "stepfunctions", "name": "my-state-machine", "id": "sm-789"}
        ]
        context_data = {"region": "us-east-1"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "lambda", context_data)
        
        # Assert
        assert result == {"type": "lambda", "name": "my-function", "id": "func-456"}
    
    def test_extract_apigateway_from_list(self):
        """Test extracting API Gateway resource from a list."""
        # Arrange
        resource_data = [
            {"type": "lambda", "name": "my-function", "id": "func-456"},
            {"type": "apigateway", "name": "my-api", "id": "abc123", "stage": "prod"}
        ]
        context_data = {"region": "eu-west-1"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "apigateway", context_data)
        
        # Assert
        assert result == {"type": "apigateway", "name": "my-api", "id": "abc123", "stage": "prod"}
    
    def test_extract_stepfunctions_from_list(self):
        """Test extracting Step Functions resource from a list."""
        # Arrange
        resource_data = [
            {"type": "stepfunctions", "name": "order-processing", "id": "sm-789", "arn": "arn:aws:states:us-east-1:123456789012:stateMachine:order-processing"}
        ]
        context_data = {"region": "us-east-1"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "stepfunctions", context_data)
        
        # Assert
        assert result == {
            "type": "stepfunctions", 
            "name": "order-processing", 
            "id": "sm-789",
            "arn": "arn:aws:states:us-east-1:123456789012:stateMachine:order-processing"
        }
    
    def test_extract_missing_resource_creates_placeholder(self):
        """Test that missing resource type creates a placeholder."""
        # Arrange
        resource_data = [
            {"type": "apigateway", "name": "my-api", "id": "abc123"},
            {"type": "stepfunctions", "name": "my-state-machine", "id": "sm-789"}
        ]
        context_data = {"region": "ap-southeast-2"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "lambda", context_data)
        
        # Assert
        expected = {
            'type': 'lambda',
            'name': 'unknown',
            'id': 'unknown',
            'region': 'ap-southeast-2'
        }
        assert result == expected
    
    def test_extract_from_single_resource_dict(self):
        """Test extracting from a single resource dictionary."""
        # Arrange
        resource_data = {"type": "lambda", "name": "single-function", "id": "func-999"}
        context_data = {"region": "us-west-2"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "lambda", context_data)
        
        # Assert
        assert result == {"type": "lambda", "name": "single-function", "id": "func-999"}
    
    def test_extract_from_empty_list_creates_placeholder(self):
        """Test that empty list creates a placeholder."""
        # Arrange
        resource_data = []
        context_data = {"region": "ca-central-1"}
        
        # Act
        result = _extract_resource_from_data(resource_data, "apigateway", context_data)
        
        # Assert
        expected = {
            'type': 'apigateway',
            'name': 'unknown',
            'id': 'unknown',
            'region': 'ca-central-1'
        }
        assert result == expected
    
    def test_extract_uses_default_region_when_missing(self):
        """Test that default region is used when not provided in context."""
        # Arrange
        resource_data = []
        context_data = {}  # No region provided
        
        # Act
        result = _extract_resource_from_data(resource_data, "lambda", context_data)
        
        # Assert
        assert result['region'] == 'us-east-1'  # Default region


class TestRunSpecialistAnalysis:
    """Test the _run_specialist_analysis helper function."""
    
    @pytest.fixture
    def mock_specialist(self):
        """Create a mock specialist with realistic behavior."""
        specialist = Mock()
        # Mock the analyze method to return realistic facts
        specialist.analyze = AsyncMock(return_value=[
            Fact(
                source="lambda_config",
                content="Function timeout is set to 30 seconds",
                confidence=0.9,
                metadata={"timeout": 30, "memory": 256}
            ),
            Fact(
                source="lambda_metrics",
                content="Function has 5 errors in the last hour",
                confidence=0.85,
                metadata={"error_count": 5, "time_window": "1h"}
            )
        ])
        return specialist
    
    @pytest.fixture
    def sample_resource(self):
        """Create a sample resource for testing."""
        return {
            "type": "lambda",
            "name": "test-function",
            "id": "func-123",
            "region": "us-east-1"
        }
    
    @pytest.fixture
    def sample_context(self):
        """Create a sample investigation context."""
        return InvestigationContext(
            trace_ids=["1-abc123-def456"],
            region="us-east-1",
            parsed_inputs=None
        )
    
    def test_run_specialist_analysis_success(self, mock_specialist, sample_resource, sample_context):
        """Test successful specialist analysis execution."""
        # Act
        facts = _run_specialist_analysis(mock_specialist, sample_resource, sample_context)
        
        # Assert
        assert len(facts) == 2
        assert facts[0].source == "lambda_config"
        assert facts[0].content == "Function timeout is set to 30 seconds"
        assert facts[0].confidence == 0.9
        assert facts[1].source == "lambda_metrics"
        assert facts[1].confidence == 0.85
        
        # Verify the specialist was called with correct parameters
        mock_specialist.analyze.assert_called_once_with(sample_resource, sample_context)
    
    def test_run_specialist_analysis_with_empty_results(self, sample_resource, sample_context):
        """Test specialist analysis that returns no facts."""
        # Arrange
        specialist = Mock()
        specialist.analyze = AsyncMock(return_value=[])
        
        # Act
        facts = _run_specialist_analysis(specialist, sample_resource, sample_context)
        
        # Assert
        assert facts == []
        specialist.analyze.assert_called_once_with(sample_resource, sample_context)
    
    def test_run_specialist_analysis_handles_async_exception(self, sample_resource, sample_context):
        """Test that async exceptions are properly propagated."""
        # Arrange
        specialist = Mock()
        specialist.analyze = AsyncMock(side_effect=Exception("Specialist analysis failed"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Specialist analysis failed"):
            _run_specialist_analysis(specialist, sample_resource, sample_context)


class TestFormatSpecialistResults:
    """Test the _format_specialist_results helper function."""
    
    @pytest.fixture
    def sample_facts(self):
        """Create sample facts for testing."""
        return [
            Fact(
                source="lambda_config",
                content="Function memory is set to 512 MB",
                confidence=0.95,
                metadata={"memory_mb": 512, "runtime": "python3.9"}
            ),
            Fact(
                source="lambda_logs",
                content="Found 3 timeout errors in CloudWatch logs",
                confidence=0.88,
                metadata={"error_type": "timeout", "count": 3}
            ),
            Fact(
                source="lambda_metrics",
                content="Average duration is 2.5 seconds",
                confidence=0.92,
                metadata={"avg_duration_ms": 2500}
            )
        ]
    
    def test_format_lambda_results(self, sample_facts):
        """Test formatting Lambda specialist results."""
        # Act
        result = _format_specialist_results("lambda", "my-function", sample_facts)
        
        # Assert
        assert result["specialist_type"] == "lambda"
        assert result["resource_name"] == "my-function"
        assert result["analysis_summary"] == "Analyzed lambda my-function - found 3 facts"
        assert len(result["facts"]) == 3
        
        # Check first fact
        fact1 = result["facts"][0]
        assert fact1["source"] == "lambda_config"
        assert fact1["content"] == "Function memory is set to 512 MB"
        assert fact1["confidence"] == 0.95
        assert fact1["metadata"] == {"memory_mb": 512, "runtime": "python3.9"}
        
        # Check second fact
        fact2 = result["facts"][1]
        assert fact2["source"] == "lambda_logs"
        assert fact2["confidence"] == 0.88
        assert fact2["metadata"]["error_type"] == "timeout"
    
    def test_format_apigateway_results(self, sample_facts):
        """Test formatting API Gateway specialist results."""
        # Act
        result = _format_specialist_results("apigateway", "my-api", sample_facts)
        
        # Assert
        assert result["specialist_type"] == "apigateway"
        assert result["resource_name"] == "my-api"
        assert result["analysis_summary"] == "Analyzed apigateway my-api - found 3 facts"
    
    def test_format_stepfunctions_results(self, sample_facts):
        """Test formatting Step Functions specialist results."""
        # Act
        result = _format_specialist_results("stepfunctions", "order-processor", sample_facts)
        
        # Assert
        assert result["specialist_type"] == "stepfunctions"
        assert result["resource_name"] == "order-processor"
        assert result["analysis_summary"] == "Analyzed stepfunctions order-processor - found 3 facts"
    
    def test_format_empty_facts(self):
        """Test formatting results with no facts."""
        # Act
        result = _format_specialist_results("lambda", "empty-function", [])
        
        # Assert
        assert result["specialist_type"] == "lambda"
        assert result["resource_name"] == "empty-function"
        assert result["analysis_summary"] == "Analyzed lambda empty-function - found 0 facts"
        assert result["facts"] == []
    
    def test_format_results_preserves_fact_structure(self):
        """Test that all fact fields are preserved in the output."""
        # Arrange
        facts = [
            Fact(
                source="test_source",
                content="Test content with special characters: àáâãäå",
                confidence=0.75,
                metadata={
                    "complex_data": {
                        "nested": {"value": 42},
                        "list": [1, 2, 3],
                        "boolean": True,
                        "null_value": None
                    }
                }
            )
        ]
        
        # Act
        result = _format_specialist_results("lambda", "test-func", facts)
        
        # Assert
        fact = result["facts"][0]
        assert fact["source"] == "test_source"
        assert fact["content"] == "Test content with special characters: àáâãäå"
        assert fact["confidence"] == 0.75
        assert fact["metadata"]["complex_data"]["nested"]["value"] == 42
        assert fact["metadata"]["complex_data"]["list"] == [1, 2, 3]
        assert fact["metadata"]["complex_data"]["boolean"] is True
        assert fact["metadata"]["complex_data"]["null_value"] is None


class TestIntegrationScenarios:
    """Integration tests combining multiple helper functions."""
    
    def test_realistic_lambda_investigation_flow(self):
        """Test a realistic flow of Lambda investigation using all helpers."""
        # Arrange - Realistic resource data from X-Ray trace discovery
        resource_data = [
            {
                "type": "apigateway",
                "name": "user-api",
                "id": "abc123def",
                "stage": "prod",
                "region": "us-east-1"
            },
            {
                "type": "lambda", 
                "name": "user-service",
                "id": "func-456ghi",
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:user-service",
                "region": "us-east-1"
            }
        ]
        context_data = {"region": "us-east-1", "trace_ids": ["1-abc123-def456"]}
        
        # Mock specialist with realistic Lambda analysis results
        mock_specialist = Mock()
        mock_specialist.analyze = AsyncMock(return_value=[
            Fact(
                source="lambda_config",
                content="Function timeout set to 30 seconds, memory 256 MB",
                confidence=0.9,
                metadata={"timeout": 30, "memory": 256, "runtime": "python3.9"}
            ),
            Fact(
                source="lambda_errors",
                content="AccessDeniedException: User is not authorized to perform dynamodb:GetItem",
                confidence=0.95,
                metadata={"error_type": "AccessDeniedException", "service": "dynamodb", "action": "GetItem"}
            ),
            Fact(
                source="lambda_metrics",
                content="Error rate is 15% over the last hour",
                confidence=0.88,
                metadata={"error_rate": 0.15, "time_window": "1h", "total_invocations": 200}
            )
        ])
        
        # Act - Simulate the complete flow
        # 1. Extract Lambda resource
        resource = _extract_resource_from_data(resource_data, "lambda", context_data)
        
        # 2. Create context
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=None
        )
        
        # 3. Run analysis
        facts = _run_specialist_analysis(mock_specialist, resource, context)
        
        # 4. Format results
        results = _format_specialist_results("lambda", resource.get('name', 'unknown'), facts)
        
        # Assert - Verify the complete flow
        assert resource["name"] == "user-service"
        assert resource["type"] == "lambda"
        
        assert len(facts) == 3
        assert any("AccessDeniedException" in fact.content for fact in facts)
        assert any("timeout" in fact.content.lower() for fact in facts)
        
        assert results["specialist_type"] == "lambda"
        assert results["resource_name"] == "user-service"
        assert results["analysis_summary"] == "Analyzed lambda user-service - found 3 facts"
        
        # Verify the results can be JSON serialized (important for tool responses)
        json_str = json.dumps(results, indent=2)
        parsed_back = json.loads(json_str)
        assert parsed_back["specialist_type"] == "lambda"
    
    def test_realistic_apigateway_investigation_flow(self):
        """Test a realistic API Gateway investigation flow."""
        # Arrange - API Gateway with integration issues
        resource_data = {
            "type": "apigateway",
            "name": "payment-api",
            "id": "xyz789abc",
            "stage": "prod",
            "methods": ["GET", "POST"],
            "region": "eu-west-1"
        }
        context_data = {"region": "eu-west-1", "trace_ids": ["1-xyz789-abc123"]}
        
        # Mock specialist with realistic API Gateway analysis
        mock_specialist = Mock()
        mock_specialist.analyze = AsyncMock(return_value=[
            Fact(
                source="apigateway_config",
                content="API Gateway stage 'prod' has throttling enabled: 1000 requests/second",
                confidence=0.92,
                metadata={"throttle_rate": 1000, "throttle_burst": 2000, "stage": "prod"}
            ),
            Fact(
                source="apigateway_integration",
                content="Lambda integration returns 502 Bad Gateway errors",
                confidence=0.89,
                metadata={"error_code": 502, "integration_type": "AWS_PROXY", "backend": "lambda"}
            ),
            Fact(
                source="apigateway_logs",
                content="Execution logs show 'Execution failed due to configuration error'",
                confidence=0.94,
                metadata={"log_level": "ERROR", "execution_id": "abc123-def456"}
            )
        ])
        
        # Act
        resource = _extract_resource_from_data(resource_data, "apigateway", context_data)
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=None
        )
        facts = _run_specialist_analysis(mock_specialist, resource, context)
        results = _format_specialist_results("apigateway", resource.get('name', 'unknown'), facts)
        
        # Assert
        assert resource["name"] == "payment-api"
        assert resource["stage"] == "prod"
        
        assert len(facts) == 3
        assert any("502" in fact.content for fact in facts)
        assert any("throttling" in fact.content.lower() for fact in facts)
        
        assert results["specialist_type"] == "apigateway"
        assert results["resource_name"] == "payment-api"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])