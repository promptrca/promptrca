#!/usr/bin/env python3
"""
Unit tests for Swarm Orchestrator configuration constants.

Tests that constants are properly defined and used consistently
throughout the swarm orchestrator implementation.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, AsyncMock

from src.promptrca.core.swarm_orchestrator import (
    # Configuration constants
    DEFAULT_MAX_HANDOFFS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_EXECUTION_TIMEOUT,
    DEFAULT_NODE_TIMEOUT,
    DEFAULT_AWS_REGION,
    
    # Agent prompt constants
    TRACE_AGENT_PROMPT,
    LAMBDA_AGENT_PROMPT,
    APIGATEWAY_AGENT_PROMPT,
    STEPFUNCTIONS_AGENT_PROMPT,
    
    # Resource type constants
    RESOURCE_TYPE_LAMBDA,
    RESOURCE_TYPE_APIGATEWAY,
    RESOURCE_TYPE_STEPFUNCTIONS,
    
    # Specialist type constants
    SPECIALIST_TYPE_LAMBDA,
    SPECIALIST_TYPE_APIGATEWAY,
    SPECIALIST_TYPE_STEPFUNCTIONS,
    SPECIALIST_TYPE_TRACE,
    
    # Placeholder constants
    UNKNOWN_RESOURCE_NAME,
    UNKNOWN_RESOURCE_ID,
    
    # Helper functions
    _extract_resource_from_data,
    _format_specialist_results,
    
    # Tools
    lambda_specialist_tool,
    apigateway_specialist_tool,
    stepfunctions_specialist_tool,
    
    # Main class
    SwarmOrchestrator
)


class TestConfigurationConstants:
    """Test that configuration constants have sensible default values."""
    
    def test_swarm_performance_defaults(self):
        """Test that swarm performance constants have reasonable defaults."""
        # Assert reasonable defaults for production use
        assert DEFAULT_MAX_HANDOFFS == 5
        assert DEFAULT_MAX_ITERATIONS == 3
        assert DEFAULT_EXECUTION_TIMEOUT == 90.0
        assert DEFAULT_NODE_TIMEOUT == 30.0
        
        # Verify types
        assert isinstance(DEFAULT_MAX_HANDOFFS, int)
        assert isinstance(DEFAULT_MAX_ITERATIONS, int)
        assert isinstance(DEFAULT_EXECUTION_TIMEOUT, float)
        assert isinstance(DEFAULT_NODE_TIMEOUT, float)
        
        # Verify reasonable ranges
        assert 1 <= DEFAULT_MAX_HANDOFFS <= 20
        assert 1 <= DEFAULT_MAX_ITERATIONS <= 10
        assert 10.0 <= DEFAULT_EXECUTION_TIMEOUT <= 300.0
        assert 5.0 <= DEFAULT_NODE_TIMEOUT <= 120.0
    
    def test_aws_region_default(self):
        """Test that default AWS region is valid."""
        assert DEFAULT_AWS_REGION == 'us-east-1'
        assert isinstance(DEFAULT_AWS_REGION, str)
        assert len(DEFAULT_AWS_REGION) > 0
    
    def test_resource_type_constants(self):
        """Test that resource type constants are properly defined."""
        assert RESOURCE_TYPE_LAMBDA == 'lambda'
        assert RESOURCE_TYPE_APIGATEWAY == 'apigateway'
        assert RESOURCE_TYPE_STEPFUNCTIONS == 'stepfunctions'
        
        # Verify they're all strings
        assert all(isinstance(const, str) for const in [
            RESOURCE_TYPE_LAMBDA,
            RESOURCE_TYPE_APIGATEWAY,
            RESOURCE_TYPE_STEPFUNCTIONS
        ])
        
        # Verify they're all unique
        resource_types = [
            RESOURCE_TYPE_LAMBDA,
            RESOURCE_TYPE_APIGATEWAY,
            RESOURCE_TYPE_STEPFUNCTIONS
        ]
        assert len(resource_types) == len(set(resource_types))
    
    def test_specialist_type_constants(self):
        """Test that specialist type constants are properly defined."""
        assert SPECIALIST_TYPE_LAMBDA == 'lambda'
        assert SPECIALIST_TYPE_APIGATEWAY == 'apigateway'
        assert SPECIALIST_TYPE_STEPFUNCTIONS == 'stepfunctions'
        assert SPECIALIST_TYPE_TRACE == 'trace'
        
        # Verify they're all strings
        assert all(isinstance(const, str) for const in [
            SPECIALIST_TYPE_LAMBDA,
            SPECIALIST_TYPE_APIGATEWAY,
            SPECIALIST_TYPE_STEPFUNCTIONS,
            SPECIALIST_TYPE_TRACE
        ])
        
        # Verify they're all unique
        specialist_types = [
            SPECIALIST_TYPE_LAMBDA,
            SPECIALIST_TYPE_APIGATEWAY,
            SPECIALIST_TYPE_STEPFUNCTIONS,
            SPECIALIST_TYPE_TRACE
        ]
        assert len(specialist_types) == len(set(specialist_types))
    
    def test_placeholder_constants(self):
        """Test that placeholder constants are properly defined."""
        assert UNKNOWN_RESOURCE_NAME == 'unknown'
        assert UNKNOWN_RESOURCE_ID == 'unknown'
        
        assert isinstance(UNKNOWN_RESOURCE_NAME, str)
        assert isinstance(UNKNOWN_RESOURCE_ID, str)
        assert len(UNKNOWN_RESOURCE_NAME) > 0
        assert len(UNKNOWN_RESOURCE_ID) > 0


class TestAgentPromptConstants:
    """Test that agent prompt constants are properly defined and contain expected content."""
    
    def test_trace_agent_prompt(self):
        """Test that trace agent prompt contains expected keywords."""
        assert isinstance(TRACE_AGENT_PROMPT, str)
        assert len(TRACE_AGENT_PROMPT) > 50
        
        # Check for key concepts
        assert 'trace analysis specialist' in TRACE_AGENT_PROMPT.lower()
        assert 'trace_specialist_tool' in TRACE_AGENT_PROMPT
        assert 'concise' in TRACE_AGENT_PROMPT.lower()
        assert 'hand off' in TRACE_AGENT_PROMPT.lower()
    
    def test_lambda_agent_prompt(self):
        """Test that Lambda agent prompt contains expected keywords."""
        assert isinstance(LAMBDA_AGENT_PROMPT, str)
        assert len(LAMBDA_AGENT_PROMPT) > 50
        
        # Check for key concepts
        assert 'lambda specialist' in LAMBDA_AGENT_PROMPT.lower()
        assert 'lambda_specialist_tool' in LAMBDA_AGENT_PROMPT
        assert 'concise' in LAMBDA_AGENT_PROMPT.lower()
        assert 'configuration' in LAMBDA_AGENT_PROMPT.lower()
        assert 'iam' in LAMBDA_AGENT_PROMPT.lower()
    
    def test_apigateway_agent_prompt(self):
        """Test that API Gateway agent prompt contains expected keywords."""
        assert isinstance(APIGATEWAY_AGENT_PROMPT, str)
        assert len(APIGATEWAY_AGENT_PROMPT) > 50
        
        # Check for key concepts
        assert 'api gateway specialist' in APIGATEWAY_AGENT_PROMPT.lower()
        assert 'apigateway_specialist_tool' in APIGATEWAY_AGENT_PROMPT
        assert 'concise' in APIGATEWAY_AGENT_PROMPT.lower()
        assert 'integration' in APIGATEWAY_AGENT_PROMPT.lower()
        assert 'permissions' in APIGATEWAY_AGENT_PROMPT.lower()
    
    def test_stepfunctions_agent_prompt(self):
        """Test that Step Functions agent prompt contains expected keywords."""
        assert isinstance(STEPFUNCTIONS_AGENT_PROMPT, str)
        assert len(STEPFUNCTIONS_AGENT_PROMPT) > 50
        
        # Check for key concepts
        assert 'step functions specialist' in STEPFUNCTIONS_AGENT_PROMPT.lower()
        assert 'stepfunctions_specialist_tool' in STEPFUNCTIONS_AGENT_PROMPT
        assert 'concise' in STEPFUNCTIONS_AGENT_PROMPT.lower()
        assert 'execution' in STEPFUNCTIONS_AGENT_PROMPT.lower()
        assert 'state transitions' in STEPFUNCTIONS_AGENT_PROMPT.lower()
    
    def test_all_prompts_are_concise(self):
        """Test that all agent prompts emphasize being concise."""
        prompts = [
            TRACE_AGENT_PROMPT,
            LAMBDA_AGENT_PROMPT,
            APIGATEWAY_AGENT_PROMPT,
            STEPFUNCTIONS_AGENT_PROMPT
        ]
        
        for prompt in prompts:
            assert 'concise' in prompt.lower() or 'brief' in prompt.lower()
    
    def test_prompts_mention_tools(self):
        """Test that each prompt mentions its corresponding tool."""
        tool_mappings = [
            (TRACE_AGENT_PROMPT, 'trace_specialist_tool'),
            (LAMBDA_AGENT_PROMPT, 'lambda_specialist_tool'),
            (APIGATEWAY_AGENT_PROMPT, 'apigateway_specialist_tool'),
            (STEPFUNCTIONS_AGENT_PROMPT, 'stepfunctions_specialist_tool')
        ]
        
        for prompt, expected_tool in tool_mappings:
            assert expected_tool in prompt


class TestConstantsUsageInHelpers:
    """Test that helper functions properly use the defined constants."""
    
    def test_extract_resource_uses_constants(self):
        """Test that _extract_resource_from_data uses constants for defaults."""
        # Test with empty list - should create placeholder with constants
        result = _extract_resource_from_data([], RESOURCE_TYPE_LAMBDA, {})
        
        assert result['name'] == UNKNOWN_RESOURCE_NAME
        assert result['id'] == UNKNOWN_RESOURCE_ID
        assert result['region'] == DEFAULT_AWS_REGION
        assert result['type'] == RESOURCE_TYPE_LAMBDA
    
    def test_extract_resource_uses_custom_region(self):
        """Test that custom region overrides default constant."""
        custom_region = 'eu-west-1'
        result = _extract_resource_from_data(
            [], 
            RESOURCE_TYPE_APIGATEWAY, 
            {'region': custom_region}
        )
        
        assert result['region'] == custom_region
        assert result['name'] == UNKNOWN_RESOURCE_NAME
        assert result['id'] == UNKNOWN_RESOURCE_ID
    
    def test_format_specialist_results_uses_constants(self):
        """Test that _format_specialist_results properly uses specialist type constants."""
        from src.promptrca.models import Fact
        
        facts = [
            Fact(
                source="test_source",
                content="Test content",
                confidence=0.9,
                metadata={"test": True}
            )
        ]
        
        # Test with each specialist type constant
        for specialist_type in [SPECIALIST_TYPE_LAMBDA, SPECIALIST_TYPE_APIGATEWAY, 
                               SPECIALIST_TYPE_STEPFUNCTIONS, SPECIALIST_TYPE_TRACE]:
            result = _format_specialist_results(specialist_type, "test-resource", facts)
            assert result["specialist_type"] == specialist_type


class TestConstantsUsageInTools:
    """Test that specialist tools properly use the defined constants."""
    
    @patch('src.promptrca.core.swarm_orchestrator.LambdaSpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    def test_lambda_tool_uses_constants(self, mock_run_analysis, mock_specialist_class):
        """Test that lambda_specialist_tool uses constants correctly."""
        # Setup mocks
        mock_run_analysis.return_value = []
        
        # Test data
        resource_data = json.dumps([{"type": "lambda", "name": "test-func"}])
        context_data = json.dumps({"region": "us-west-2", "trace_ids": []})
        
        # Call tool
        result_json = lambda_specialist_tool(resource_data, context_data)
        result = json.loads(result_json)
        
        # Verify constants are used
        assert result["specialist_type"] == SPECIALIST_TYPE_LAMBDA
        
        # Verify the helper was called with the right constant
        mock_run_analysis.assert_called_once()
    
    @patch('src.promptrca.core.swarm_orchestrator.APIGatewaySpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    def test_apigateway_tool_uses_constants(self, mock_run_analysis, mock_specialist_class):
        """Test that apigateway_specialist_tool uses constants correctly."""
        # Setup mocks
        mock_run_analysis.return_value = []
        
        # Test data
        resource_data = json.dumps([{"type": "apigateway", "name": "test-api"}])
        context_data = json.dumps({"region": "eu-central-1", "trace_ids": []})
        
        # Call tool
        result_json = apigateway_specialist_tool(resource_data, context_data)
        result = json.loads(result_json)
        
        # Verify constants are used
        assert result["specialist_type"] == SPECIALIST_TYPE_APIGATEWAY
    
    @patch('src.promptrca.core.swarm_orchestrator.StepFunctionsSpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    def test_stepfunctions_tool_uses_constants(self, mock_run_analysis, mock_specialist_class):
        """Test that stepfunctions_specialist_tool uses constants correctly."""
        # Setup mocks
        mock_run_analysis.return_value = []
        
        # Test data
        resource_data = json.dumps([{"type": "stepfunctions", "name": "test-sm"}])
        context_data = json.dumps({"region": "ap-southeast-1", "trace_ids": []})
        
        # Call tool
        result_json = stepfunctions_specialist_tool(resource_data, context_data)
        result = json.loads(result_json)
        
        # Verify constants are used
        assert result["specialist_type"] == SPECIALIST_TYPE_STEPFUNCTIONS
    
    def test_tool_error_responses_use_constants(self):
        """Test that tool error responses use specialist type constants."""
        # Test with invalid JSON to trigger error handling
        invalid_json = "invalid json"
        context_data = json.dumps({"region": "us-east-1"})
        
        # Test each tool's error handling
        tools_and_types = [
            (lambda_specialist_tool, SPECIALIST_TYPE_LAMBDA),
            (apigateway_specialist_tool, SPECIALIST_TYPE_APIGATEWAY),
            (stepfunctions_specialist_tool, SPECIALIST_TYPE_STEPFUNCTIONS)
        ]
        
        for tool_func, expected_type in tools_and_types:
            result_json = tool_func(invalid_json, context_data)
            result = json.loads(result_json)
            
            assert result["specialist_type"] == expected_type
            assert "error" in result
            assert result["facts"] == []


class TestEnvironmentVariableIntegration:
    """Test that environment variables properly override constants."""
    
    @patch.dict(os.environ, {
        'SWARM_MAX_HANDOFFS': '8',
        'SWARM_MAX_ITERATIONS': '5',
        'SWARM_EXECUTION_TIMEOUT': '120.0',
        'SWARM_NODE_TIMEOUT': '45.0'
    })
    @patch('src.promptrca.utils.config.create_lambda_agent_model')
    @patch('src.promptrca.utils.config.create_apigateway_agent_model')
    @patch('src.promptrca.utils.config.create_stepfunctions_agent_model')
    @patch('src.promptrca.utils.config.create_orchestrator_model')
    def test_swarm_orchestrator_uses_env_vars(self, mock_trace_model, mock_sf_model, 
                                            mock_apigw_model, mock_lambda_model):
        """Test that SwarmOrchestrator reads environment variables with constant fallbacks."""
        # Setup mocks
        for mock_model in [mock_trace_model, mock_sf_model, mock_apigw_model, mock_lambda_model]:
            mock_model.return_value = Mock()
        
        # Create orchestrator (this will call _create_swarm)
        orchestrator = SwarmOrchestrator()
        
        # Verify the swarm was created with environment variable values
        swarm = orchestrator.swarm
        assert swarm.max_handoffs == 8  # From env var
        assert swarm.max_iterations == 5  # From env var
        assert swarm.execution_timeout == 120.0  # From env var
        assert swarm.node_timeout == 45.0  # From env var
    
    @patch.dict(os.environ, {}, clear=True)  # Clear all env vars
    @patch('src.promptrca.utils.config.create_lambda_agent_model')
    @patch('src.promptrca.utils.config.create_apigateway_agent_model')
    @patch('src.promptrca.utils.config.create_stepfunctions_agent_model')
    @patch('src.promptrca.utils.config.create_orchestrator_model')
    def test_swarm_orchestrator_uses_default_constants(self, mock_trace_model, mock_sf_model,
                                                     mock_apigw_model, mock_lambda_model):
        """Test that SwarmOrchestrator falls back to constants when env vars are not set."""
        # Setup mocks
        for mock_model in [mock_trace_model, mock_sf_model, mock_apigw_model, mock_lambda_model]:
            mock_model.return_value = Mock()
        
        # Create orchestrator
        orchestrator = SwarmOrchestrator()
        
        # Verify the swarm was created with default constant values
        swarm = orchestrator.swarm
        assert swarm.max_handoffs == DEFAULT_MAX_HANDOFFS
        assert swarm.max_iterations == DEFAULT_MAX_ITERATIONS
        assert swarm.execution_timeout == DEFAULT_EXECUTION_TIMEOUT
        assert swarm.node_timeout == DEFAULT_NODE_TIMEOUT


class TestConstantsConsistency:
    """Test that constants are used consistently throughout the codebase."""
    
    def test_resource_and_specialist_type_alignment(self):
        """Test that resource types align with specialist types where expected."""
        # These should match for the main service types
        assert RESOURCE_TYPE_LAMBDA == SPECIALIST_TYPE_LAMBDA
        assert RESOURCE_TYPE_APIGATEWAY == SPECIALIST_TYPE_APIGATEWAY
        assert RESOURCE_TYPE_STEPFUNCTIONS == SPECIALIST_TYPE_STEPFUNCTIONS
        
        # Trace is special - it's a specialist type but not a resource type
        assert SPECIALIST_TYPE_TRACE == 'trace'
    
    def test_constants_are_immutable_strings(self):
        """Test that all string constants are immutable."""
        string_constants = [
            DEFAULT_AWS_REGION,
            TRACE_AGENT_PROMPT,
            LAMBDA_AGENT_PROMPT,
            APIGATEWAY_AGENT_PROMPT,
            STEPFUNCTIONS_AGENT_PROMPT,
            RESOURCE_TYPE_LAMBDA,
            RESOURCE_TYPE_APIGATEWAY,
            RESOURCE_TYPE_STEPFUNCTIONS,
            SPECIALIST_TYPE_LAMBDA,
            SPECIALIST_TYPE_APIGATEWAY,
            SPECIALIST_TYPE_STEPFUNCTIONS,
            SPECIALIST_TYPE_TRACE,
            UNKNOWN_RESOURCE_NAME,
            UNKNOWN_RESOURCE_ID
        ]
        
        for constant in string_constants:
            assert isinstance(constant, str)
            assert len(constant) > 0
            # Strings are immutable in Python, but let's verify they're not empty
    
    def test_numeric_constants_are_positive(self):
        """Test that all numeric constants have positive values."""
        numeric_constants = [
            DEFAULT_MAX_HANDOFFS,
            DEFAULT_MAX_ITERATIONS,
            DEFAULT_EXECUTION_TIMEOUT,
            DEFAULT_NODE_TIMEOUT
        ]
        
        for constant in numeric_constants:
            assert isinstance(constant, (int, float))
            assert constant > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])