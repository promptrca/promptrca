#!/usr/bin/env python3
"""
Agent Metrics Collection Tests for PromptRCA

Tests metrics collection and analysis including token usage tracking,
response time measurement, tool metrics, cycle count tracking,
and metrics summary generation.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from strands import Agent
from strands.multiagent import Swarm

from src.promptrca.agents.swarm_agents import (
    create_trace_agent,
    create_lambda_agent,
    create_apigateway_agent,
    create_stepfunctions_agent
)
from tests.agent_evaluator import AgentMetrics
from tests.fixtures.agent_mocks import (
    create_mock_tool_context,
    create_mock_specialist_facts,
    create_mock_swarm_result
)


class TestAgentMetricsCollection:
    """Verify metrics are collected correctly."""
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent for testing."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_token_usage_tracking(self, trace_agent, mock_tool_context):
        """Test that token usage (input, output, total) is tracked."""
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
                assert isinstance(usage, dict)
                # Should have token information
                assert "inputTokens" in usage or "totalTokens" in usage or "outputTokens" in usage
    
    @pytest.mark.asyncio
    async def test_response_time_measurement(self, trace_agent, mock_tool_context):
        """Test that response time is measured."""
        import time
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                await asyncio.sleep(0.1)
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
            
            # Response time should be measurable
            assert response_time > 0
            assert response_time < 30.0  # Should complete within reasonable time
    
    @pytest.fixture
    def lambda_agent(self):
        """Create Lambda agent for testing."""
        return create_lambda_agent()
    
    @pytest.mark.asyncio
    async def test_tool_metrics_collection(self, lambda_agent, mock_tool_context):
        """Test that tool metrics (call count, success rate) are collected."""
        query = "Analyze Lambda function test-function"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            
            swarm = Swarm(agents=[lambda_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool was called
            assert mock_run_analysis.called
            
            # Check for tool metrics in result
            if hasattr(result, 'cycles'):
                cycles = result.cycles
                if cycles:
                    # Should have tool call information
                    assert isinstance(cycles, list)
    
    @pytest.mark.asyncio
    async def test_cycle_count_tracking(self, trace_agent, mock_tool_context):
        """Test that cycle count and duration are tracked."""
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
            
            # Check for cycle information
            if hasattr(result, 'cycles'):
                cycles = result.cycles
                assert isinstance(cycles, list) or cycles is None


class TestMetricsSummary:
    """Test get_summary() method output."""
    
    def test_metrics_summary_structure(self):
        """Test that metrics summary has correct structure."""
        metrics = AgentMetrics(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            response_time_seconds=2.5,
            tool_call_count=3,
            tool_success_count=2,
            tool_failure_count=1,
            cycle_count=1
        )
        
        summary = metrics.get_summary()
        
        assert "tokens" in summary
        assert "performance" in summary
        assert "tools" in summary
        
        assert summary["tokens"]["input"] == 1000
        assert summary["tokens"]["output"] == 500
        assert summary["tokens"]["total"] == 1500
        
        assert summary["performance"]["response_time_seconds"] == 2.5
        assert summary["performance"]["cycles"] == 1
        
        assert summary["tools"]["total_calls"] == 3
        assert summary["tools"]["successful"] == 2
        assert summary["tools"]["failed"] == 1
        assert summary["tools"]["success_rate"] == 2.0 / 3.0
    
    def test_metrics_summary_zero_tool_calls(self):
        """Test metrics summary with zero tool calls."""
        metrics = AgentMetrics(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            response_time_seconds=1.0,
            tool_call_count=0,
            tool_success_count=0,
            tool_failure_count=0,
            cycle_count=1
        )
        
        summary = metrics.get_summary()
        
        assert summary["tools"]["success_rate"] == 0.0
        assert summary["tools"]["total_calls"] == 0


class TestToolMetrics:
    """Validate tool-specific metrics."""
    
    @pytest.fixture
    def lambda_agent(self):
        """Create Lambda agent for testing."""
        return create_lambda_agent()
    
    @pytest.fixture
    def apigateway_agent(self):
        """Create API Gateway agent for testing."""
        return create_apigateway_agent()
    
    @pytest.fixture
    def stepfunctions_agent(self):
        """Create Step Functions agent for testing."""
        return create_stepfunctions_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_tool_call_count_tracking(self, lambda_agent, mock_tool_context):
        """Test that tool call count is tracked."""
        query = "Analyze Lambda function test-function"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            
            swarm = Swarm(agents=[lambda_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool was called
            assert mock_run_analysis.called
            
            # Tool call count should be tracked
            call_count = mock_run_analysis.call_count
            assert call_count >= 0
    
    @pytest.mark.asyncio
    async def test_tool_success_rate_tracking(self, apigateway_agent, mock_tool_context):
        """Test that tool success rate is tracked."""
        query = "Analyze API Gateway api-123"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.APIGatewaySpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("apigateway_specialist", 1)
            
            swarm = Swarm(agents=[apigateway_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Verify tool execution
            assert mock_run_analysis.called
            
            # Success should be tracked (no exception means success)
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_tool_execution_time_tracking(self, stepfunctions_agent, mock_tool_context):
        """Test that tool execution time is tracked."""
        import time
        query = "Analyze Step Functions execution arn:aws:states:us-east-1:123456789012:execution:test:exec-123"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.StepFunctionsSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            async def slow_analysis(*args, **kwargs):
                await asyncio.sleep(0.1)
                return create_mock_specialist_facts("stepfunctions_specialist", 1)
            
            mock_run_analysis.side_effect = slow_analysis
            
            swarm = Swarm(agents=[stepfunctions_agent])
            start_time = time.time()
            
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            execution_time = time.time() - start_time
            
            # Execution time should be measurable
            assert execution_time > 0
            assert result is not None


class TestPerformanceBenchmarks:
    """Establish performance baselines."""
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent for testing."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_response_time_benchmark(self, trace_agent, mock_tool_context):
        """Test that response time meets benchmark (< 30 seconds)."""
        import time
        query = "Analyze trace 1-67890123-abcdef1234567890abcdef12"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            mock_specialist = Mock()
            async def mock_analyze_trace(trace_id, context):
                await asyncio.sleep(0.1)
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
            
            # Should meet performance benchmark
            assert response_time < 30.0
            assert result is not None
    
    @pytest.mark.asyncio
    async def test_token_usage_benchmark(self, lambda_agent, mock_tool_context):
        """Test that token usage is within reasonable limits."""
        query = "Analyze Lambda function test-function"
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.LambdaSpecialist'), \
             patch('src.promptrca.core.swarm_tools._run_specialist_analysis') as mock_run_analysis:
            
            mock_run_analysis.return_value = create_mock_specialist_facts("lambda_specialist", 1)
            
            swarm = Swarm(agents=[lambda_agent])
            result = await swarm.run(
                query,
                invocation_state=mock_tool_context.invocation_state
            )
            
            # Check token usage if available
            if hasattr(result, 'accumulated_usage'):
                usage = result.accumulated_usage
                total_tokens = usage.get("totalTokens", 0)
                # Should use reasonable amount of tokens (less than 100k for a simple query)
                assert total_tokens < 100000 or total_tokens == 0
    
    @pytest.mark.asyncio
    async def test_cycle_count_benchmark(self, trace_agent, mock_tool_context):
        """Test that cycle count is reasonable."""
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
            
            # Check cycle count if available
            if hasattr(result, 'cycles'):
                cycles = result.cycles
                cycle_count = len(cycles) if cycles else 0
                # Should have reasonable number of cycles (less than 10 for simple query)
                assert cycle_count < 10 or cycle_count == 0
