#!/usr/bin/env python3
"""
Agent Evaluation Framework Tests for PromptRCA

Tests the evaluation framework itself including test case loading,
evaluation execution flow, results export, LLM judge integration,
and comparison between agent configurations.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import pytest
import json
import tempfile
import os
from pathlib import Path

from strands import Agent

from src.promptrca.agents.swarm_agents import (
    create_trace_agent,
    create_lambda_agent,
    create_apigateway_agent,
    create_stepfunctions_agent
)
from tests.agent_evaluator import (
    AgentEvaluator,
    AgentTestCase,
    TestCase,  # Alias for backward compatibility
    EvaluationResult,
    AgentMetrics
)
from tests.fixtures.agent_mocks import create_mock_tool_context


class TestTestCaseLoading:
    """Test case loading and validation."""
    
    def test_load_test_cases_from_json(self):
        """Test loading test cases from JSON file."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        evaluator = AgentEvaluator(test_cases_path=test_cases_path)
        
        assert len(evaluator.test_cases) > 0
        assert all(isinstance(tc, AgentTestCase) for tc in evaluator.test_cases)
    
    def test_load_test_cases_invalid_path(self):
        """Test loading test cases with invalid path raises error."""
        with pytest.raises(FileNotFoundError):
            AgentEvaluator(test_cases_path="nonexistent/path.json")
    
    def test_test_case_structure(self):
        """Test that test cases have correct structure."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        evaluator = AgentEvaluator(test_cases_path=test_cases_path)
        
        # Check first test case structure
        if evaluator.test_cases:
            tc = evaluator.test_cases[0]
            assert hasattr(tc, 'id')
            assert hasattr(tc, 'query')
            assert hasattr(tc, 'category')
            assert hasattr(tc, 'agent')
    
    def test_filter_test_cases_by_agent(self):
        """Test filtering test cases by agent name."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        evaluator = AgentEvaluator(test_cases_path=test_cases_path)
        
        trace_cases = [tc for tc in evaluator.test_cases if tc.agent == "trace_specialist"]
        lambda_cases = [tc for tc in evaluator.test_cases if tc.agent == "lambda_specialist"]
        
        assert len(trace_cases) > 0
        assert len(lambda_cases) > 0


class TestEvaluationExecutionFlow:
    """Test evaluation execution flow."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        return AgentEvaluator(test_cases_path=test_cases_path)
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_evaluate_agent_execution(self, evaluator, trace_agent, mock_tool_context):
        """Test that agent evaluation executes successfully."""
        from unittest.mock import patch
        
        test_cases = [tc for tc in evaluator.test_cases if tc.agent == "trace_specialist"][:1]
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            from tests.fixtures.agent_mocks import create_mock_specialist_facts
            mock_specialist = type('MockSpecialist', (), {})()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            results = await evaluator.evaluate_agent(
                trace_agent,
                "trace_specialist",
                test_cases=test_cases,
                mock_tool_context=mock_tool_context
            )
            
            assert len(results) > 0
            assert all(isinstance(r, EvaluationResult) for r in results)
    
    @pytest.mark.asyncio
    async def test_evaluation_result_structure(self, evaluator, trace_agent, mock_tool_context):
        """Test that evaluation results have correct structure."""
        from unittest.mock import patch
        
        test_cases = [tc for tc in evaluator.test_cases if tc.agent == "trace_specialist"][:1]
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            from tests.fixtures.agent_mocks import create_mock_specialist_facts
            mock_specialist = type('MockSpecialist', (), {})()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            results = await evaluator.evaluate_agent(
                trace_agent,
                "trace_specialist",
                test_cases=test_cases,
                mock_tool_context=mock_tool_context
            )
            
            if results:
                result = results[0]
                assert hasattr(result, 'test_case_id')
                assert hasattr(result, 'agent_name')
                assert hasattr(result, 'query')
                assert hasattr(result, 'success')
                assert hasattr(result, 'metrics')
    
    @pytest.mark.asyncio
    async def test_evaluation_handles_errors(self, evaluator, trace_agent, mock_tool_context):
        """Test that evaluation handles errors gracefully."""
        from unittest.mock import patch
        
        # Create a test case that will cause an error
        error_test_case = AgentTestCase(
            id="error-test",
            query="Invalid query that causes error",
            category="edge_cases",
            agent="trace_specialist"
        )
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            # Make specialist raise an error
            mock_specialist_class.side_effect = Exception("Test error")
            
            results = await evaluator.evaluate_agent(
                trace_agent,
                "trace_specialist",
                test_cases=[error_test_case],
                mock_tool_context=mock_tool_context
            )
            
            # Should handle error and return result
            assert len(results) > 0
            assert results[0].success is False
            assert results[0].error is not None


class TestResultsExport:
    """Test results export (CSV/JSON)."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        return AgentEvaluator(test_cases_path=test_cases_path)
    
    def test_export_results_json(self, evaluator):
        """Test exporting results to JSON."""
        # Create sample results
        result = EvaluationResult(
            test_case_id="test-1",
            agent_name="trace_specialist",
            query="Test query",
            success=True,
            response_content="Test response",
            metrics=AgentMetrics(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                response_time_seconds=1.0
            )
        )
        evaluator.results = [result]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            evaluator.export_results(temp_path, format="json")
            
            # Verify file was created and contains data
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                data = json.load(f)
                assert len(data) == 1
                assert data[0]["test_case_id"] == "test-1"
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_export_results_csv(self, evaluator):
        """Test exporting results to CSV."""
        # Create sample results
        result = EvaluationResult(
            test_case_id="test-1",
            agent_name="trace_specialist",
            query="Test query",
            success=True,
            response_content="Test response",
            metrics=AgentMetrics(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                response_time_seconds=1.0
            )
        )
        evaluator.results = [result]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            temp_path = f.name
        
        try:
            evaluator.export_results(temp_path, format="csv")
            
            # Verify file was created
            assert os.path.exists(temp_path)
            with open(temp_path, 'r') as f:
                content = f.read()
                assert "test_case_id" in content
                assert "test-1" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_export_results_invalid_format(self, evaluator):
        """Test exporting with invalid format raises error."""
        result = EvaluationResult(
            test_case_id="test-1",
            agent_name="trace_specialist",
            query="Test query",
            success=True,
            response_content="Test response",
            metrics=AgentMetrics()
        )
        evaluator.results = [result]
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError):
                evaluator.export_results(temp_path, format="invalid")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


class TestResultsAnalysis:
    """Test results analysis and metrics generation."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        return AgentEvaluator(test_cases_path=test_cases_path)
    
    def test_analyze_results_summary(self, evaluator):
        """Test that analyze_results generates summary."""
        # Create sample results
        results = [
            EvaluationResult(
                test_case_id="test-1",
                agent_name="trace_specialist",
                query="Test query 1",
                success=True,
                response_content="Response 1",
                metrics=AgentMetrics(
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    response_time_seconds=1.0,
                    tool_call_count=1,
                    tool_success_count=1
                )
            ),
            EvaluationResult(
                test_case_id="test-2",
                agent_name="trace_specialist",
                query="Test query 2",
                success=False,
                response_content="Response 2",
                metrics=AgentMetrics(
                    input_tokens=200,
                    output_tokens=100,
                    total_tokens=300,
                    response_time_seconds=2.0,
                    tool_call_count=1,
                    tool_success_count=0,
                    tool_failure_count=1
                )
            )
        ]
        
        analysis = evaluator.analyze_results(results, agent_name="trace_specialist")
        
        assert "summary" in analysis
        assert analysis["summary"]["total_tests"] == 2
        assert analysis["summary"]["successful_tests"] == 1
        assert analysis["summary"]["failed_tests"] == 1
        assert analysis["summary"]["success_rate"] == 0.5
    
    def test_analyze_results_metrics(self, evaluator):
        """Test that analyze_results includes metrics."""
        results = [
            EvaluationResult(
                test_case_id="test-1",
                agent_name="lambda_specialist",
                query="Test query",
                success=True,
                response_content="Response",
                metrics=AgentMetrics(
                    input_tokens=1000,
                    output_tokens=500,
                    total_tokens=1500,
                    response_time_seconds=2.5,
                    tool_call_count=3,
                    tool_success_count=2,
                    tool_failure_count=1
                )
            )
        ]
        
        analysis = evaluator.analyze_results(results)
        
        assert "metrics" in analysis
        assert "tokens" in analysis["metrics"]
        assert "performance" in analysis["metrics"]
        assert "tools" in analysis["metrics"]
        
        assert analysis["metrics"]["tokens"]["total"] == 1500
        assert analysis["metrics"]["performance"]["avg_response_time_seconds"] == 2.5
        assert analysis["metrics"]["tools"]["total_calls"] == 3
    
    def test_analyze_results_tool_usage(self, evaluator):
        """Test that analyze_results includes tool usage."""
        results = [
            EvaluationResult(
                test_case_id="test-1",
                agent_name="trace_specialist",
                query="Test query",
                success=True,
                response_content="Response",
                tool_used="trace_specialist_tool",
                metrics=AgentMetrics()
            )
        ]
        
        analysis = evaluator.analyze_results(results)
        
        assert "tool_usage" in analysis
        assert "trace_specialist_tool" in analysis["tool_usage"]


class TestAgentComparison:
    """Test comparison between agent configurations."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        return AgentEvaluator(test_cases_path=test_cases_path)
    
    def test_compare_agents(self, evaluator):
        """Test comparing multiple agent configurations."""
        # Create sample results for different agents
        evaluator.results = [
            EvaluationResult(
                test_case_id="test-1",
                agent_name="trace_specialist",
                query="Test query",
                success=True,
                response_content="Response",
                metrics=AgentMetrics(
                    input_tokens=100,
                    output_tokens=50,
                    total_tokens=150,
                    response_time_seconds=1.0
                )
            ),
            EvaluationResult(
                test_case_id="test-2",
                agent_name="lambda_specialist",
                query="Test query",
                success=True,
                response_content="Response",
                metrics=AgentMetrics(
                    input_tokens=200,
                    output_tokens=100,
                    total_tokens=300,
                    response_time_seconds=2.0
                )
            )
        ]
        
        agent_configs = [
            {"name": "trace_specialist", "agent": create_trace_agent()},
            {"name": "lambda_specialist", "agent": create_lambda_agent()}
        ]
        
        comparison = evaluator.compare_agents(agent_configs)
        
        assert "trace_specialist" in comparison
        assert "lambda_specialist" in comparison
        
        assert comparison["trace_specialist"]["summary"]["total_tests"] == 1
        assert comparison["lambda_specialist"]["summary"]["total_tests"] == 1


class TestToolUsageEvaluation:
    """Test tool usage accuracy evaluation."""
    
    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance."""
        test_cases_path = "tests/test_data/agent_test_cases.json"
        return AgentEvaluator(test_cases_path=test_cases_path)
    
    @pytest.fixture
    def trace_agent(self):
        """Create trace agent."""
        return create_trace_agent()
    
    @pytest.fixture
    def mock_tool_context(self):
        """Create mock tool context."""
        return create_mock_tool_context()
    
    @pytest.mark.asyncio
    async def test_evaluate_tool_usage_accuracy(self, evaluator, trace_agent, mock_tool_context):
        """Test tool usage accuracy evaluation."""
        from unittest.mock import patch
        
        tool_test_cases = [
            AgentTestCase(
                id="tool-test-1",
                query="Analyze trace 1-67890123-abcdef1234567890abcdef12",
                expected_tool="trace_specialist_tool",
                category="tool_usage",
                agent="trace_specialist"
            )
        ]
        
        with patch('src.promptrca.core.swarm_tools.set_aws_client'), \
             patch('src.promptrca.core.swarm_tools.TraceSpecialist') as mock_specialist_class:
            
            from tests.fixtures.agent_mocks import create_mock_specialist_facts
            mock_specialist = type('MockSpecialist', (), {})()
            async def mock_analyze_trace(trace_id, context):
                return create_mock_specialist_facts("trace_specialist", 1)
            mock_specialist.analyze_trace = mock_analyze_trace
            mock_specialist_class.return_value = mock_specialist
            
            tool_usage_result = await evaluator.evaluate_tool_usage(
                trace_agent,
                tool_test_cases,
                mock_tool_context
            )
            
            assert "total_tests" in tool_usage_result
            assert "correct_selections" in tool_usage_result
            assert "accuracy" in tool_usage_result
            assert "details" in tool_usage_result
