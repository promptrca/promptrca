#!/usr/bin/env python3
"""
Agent Evaluation Framework for PromptRCA

Provides reusable evaluation framework for testing Strands agents following
official Strands documentation patterns. Supports agent execution tests,
tool usage validation, metrics collection, and evaluation reports.

Copyright (C) 2025 Christian Gennaro Faraone
"""

import json
import csv
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from strands import Agent
from strands.multiagent import Swarm

from src.promptrca.models import Fact


@dataclass
class AgentMetrics:
    """Metrics collected during agent execution."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    response_time_seconds: float = 0.0
    tool_call_count: int = 0
    tool_success_count: int = 0
    tool_failure_count: int = 0
    cycle_count: int = 0
    cycles: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of metrics."""
        return {
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens
            },
            "performance": {
                "response_time_seconds": self.response_time_seconds,
                "cycles": self.cycle_count
            },
            "tools": {
                "total_calls": self.tool_call_count,
                "successful": self.tool_success_count,
                "failed": self.tool_failure_count,
                "success_rate": (
                    self.tool_success_count / self.tool_call_count 
                    if self.tool_call_count > 0 else 0.0
                )
            }
        }


@dataclass
class TestCase:
    """Represents a single test case."""
    id: str
    query: str
    category: str
    agent: str
    expected_tool: Optional[str] = None
    expected_content: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """Result of evaluating a single test case."""
    test_case_id: str
    agent_name: str
    query: str
    success: bool
    response_content: str
    metrics: AgentMetrics
    tool_used: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "test_case_id": self.test_case_id,
            "agent_name": self.agent_name,
            "query": self.query,
            "success": self.success,
            "response_content": self.response_content[:500] if self.response_content else "",  # Truncate for CSV
            "tool_used": self.tool_used,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "metrics": asdict(self.metrics)
        }


class AgentEvaluator:
    """
    Reusable evaluation framework for testing Strands agents.
    
    Follows Strands documentation patterns for agent evaluation,
    metrics collection, and result analysis.
    """
    
    def __init__(self, test_cases_path: Optional[str] = None):
        """
        Initialize the evaluator.
        
        Args:
            test_cases_path: Path to JSON file containing test cases.
                            If None, test cases must be loaded separately.
        """
        self.test_cases_path = test_cases_path
        self.test_cases: List[TestCase] = []
        self.results: List[EvaluationResult] = []
        
        if test_cases_path:
            self.load_test_cases(test_cases_path)
    
    def load_test_cases(self, test_cases_path: str) -> None:
        """Load test cases from JSON file."""
        path = Path(test_cases_path)
        if not path.exists():
            raise FileNotFoundError(f"Test cases file not found: {test_cases_path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        self.test_cases = [
            TestCase(**case) for case in data
        ]
    
    def _extract_metrics(self, result: Any) -> AgentMetrics:
        """Extract metrics from agent execution result."""
        metrics = AgentMetrics()
        
        # Extract token usage
        if hasattr(result, 'accumulated_usage'):
            usage = result.accumulated_usage
            metrics.input_tokens = usage.get("inputTokens", 0)
            metrics.output_tokens = usage.get("outputTokens", 0)
            metrics.total_tokens = usage.get("totalTokens", 0)
        
        # Extract cycle information
        if hasattr(result, 'cycles'):
            cycles = result.cycles
            metrics.cycle_count = len(cycles) if cycles else 0
            metrics.cycles = [
                {
                    "agent": cycle.get("agent", "unknown"),
                    "content": cycle.get("content", "")[:100],  # Truncate
                    "tool_calls": len(cycle.get("tool_calls", []))
                }
                for cycle in cycles
            ] if cycles else []
        
        # Extract tool metrics from cycles
        if hasattr(result, 'cycles') and result.cycles:
            for cycle in result.cycles:
                tool_calls = cycle.get("tool_calls", [])
                metrics.tool_call_count += len(tool_calls)
                for tool_call in tool_calls:
                    if tool_call.get("status") == "success":
                        metrics.tool_success_count += 1
                    else:
                        metrics.tool_failure_count += 1
        
        return metrics
    
    def _extract_tool_used(self, result: Any) -> Optional[str]:
        """Extract the tool used from agent execution result."""
        if hasattr(result, 'cycles') and result.cycles:
            for cycle in result.cycles:
                tool_calls = cycle.get("tool_calls", [])
                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool_name")
                    if tool_name:
                        return tool_name
        return None
    
    async def evaluate_agent(
        self,
        agent: Agent,
        agent_name: str,
        test_cases: Optional[List[TestCase]] = None,
        mock_tool_context: Optional[Any] = None
    ) -> List[EvaluationResult]:
        """
        Run evaluation on a single agent.
        
        Args:
            agent: The agent to evaluate
            agent_name: Name of the agent for reporting
            test_cases: List of test cases to run. If None, uses loaded test cases.
            mock_tool_context: Mock ToolContext for testing
        
        Returns:
            List of evaluation results
        """
        if test_cases is None:
            test_cases = [tc for tc in self.test_cases if tc.agent == agent_name]
        
        if not test_cases:
            return []
        
        results = []
        
        for test_case in test_cases:
            try:
                start_time = time.time()
                
                # Execute agent with test query
                if mock_tool_context:
                    # For testing, we'll use a Swarm with the agent
                    swarm = Swarm(agents=[agent])
                    result = await swarm.run(
                        test_case.query,
                        invocation_state={"aws_client": mock_tool_context.invocation_state.get("aws_client")} if mock_tool_context else {}
                    )
                else:
                    swarm = Swarm(agents=[agent])
                    result = await swarm.run(test_case.query)
                
                response_time = time.time() - start_time
                
                # Extract metrics
                metrics = self._extract_metrics(result)
                metrics.response_time_seconds = response_time
                
                # Extract response content
                response_content = result.content if hasattr(result, 'content') else str(result)
                
                # Extract tool used
                tool_used = self._extract_tool_used(result)
                
                # Determine success
                success = True
                error = None
                
                if test_case.expected_tool and tool_used != test_case.expected_tool:
                    success = False
                    error = f"Expected tool '{test_case.expected_tool}' but got '{tool_used}'"
                
                if test_case.expected_content and test_case.expected_content.lower() not in response_content.lower():
                    success = False
                    if error:
                        error += f"; Expected content not found"
                    else:
                        error = "Expected content not found in response"
                
                result_obj = EvaluationResult(
                    test_case_id=test_case.id,
                    agent_name=agent_name,
                    query=test_case.query,
                    success=success,
                    response_content=response_content,
                    metrics=metrics,
                    tool_used=tool_used,
                    error=error
                )
                
                results.append(result_obj)
                self.results.append(result_obj)
                
            except Exception as e:
                # Handle execution errors
                error_result = EvaluationResult(
                    test_case_id=test_case.id,
                    agent_name=agent_name,
                    query=test_case.query,
                    success=False,
                    response_content="",
                    metrics=AgentMetrics(),
                    error=str(e)
                )
                results.append(error_result)
                self.results.append(error_result)
        
        return results
    
    def analyze_results(
        self,
        results: Optional[List[EvaluationResult]] = None,
        agent_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate metrics and analysis from evaluation results.
        
        Args:
            results: List of results to analyze. If None, uses all stored results.
            agent_name: Filter results by agent name. If None, analyzes all.
        
        Returns:
            Dictionary with analysis metrics
        """
        if results is None:
            results = self.results
        
        if agent_name:
            results = [r for r in results if r.agent_name == agent_name]
        
        if not results:
            return {"error": "No results to analyze"}
        
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        failed_tests = total_tests - successful_tests
        
        # Aggregate metrics
        total_input_tokens = sum(r.metrics.input_tokens for r in results)
        total_output_tokens = sum(r.metrics.output_tokens for r in results)
        total_tokens = sum(r.metrics.total_tokens for r in results)
        avg_response_time = sum(r.metrics.response_time_seconds for r in results) / total_tests if total_tests > 0 else 0.0
        total_tool_calls = sum(r.metrics.tool_call_count for r in results)
        total_tool_successes = sum(r.metrics.tool_success_count for r in results)
        total_tool_failures = sum(r.metrics.tool_failure_count for r in results)
        
        # Tool usage analysis
        tool_usage = {}
        for result in results:
            if result.tool_used:
                tool_usage[result.tool_used] = tool_usage.get(result.tool_used, 0) + 1
        
        # Category breakdown
        category_stats = {}
        for result in results:
            # Find test case category
            test_case = next((tc for tc in self.test_cases if tc.id == result.test_case_id), None)
            if test_case:
                category = test_case.category
                if category not in category_stats:
                    category_stats[category] = {"total": 0, "success": 0}
                category_stats[category]["total"] += 1
                if result.success:
                    category_stats[category]["success"] += 1
        
        return {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": successful_tests / total_tests if total_tests > 0 else 0.0
            },
            "metrics": {
                "tokens": {
                    "total_input": total_input_tokens,
                    "total_output": total_output_tokens,
                    "total": total_tokens,
                    "avg_per_test": total_tokens / total_tests if total_tests > 0 else 0
                },
                "performance": {
                    "avg_response_time_seconds": avg_response_time,
                    "total_response_time_seconds": sum(r.metrics.response_time_seconds for r in results)
                },
                "tools": {
                    "total_calls": total_tool_calls,
                    "successful": total_tool_successes,
                    "failed": total_tool_failures,
                    "success_rate": total_tool_successes / total_tool_calls if total_tool_calls > 0 else 0.0
                }
            },
            "tool_usage": tool_usage,
            "category_stats": category_stats,
            "errors": [r.error for r in results if r.error]
        }
    
    def compare_agents(self, agent_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compare multiple agent configurations.
        
        Args:
            agent_configs: List of dicts with 'name' and 'agent' keys
        
        Returns:
            Comparison analysis
        """
        comparison = {}
        
        for config in agent_configs:
            agent_name = config.get("name", "unknown")
            agent_results = [r for r in self.results if r.agent_name == agent_name]
            
            if agent_results:
                comparison[agent_name] = self.analyze_results(agent_results, agent_name)
        
        return comparison
    
    def evaluate_tool_usage(
        self,
        agent: Agent,
        tool_test_cases: List[TestCase],
        mock_tool_context: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Test tool selection accuracy.
        
        Args:
            agent: The agent to test
            tool_test_cases: Test cases with expected_tool specified
            mock_tool_context: Mock ToolContext for testing
        
        Returns:
            Tool usage accuracy metrics
        """
        results = asyncio.run(
            self.evaluate_agent(agent, agent.name, tool_test_cases, mock_tool_context)
        )
        
        correct_selections = sum(
            1 for r in results 
            if r.tool_used == next((tc.expected_tool for tc in tool_test_cases if tc.id == r.test_case_id), None)
        )
        
        total_tests = len(results)
        
        return {
            "total_tests": total_tests,
            "correct_selections": correct_selections,
            "accuracy": correct_selections / total_tests if total_tests > 0 else 0.0,
            "details": [
                {
                    "test_case_id": r.test_case_id,
                    "expected_tool": next((tc.expected_tool for tc in tool_test_cases if tc.id == r.test_case_id), None),
                    "actual_tool": r.tool_used,
                    "correct": r.tool_used == next((tc.expected_tool for tc in tool_test_cases if tc.id == r.test_case_id), None)
                }
                for r in results
            ]
        }
    
    def export_results(
        self,
        output_path: str,
        format: str = "json",
        results: Optional[List[EvaluationResult]] = None
    ) -> None:
        """
        Export results to CSV or JSON file.
        
        Args:
            output_path: Path to output file
            format: Export format ('json' or 'csv')
            results: Results to export. If None, exports all stored results.
        """
        if results is None:
            results = self.results
        
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(path, 'w') as f:
                json.dump([r.to_dict() for r in results], f, indent=2, default=str)
        elif format == "csv":
            if not results:
                return
            
            with open(path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "test_case_id", "agent_name", "query", "success", 
                    "response_content", "tool_used", "error", "timestamp",
                    "input_tokens", "output_tokens", "total_tokens",
                    "response_time_seconds", "tool_call_count", "tool_success_count", "tool_failure_count"
                ])
                writer.writeheader()
                for result in results:
                    row = {
                        "test_case_id": result.test_case_id,
                        "agent_name": result.agent_name,
                        "query": result.query,
                        "success": result.success,
                        "response_content": result.response_content[:500] if result.response_content else "",
                        "tool_used": result.tool_used or "",
                        "error": result.error or "",
                        "timestamp": result.timestamp.isoformat(),
                        "input_tokens": result.metrics.input_tokens,
                        "output_tokens": result.metrics.output_tokens,
                        "total_tokens": result.metrics.total_tokens,
                        "response_time_seconds": result.metrics.response_time_seconds,
                        "tool_call_count": result.metrics.tool_call_count,
                        "tool_success_count": result.metrics.tool_success_count,
                        "tool_failure_count": result.metrics.tool_failure_count
                    }
                    writer.writerow(row)
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'json' or 'csv'")
