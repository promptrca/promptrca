#!/usr/bin/env python3
"""
Tests for SwarmOrchestrator - Strands best practices implementation
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from src.promptrca.core.swarm_orchestrator import SwarmOrchestrator
from src.promptrca.models import Fact


class TestSwarmOrchestrator:
    """Test the Swarm-based orchestrator implementation."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a SwarmOrchestrator instance for testing."""
        return SwarmOrchestrator(region="us-east-1")
    
    @pytest.fixture
    def sample_inputs(self):
        """Sample investigation inputs."""
        return {
            "xray_trace_id": "1-67890123-abcdef1234567890abcdef12",
            "investigation_target": {
                "type": "lambda",
                "name": "test-function",
                "region": "us-east-1"
            }
        }
    
    def test_orchestrator_initialization(self, orchestrator):
        """Test that the orchestrator initializes correctly."""
        assert orchestrator.region == "us-east-1"
        assert orchestrator.input_parser is not None
        assert orchestrator.lambda_agent is not None
        assert orchestrator.apigateway_agent is not None
        assert orchestrator.stepfunctions_agent is not None
        assert orchestrator.trace_agent is not None
        assert orchestrator.swarm is not None
    
    def test_parse_inputs_structured(self, orchestrator):
        """Test parsing structured inputs."""
        inputs = {
            "investigation_inputs": {
                "trace_ids": ["1-67890123-abcdef1234567890abcdef12"],
                "primary_targets": [
                    {"type": "lambda", "name": "test-function", "region": "us-east-1"}
                ]
            }
        }
        
        with patch.object(orchestrator.input_parser, 'parse_inputs') as mock_parse:
            mock_parse.return_value = Mock(
                trace_ids=["1-67890123-abcdef1234567890abcdef12"],
                primary_targets=[Mock(type="lambda", name="test-function", region="us-east-1")]
            )
            
            result = orchestrator._parse_inputs(inputs, "us-east-1")
            
            mock_parse.assert_called_once_with(inputs["investigation_inputs"], "us-east-1")
            assert result.trace_ids == ["1-67890123-abcdef1234567890abcdef12"]
    
    def test_parse_inputs_legacy(self, orchestrator):
        """Test parsing legacy input format."""
        inputs = {
            "xray_trace_id": "1-67890123-abcdef1234567890abcdef12",
            "function_name": "test-function"
        }
        
        with patch.object(orchestrator.input_parser, 'parse_inputs') as mock_parse:
            mock_parse.return_value = Mock(
                trace_ids=["1-67890123-abcdef1234567890abcdef12"],
                primary_targets=[Mock(type="lambda", name="test-function", region="us-east-1")]
            )
            
            result = orchestrator._parse_inputs(inputs, "us-east-1")
            
            # Should convert legacy format to structured
            expected_structured = {
                'trace_ids': ['1-67890123-abcdef1234567890abcdef12'],
                'primary_targets': [{'type': 'lambda', 'name': 'test-function', 'region': 'us-east-1'}]
            }
            mock_parse.assert_called_once_with(expected_structured, "us-east-1")
    
    @pytest.mark.asyncio
    async def test_discover_resources_explicit_targets(self, orchestrator):
        """Test resource discovery from explicit targets."""
        parsed_inputs = Mock(
            primary_targets=[
                Mock(type="lambda", name="test-function", arn="arn:aws:lambda:us-east-1:123456789012:function:test-function", region="us-east-1", metadata={})
            ],
            trace_ids=[]
        )
        
        resources = await orchestrator._discover_resources(parsed_inputs)
        
        assert len(resources) == 1
        assert resources[0]['type'] == 'lambda'
        assert resources[0]['name'] == 'test-function'
        assert resources[0]['source'] == 'explicit_target'
    
    @pytest.mark.asyncio
    async def test_discover_resources_from_traces(self, orchestrator):
        """Test resource discovery from X-Ray traces."""
        parsed_inputs = Mock(
            primary_targets=[],
            trace_ids=["1-67890123-abcdef1234567890abcdef12"]
        )
        
        mock_trace_resources = {
            "resources": [
                {
                    "type": "lambda",
                    "name": "trace-function",
                    "arn": "arn:aws:lambda:us-east-1:123456789012:function:trace-function",
                    "metadata": {}
                }
            ]
        }
        
        with patch('src.promptrca.core.swarm_orchestrator.get_all_resources_from_trace') as mock_get_resources:
            mock_get_resources.return_value = json.dumps(mock_trace_resources)
            
            resources = await orchestrator._discover_resources(parsed_inputs)
            
            assert len(resources) == 1
            assert resources[0]['type'] == 'lambda'
            assert resources[0]['name'] == 'trace-function'
            assert resources[0]['source'] == 'xray_trace'
    
    def test_create_investigation_prompt(self, orchestrator):
        """Test investigation prompt creation."""
        resources = [
            {"type": "lambda", "name": "test-function"},
            {"type": "apigateway", "name": "test-api"}
        ]
        
        parsed_inputs = Mock(trace_ids=["1-67890123-abcdef1234567890abcdef12"])
        
        investigation_context = {
            "region": "us-east-1",
            "trace_ids": ["1-67890123-abcdef1234567890abcdef12"]
        }
        
        prompt = orchestrator._create_investigation_prompt(resources, parsed_inputs, investigation_context)
        
        assert "AWS Infrastructure Investigation Request" in prompt
        assert "LAMBDA: test-function" in prompt
        assert "APIGATEWAY: test-api" in prompt
        assert "1-67890123-abcdef1234567890abcdef12" in prompt
        assert "us-east-1" in prompt
    
    def test_extract_facts_from_swarm_result(self, orchestrator):
        """Test fact extraction from swarm results."""
        # Mock swarm result with JSON facts
        swarm_result = Mock(
            content='''
            The investigation found several issues:
            
            ```json
            {
                "facts": [
                    {
                        "source": "lambda_specialist",
                        "content": "Function timeout detected",
                        "confidence": 0.9,
                        "metadata": {"timeout": 30}
                    }
                ]
            }
            ```
            
            Additional analysis shows permission errors.
            '''
        )
        
        facts = orchestrator._extract_facts_from_swarm_result(swarm_result)
        
        assert len(facts) >= 1
        # Should find the structured fact
        lambda_facts = [f for f in facts if f.source == "lambda_specialist"]
        assert len(lambda_facts) == 1
        assert lambda_facts[0].content == "Function timeout detected"
        assert lambda_facts[0].confidence == 0.9
    
    def test_extract_facts_fallback(self, orchestrator):
        """Test fact extraction fallback when no structured data found."""
        swarm_result = Mock(content="Investigation completed with error analysis")
        
        facts = orchestrator._extract_facts_from_swarm_result(swarm_result)
        
        # Should create summary facts
        assert len(facts) >= 1
        summary_facts = [f for f in facts if f.source == "swarm_investigation"]
        assert len(summary_facts) >= 1
    
    @pytest.mark.asyncio
    @patch('src.promptrca.core.swarm_orchestrator.set_aws_client')
    @patch('src.promptrca.core.swarm_orchestrator.clear_aws_client')
    async def test_investigate_full_flow(self, mock_clear_aws, mock_set_aws, orchestrator, sample_inputs):
        """Test the full investigation flow."""
        # Mock the swarm execution
        mock_swarm_result = Mock(
            content='''
            ```json
            {
                "facts": [
                    {
                        "source": "test_specialist",
                        "content": "Test fact found",
                        "confidence": 0.8,
                        "metadata": {}
                    }
                ]
            }
            ```
            '''
        )
        
        with patch.object(orchestrator, '_parse_inputs') as mock_parse, \
             patch.object(orchestrator, '_discover_resources') as mock_discover, \
             patch.object(orchestrator.swarm, '__call__') as mock_swarm_call, \
             patch.object(orchestrator, '_run_hypothesis_agent') as mock_hypotheses, \
             patch.object(orchestrator, '_analyze_root_cause') as mock_root_cause:
            
            # Setup mocks
            mock_parse.return_value = Mock(
                primary_targets=[Mock(type="lambda", name="test-function", region="us-east-1")],
                trace_ids=["1-67890123-abcdef1234567890abcdef12"]
            )
            mock_discover.return_value = [{"type": "lambda", "name": "test-function"}]
            mock_swarm_call.return_value = mock_swarm_result
            mock_hypotheses.return_value = []
            mock_root_cause.return_value = Mock(confidence_score=0.8, analysis_summary="Test analysis")
            
            # Run investigation
            result = await orchestrator.investigate(sample_inputs)
            
            # Verify the flow
            assert result.status == "completed"
            assert mock_set_aws.called
            assert mock_clear_aws.called
            assert mock_swarm_call.called
    
    @pytest.mark.asyncio
    async def test_investigate_error_handling(self, orchestrator, sample_inputs):
        """Test error handling in investigation."""
        with patch.object(orchestrator, '_parse_inputs', side_effect=Exception("Parse error")):
            result = await orchestrator.investigate(sample_inputs)
            
            assert result.status == "failed"
            assert "Parse error" in result.summary


# Test the tool functions
class TestSwarmTools:
    """Test the tool-wrapped specialist functions."""
    
    def test_lambda_specialist_tool(self):
        """Test the lambda specialist tool."""
        from src.promptrca.core.swarm_orchestrator import lambda_specialist_tool
        
        resource_data = json.dumps({
            "type": "lambda",
            "name": "test-function",
            "arn": "arn:aws:lambda:us-east-1:123456789012:function:test-function"
        })
        
        investigation_context = json.dumps({
            "trace_ids": ["1-67890123-abcdef1234567890abcdef12"],
            "region": "us-east-1"
        })
        
        with patch('src.promptrca.specialists.LambdaSpecialist') as mock_specialist_class:
            mock_specialist = Mock()
            mock_specialist_class.return_value = mock_specialist
            
            # Mock the async analyze method
            async def mock_analyze(resource, context):
                return [
                    Fact(source="lambda", content="Test fact", confidence=0.8, metadata={})
                ]
            
            mock_specialist.analyze = mock_analyze
            
            result = lambda_specialist_tool(resource_data, investigation_context)
            
            # Should return JSON with facts
            result_data = json.loads(result)
            assert result_data["specialist_type"] == "lambda"
            assert result_data["resource_name"] == "test-function"
            assert len(result_data["facts"]) == 1
            assert result_data["facts"][0]["content"] == "Test fact"
    
    def test_tool_error_handling(self):
        """Test tool error handling."""
        from src.promptrca.core.swarm_orchestrator import lambda_specialist_tool
        
        # Invalid JSON should be handled gracefully
        result = lambda_specialist_tool("invalid json", "{}")
        
        result_data = json.loads(result)
        assert "error" in result_data
        assert result_data["specialist_type"] == "lambda"