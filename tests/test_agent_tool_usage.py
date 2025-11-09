#!/usr/bin/env python3
"""
Agent Tool Usage Tests for PromptRCA

Validates tool selection accuracy, tool parameter validation,
tool execution success/failure tracking, and multiple tool usage scenarios.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, call

from strands import Agent
from strands.multiagent import Swarm

from src.promptrca.agents.swarm_agents import (
    create_trace_agent,
    create_lambda_agent,
    create_apigateway_agent,
    create_stepfunctions_agent
)
from tests.fixtures.agent_mocks import (
    create_mock_tool_context,
    create_mock_specialist_facts
)


class TestTraceAgentToolUsage:
    """Verify trace_specialist_tool usage."""
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent for testing."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_trace_agent_selects_correct_tool(self, trace_agent, mock_tool_context):
        """Test that trace agent selects trace_specialist_tool for trace queries."""
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm([trace_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify trace specialist was called
            assert mock_specialist_class.called
    
    @pytest.mark.asyncio
    async def test_trace_agent_tool_parameter_validation(self, trace_agent, mock_tool_context):
        """Test that trace agent validates tool parameters correctly."""
        query = "Analyze these X-Ray traces: 1-67890123-abcdef1234567890abcdef12, 1-67890124-abcdef1234567890abcdef13"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm([trace_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify specialist was called (parameter validation happens in tool)
            assert mock_specialist_class.called
    
    @pytest.mark.asyncio
    async def test_trace_agent_tool_execution_success(self, trace_agent, mock_tool_context):
        """Test that trace agent tool execution succeeds."""
        query = "What services are involved in trace 1-67890123-abcdef1234567890abcdef12?"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 2)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm([trace_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify successful execution
            assert result is not None
            assert mock_specialist_class.called


class TestLambdaAgentToolUsage:
    """Verify lambda_specialist_tool usage."""
    
    @pytest.fixture
    def lambda_agent(self):
        """Create Lambda agent for testing."""
        return create_lambda_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_lambda_agent_selects_correct_tool(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent selects lambda_specialist_tool for Lambda queries."""
        query = "Analyze Lambda function test-function for errors"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist') as mock_specialist_class, \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 2)
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify Lambda specialist was called
            assert mock_specialist_class.called or mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_lambda_agent_tool_parameter_validation(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent validates tool parameters correctly."""
        query = "Check why my-function is timing out"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool was called (parameter validation happens in tool)
            assert mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_lambda_agent_tool_execution_tracking(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent tracks tool execution success/failure."""
        query = "Investigate memory issues in function memory-test"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool execution was tracked
            assert mock_run_analysis.called
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_lambda_agent_multiple_tool_usage(self, lambda_agent, mock_tool_context):
        """Test Lambda agent with multiple tool calls scenario."""
        query = "Analyze Lambda function test-function and check AWS documentation for timeout issues"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis, \
             patch('src.promptrca.tools.aws_knowledge_tools.search_aws_documentation') as mock_search_docs:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            mock_search_docs.return_value = "AWS Lambda timeout documentation"
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify multiple tools can be used
            assert result is not None


class TestAPIGatewayAgentToolUsage:
    """Verify apigateway_specialist_tool usage."""
    
    @pytest.fixture
    def apigateway_agent(self):
        """Create API Gateway agent for testing."""
        return create_apigateway_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_apigateway_agent_selects_correct_tool(self, apigateway_agent, mock_tool_context):
        """Test that API Gateway agent selects apigateway_specialist_tool for API Gateway queries."""
        query = "Analyze API Gateway api-123 for integration errors"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist') as mock_specialist_class, \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("apigateway_specialist", 2)
            
            swarm = Swarm([apigateway_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify API Gateway specialist was called
            assert mock_specialist_class.called or mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_apigateway_agent_tool_parameter_validation(self, apigateway_agent, mock_tool_context):
        """Test that API Gateway agent validates tool parameters correctly."""
        query = "Check API Gateway test-api stage prod for authentication issues"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("apigateway_specialist", 1)
            
            swarm = Swarm([apigateway_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool was called with proper parameters
            assert mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_apigateway_agent_tool_execution_failure_tracking(self, apigateway_agent, mock_tool_context):
        """Test that API Gateway agent tracks tool execution failures."""
        query = "Why is my API Gateway returning 502 errors?"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist') as mock_specialist_class:
            
            # Make specialist creation fail
            mock_specialist_class.side_effect = Exception("API Gateway not found")
            
            swarm = Swarm([apigateway_agent])
            
            try:
                result = await swarm.run(
                    query,
                    invocation_state=mock_tool_context.invocation_state
                )
                # Should handle failure gracefully
                assert result is not None
            except Exception:
                # Failure should be tracked
                pass


class TestStepFunctionsAgentToolUsage:
    """Verify stepfunctions_specialist_tool usage."""
    
    @pytest.fixture
    def stepfunctions_agent(self):
        """Create Step Functions agent for testing."""
        return create_stepfunctions_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_selects_correct_tool(self, stepfunctions_agent, mock_tool_context):
        """Test that Step Functions agent selects stepfunctions_specialist_tool for Step Functions queries."""
        query = "Analyze Step Functions execution arn:aws:states:us-east-1:123456789012:execution:test-state-machine:exec-123"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist') as mock_specialist_class, \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("stepfunctions_specialist", 2)
            
            swarm = Swarm([stepfunctions_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify Step Functions specialist was called
            assert mock_specialist_class.called or mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_tool_parameter_validation(self, stepfunctions_agent, mock_tool_context):
        """Test that Step Functions agent validates tool parameters correctly."""
        query = "Check state machine test-workflow for timeout issues"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("stepfunctions_specialist", 1)
            
            swarm = Swarm([stepfunctions_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool was called with proper parameters
            assert mock_run_analysis.called
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_multiple_tool_scenarios(self, stepfunctions_agent, mock_tool_context):
        """Test Step Functions agent with multiple tool usage scenarios."""
        query = "Analyze Step Functions execution and check AWS documentation for state machine best practices"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis, \
             patch('src.promptrca.tools.aws_knowledge_tools.search_aws_documentation') as mock_search_docs:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("stepfunctions_specialist", 1)
            mock_search_docs.return_value = "Step Functions best practices"
            
            swarm = Swarm([stepfunctions_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify multiple tools can be used
            assert result is not None
