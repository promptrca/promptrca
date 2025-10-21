#!/usr/bin/env python3
"""
Test flow control and cost management for SwarmOrchestrator.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.promptrca.core.swarm_orchestrator import (
    SwarmOrchestrator, InvestigationPhase, InvestigationProgress, 
    CostControlConfig, InvestigationTimeoutError
)


class TestSwarmFlowControl:
    """Test investigation flow control and cost management."""
    
    def test_investigation_progress_initialization(self):
        """Test investigation progress tracking initialization."""
        orchestrator = SwarmOrchestrator()
        progress = orchestrator._initialize_investigation_progress("test-123")
        
        assert progress.current_phase == InvestigationPhase.TRACE_ANALYSIS
        assert len(progress.phases_completed) == len(InvestigationPhase)
        assert all(not completed for completed in progress.phases_completed.values())
        assert len(progress.handoff_history) == 0
        assert len(progress.unique_agents_used) == 0
        assert progress.cost_estimate == 0.0
        assert not progress.early_termination_triggered
    
    def test_investigation_phase_transitions(self):
        """Test investigation phase tracking and transitions."""
        orchestrator = SwarmOrchestrator()
        progress = InvestigationProgress()
        
        # Test phase transition
        orchestrator._update_investigation_phase(
            progress, InvestigationPhase.SERVICE_ANALYSIS, "lambda_specialist"
        )
        
        assert progress.current_phase == InvestigationPhase.SERVICE_ANALYSIS
        assert progress.phases_completed[InvestigationPhase.TRACE_ANALYSIS] == True
        assert "lambda_specialist" in progress.unique_agents_used
        assert len(progress.handoff_history) == 1
        
        handoff = progress.handoff_history[0]
        assert handoff["from_phase"] == InvestigationPhase.TRACE_ANALYSIS.value
        assert handoff["to_phase"] == InvestigationPhase.SERVICE_ANALYSIS.value
        assert handoff["agent"] == "lambda_specialist"
    
    def test_cost_estimation(self):
        """Test investigation cost estimation."""
        orchestrator = SwarmOrchestrator()
        progress = InvestigationProgress()
        
        resources = [
            {"type": "lambda", "name": "test-function"},
            {"type": "apigateway", "name": "test-api"},
            {"type": "stepfunctions", "name": "test-state-machine"}
        ]
        
        cost = orchestrator._estimate_investigation_cost(resources, progress)
        
        # Should have base cost for 3 resources
        assert cost > 0
        assert progress.cost_estimate == cost
        
        # Test with more complex scenario
        progress.unique_agents_used.add("lambda_specialist")
        progress.unique_agents_used.add("apigateway_specialist")
        progress.current_phase = InvestigationPhase.HYPOTHESIS_GENERATION
        
        complex_cost = orchestrator._estimate_investigation_cost(resources, progress)
        assert complex_cost > cost  # Should be higher due to complexity
    
    def test_early_termination_conditions(self):
        """Test early termination condition checking."""
        config = CostControlConfig(
            max_cost_estimate=5.0,
            token_limit=1000,
            execution_timeout=60.0,
            max_handoffs=5
        )
        orchestrator = SwarmOrchestrator(cost_control_config=config)
        progress = InvestigationProgress()
        resources = []
        
        # Test cost limit
        progress.cost_estimate = 6.0
        reason = orchestrator._check_early_termination_conditions(progress, resources)
        assert reason is not None
        assert "cost estimate" in reason.lower()
        
        # Test token limit
        progress.cost_estimate = 2.0
        progress.token_usage["total"] = 1500
        reason = orchestrator._check_early_termination_conditions(progress, resources)
        assert reason is not None
        assert "token limit" in reason.lower()
        
        # Test repetitive handoff detection (checked first)
        progress.token_usage["total"] = 500
        progress.handoff_history = [
            {"agent": "agent_a"}, {"agent": "agent_b"}, 
            {"agent": "agent_a"}, {"agent": "agent_b"},
            {"agent": "agent_a"}, {"agent": "agent_b"},
            {"agent": "agent_a"}, {"agent": "agent_b"}
        ]
        reason = orchestrator._check_early_termination_conditions(progress, resources)
        assert reason is not None
        assert "repetitive handoff" in reason.lower()
        
        # Test handoff limit (with different agents to avoid repetitive detection)
        progress.handoff_history = [{"agent": f"agent_{i}"} for i in range(6)]
        reason = orchestrator._check_early_termination_conditions(progress, resources)
        assert reason is not None
        assert "handoff limit" in reason.lower()
    
    def test_cost_control_config(self):
        """Test cost control configuration."""
        config = CostControlConfig(
            max_handoffs=8,
            execution_timeout=300.0,
            max_cost_estimate=15.0
        )
        
        orchestrator = SwarmOrchestrator(cost_control_config=config)
        
        assert orchestrator.cost_control_config.max_handoffs == 8
        assert orchestrator.cost_control_config.execution_timeout == 300.0
        assert orchestrator.cost_control_config.max_cost_estimate == 15.0
    
    def test_token_usage_tracking(self):
        """Test token usage tracking from swarm results."""
        orchestrator = SwarmOrchestrator()
        progress = InvestigationProgress()
        
        # Mock swarm result with usage data
        mock_result = Mock()
        mock_result.accumulated_usage = {
            "inputTokens": 1000,
            "outputTokens": 500,
            "totalTokens": 1500
        }
        
        orchestrator._update_token_usage(progress, mock_result)
        
        assert progress.token_usage["input"] == 1000
        assert progress.token_usage["output"] == 500
        assert progress.token_usage["total"] == 1500
    
    def test_cost_limit_report_generation(self):
        """Test cost limit exceeded report generation."""
        config = CostControlConfig(max_cost_estimate=5.0)
        orchestrator = SwarmOrchestrator(cost_control_config=config)
        
        start_time = datetime.now(timezone.utc)
        resources = [{"type": "lambda", "name": "test-function"}]
        estimated_cost = 8.0
        
        report = orchestrator._generate_cost_limit_report(estimated_cost, start_time, resources)
        
        assert report.status == "cost_limited"
        assert len(report.facts) >= 2
        assert any("cost limit" in fact.content.lower() for fact in report.facts)
        assert len(report.affected_resources) == 1
        assert report.affected_resources[0].health_status == "not_analyzed"
        assert len(report.advice) >= 1
        assert any("cost" in advice.category.lower() for advice in report.advice)
    
    def test_report_enhancement_with_flow_control(self):
        """Test report enhancement with flow control data."""
        orchestrator = SwarmOrchestrator()
        progress = InvestigationProgress()
        progress.unique_agents_used.add("trace_specialist")
        progress.unique_agents_used.add("lambda_specialist")
        progress.handoff_history = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_phase": "trace_analysis",
                "to_phase": "service_analysis",
                "agent": "lambda_specialist"
            }
        ]
        progress.token_usage = {"input": 800, "output": 400, "total": 1200}
        progress.cost_estimate = 3.5
        
        # Create a basic report
        from src.promptrca.models import InvestigationReport, SeverityAssessment, RootCauseAnalysis
        
        basic_report = InvestigationReport(
            run_id="test-123",
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            duration_seconds=60.0,
            affected_resources=[],
            severity_assessment=SeverityAssessment(
                severity="medium", impact_scope="service", affected_resource_count=1,
                user_impact="minimal", confidence=0.8, reasoning="Test"
            ),
            facts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None, contributing_factors=[],
                confidence_score=0.8, analysis_summary="Test analysis"
            ),
            hypotheses=[],
            advice=[],
            timeline=[],
            summary="Basic test report"
        )
        
        enhanced_report = orchestrator._enhance_report_with_flow_control_data(basic_report, progress)
        
        # Check that flow control facts were added
        flow_control_facts = [f for f in enhanced_report.facts if f.source in ["flow_control", "cost_control", "agent_coordination"]]
        assert len(flow_control_facts) >= 3
        
        # Check that timeline events were added
        phase_transitions = [e for e in enhanced_report.timeline if e.event_type == "phase_transition"]
        assert len(phase_transitions) >= 1
        
        # Check that summary was enhanced
        import json
        summary_data = json.loads(enhanced_report.summary)
        assert "flow_control" in summary_data
        assert "cost_control" in summary_data
        assert summary_data["flow_control"]["unique_agents_used"] == 2
        assert summary_data["cost_control"]["estimated_cost"] == 3.5


if __name__ == "__main__":
    pytest.main([__file__])