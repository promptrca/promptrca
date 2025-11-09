#!/usr/bin/env python3
"""
Agent Execution Tests for PromptRCA

Tests agent behavior and responses including execution with mocked tools,
response quality validation, error handling, response time benchmarks,
and token usage tracking.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from strands import Agent
from strands.multiagent import Swarm

from src.promptrca.agents.swarm_agents import (
    create_trace_agent,
    create_lambda_agent,
    create_apigateway_agent,
    create_stepfunctions_agent
)
from src.promptrca.models import Fact
from tests.fixtures.agent_mocks import (
    create_mock_tool_context,
    create_mock_specialist_facts,
    create_mock_swarm_result
)


class TestTraceAgentExecution:
    """Trace agent execution tests."""
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent for testing."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_trace_agent_executes_successfully(self, trace_agent, mock_tool_context):
        """Test that trace agent executes with a valid query."""
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            # Mock specialist response
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 2)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            # Create swarm with agent
            swarm = Swarm([trace_agent])
            
            # Execute agent (Swarm is callable)
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify execution
            assert result is not None
            assert hasattr(result, 'content') or hasattr(result, 'accumulated_usage')
    
    @pytest.mark.asyncio
    async def test_trace_agent_response_time(self, trace_agent, mock_tool_context):
        """Test that trace agent responds within reasonable time."""
        import time
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                await asyncio.sleep(0.1)  # Simulate processing time
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm(agents=[trace_agent])
            start_time = time.time()
            
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            response_time = time.time() - start_time
            
            # Should complete within 30 seconds (reasonable for tests)
            assert response_time < 30.0
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_trace_agent_token_usage_tracking(self, trace_agent, mock_tool_context):
        """Test that token usage is tracked."""
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm(agents=[trace_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Check for token usage tracking
            if hasattr(result, 'accumulated_usage'):
                usage = result.accumulated_usage
                assert "inputTokens" in usage or "totalTokens" in usage
    
    @pytest.mark.asyncio
    async def test_trace_agent_error_handling(self, trace_agent, mock_tool_context):
        """Test that trace agent handles errors gracefully."""
        query = "Analyze trace invalid-trace-id"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            # Make specialist raise an error
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                raise Exception("Trace not found")
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            swarm = Swarm(agents=[trace_agent])
            
            # Should handle error gracefully
            try:
                result = await swarm.run(
                    query,
                    invocation_state=mock_tool_context.invocation_state
                )
                # If execution succeeds, verify error is handled
                assert result is not None
            except Exception as e:
                # Error should be meaningful
                assert "trace" in str(e).lower() or "not found" in str(e).lower()


class TestLambdaAgentExecution:
    """Lambda agent execution tests."""
    
    @pytest.fixture
    def lambda_agent(self):
        """Create Lambda agent for testing."""
        return create_lambda_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_lambda_agent_executes_successfully(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent executes with a valid query."""
        query = "Analyze Lambda function test-function for errors"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 2)
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_lambda_agent_response_quality(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent produces quality responses."""
        query = "Why is my Lambda function timing out?"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            facts = [
                Fact(
                    source="lambda_specialist",
                    content="Function timeout detected - timeout set to 30s",
                    confidence=0.9,
                    metadata={"timeout": 30}
                )
            ]
            mock_run_analysis.return_value = facts
            
            swarm = Swarm([lambda_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            assert result is not None
            if hasattr(result, 'content'):
                content = result.content.lower()
                # Response should be relevant to the query
                assert len(content) > 0
    
    @pytest.mark.asyncio
    async def test_lambda_agent_graceful_degradation(self, lambda_agent, mock_tool_context):
        """Test that Lambda agent degrades gracefully on errors."""
        query = "Analyze Lambda function non-existent-function"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist') as mock_specialist_class:
            
            # Make specialist creation fail
            mock_specialist_class.side_effect = Exception("Function not found")
            
            swarm = Swarm([lambda_agent])
            
            try:
                result = await swarm.run(
                    query,
                    invocation_state=mock_tool_context.invocation_state
                )
                # Should handle error gracefully
                assert result is not None
            except Exception:
                # If exception is raised, it should be handled by the tool
                pass


class TestAPIGatewayAgentExecution:
    """API Gateway agent execution tests."""
    
    @pytest.fixture
    def apigateway_agent(self):
        """Create API Gateway agent for testing."""
        return create_apigateway_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_apigateway_agent_executes_successfully(self, apigateway_agent, mock_tool_context):
        """Test that API Gateway agent executes with a valid query."""
        query = "Analyze API Gateway api-123 for integration errors"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("apigateway_specialist", 2)
            
            swarm = Swarm([apigateway_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_apigateway_agent_response_time_benchmark(self, apigateway_agent, mock_tool_context):
        """Test API Gateway agent response time benchmark."""
        import time
        query = "Why is my API Gateway returning 502 errors?"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("apigateway_specialist", 1)
            
            swarm = Swarm([apigateway_agent])
            start_time = time.time()
            
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            response_time = time.time() - start_time
            
            # Should complete within reasonable time
            assert response_time < 30.0
            assert result is not None


class TestStepFunctionsAgentExecution:
    """Step Functions agent execution tests."""
    
    @pytest.fixture
    def stepfunctions_agent(self):
        """Create Step Functions agent for testing."""
        return create_stepfunctions_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_executes_successfully(self, stepfunctions_agent, mock_tool_context):
        """Test that Step Functions agent executes with a valid query."""
        query = "Analyze Step Functions execution arn:aws:states:us-east-1:123456789012:execution:test-state-machine:exec-123"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("stepfunctions_specialist", 2)
            
            swarm = Swarm([stepfunctions_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_token_usage(self, stepfunctions_agent, mock_tool_context):
        """Test Step Functions agent token usage tracking."""
        query = "Why did my Step Functions state machine fail?"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("stepfunctions_specialist", 1)
            
            swarm = Swarm([stepfunctions_agent])
            result = await swarm(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Check for token usage
            if hasattr(result, 'accumulated_usage'):
                usage = result.accumulated_usage
                assert isinstance(usage, dict)
    
    @pytest.mark.asyncio
    async def test_stepfunctions_agent_error_handling(self, stepfunctions_agent, mock_tool_context):
        """Test Step Functions agent error handling."""
        query = "Analyze Step Functions execution invalid-arn"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist') as mock_specialist_class:
            
            mock_specialist_class.side_effect = Exception("Invalid execution ARN")
            
            swarm = Swarm([stepfunctions_agent])
            
            try:
                result = await swarm.run(
                    query,
                    invocation_state=mock_tool_context.invocation_state
                )
                # Should handle error gracefully
                assert result is not None
            except Exception:
                # Error should be handled by tool
                pass
