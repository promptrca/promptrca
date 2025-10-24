import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from strands import Agent
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.tracer import get_tracer

from ..models.base import InvestigationReport, Fact, Hypothesis, SeverityAssessment, AffectedResource, RootCauseAnalysis, EventTimeline, Advice
from ..utils import get_logger

logger = get_logger(__name__)

class StructuredReportNode(MultiAgentBase):
    """
    A simple custom Strands node that generates a structured InvestigationReport using
    Strands' structured output capabilities with Pydantic models.
    """
    def __init__(self, region: str, **kwargs):
        """
        Initialize the StructuredReportNode.
        
        Args:
            region: AWS region for the investigation
        """
        super().__init__()
        self.region = region
    
    async def invoke_async(self, task, invocation_state, **kwargs):
        """
        Generate structured InvestigationReport using Strands structured output.
        
        Args:
            task: Combined input from Graph (original task + results from dependency nodes)
            invocation_state: Shared state containing investigation results
            **kwargs: Additional arguments
            
        Returns:
            MultiAgentResult containing the InvestigationReport
        """
        try:
            logger.info("🔧 StructuredReportNode: Processing investigation findings...")
            
            # Extract data from invocation state
            resources = invocation_state.get("resources", [])
            investigation_id = invocation_state.get("investigation_id", "unknown")
            region = invocation_state.get("region", self.region)
            
            # Get investigation start time from state or use current time
            start_time = invocation_state.get("investigation_start_time", datetime.now(timezone.utc))
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # The 'task' parameter contains the combined input from Graph execution
            # This includes the original task + results from all dependency nodes
            # According to Strands docs: "Dependent nodes receive a combined input that includes:
            # - The original task
            # - Results from all dependency nodes that have completed execution"
            
            logger.info(f"🔍 Debug: Task type: {type(task)}")
            logger.info(f"🔍 Debug: Task content preview: {str(task)[:200]}...")
            
            # Create simple prompt with the actual Graph results
            findings_text = f"""
INVESTIGATION FINDINGS FROM GRAPH EXECUTION:

{task}

RESOURCES:
{resources}

Create an InvestigationReport based ONLY on these actual findings from the Graph execution. Do not invent or hallucinate any data.
"""
            
            # Create agent for structured output
            agent = Agent()
            
            # Generate structured report using Strands structured output
            logger.info("🤖 Generating structured InvestigationReport...")
            report = await agent.structured_output_async(
                InvestigationReport,
                findings_text
            )
            
            logger.info("✅ StructuredReportNode: Generated structured InvestigationReport")
            logger.info(f"🔍 Debug: report type: {type(report)}")
            logger.info(f"🔍 Debug: report has model_dump: {hasattr(report, 'model_dump')}")
            
            # Return wrapped in MultiAgentResult with the report directly
            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "report_generator": NodeResult(
                        result=report,
                        execution_time=0,
                        status=Status.COMPLETED
                    )
                },
                execution_time=0,
                accumulated_usage={"totalTokens": 0, "inputTokens": 0, "outputTokens": 0}
            )
            
        except Exception as e:
            logger.error(f"❌ StructuredReportNode failed: {e}")
            
            # Create fallback report
            fallback_report = self._create_fallback_report(
                investigation_id=invocation_state.get("investigation_id", "unknown"),
                start_time=invocation_state.get("investigation_start_time", datetime.now(timezone.utc)),
                region=invocation_state.get("region", self.region),
                resources=invocation_state.get("resources", []),
                error=str(e)
            )
            
            # Return fallback report
            return MultiAgentResult(
                status=Status.COMPLETED,
                results={
                    "report_generator": NodeResult(
                        result=fallback_report,
                        execution_time=0,
                        status=Status.COMPLETED
                    )
                },
                execution_time=0,
                accumulated_usage={"totalTokens": 0, "inputTokens": 0, "outputTokens": 0}
            )
    
    def _create_fallback_report(self, investigation_id: str, start_time: datetime, 
                              region: str, resources: List[Dict[str, Any]], 
                              error: str) -> InvestigationReport:
        """Create a fallback InvestigationReport for errors."""
        
        # Create basic affected resource if we have any
        affected_resources = []
        if resources:
            for resource in resources:
                affected_resources.append(AffectedResource(
                    resource_type=resource.get("type", "unknown"),
                    resource_id=resource.get("name", "unknown"),
                    resource_name=resource.get("name", "unknown"),
                    health_status="unknown",
                    detected_issues=[f"Investigation failed: {error}"],
                    metadata=resource
                ))
        
        return InvestigationReport(
            run_id=investigation_id,
            status="failed",
            started_at=start_time,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=(datetime.now(timezone.utc) - start_time).total_seconds(),
            affected_resources=affected_resources,
            severity_assessment=SeverityAssessment(
                severity="unknown",
                impact_scope="unknown",
                affected_resource_count=len(affected_resources),
                user_impact="unknown",
                confidence=0.0,
                reasoning=f"Investigation failed: {error}"
            ),
            facts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary=f"Investigation failed: {error}"
            ),
            hypotheses=[],
            advice=[Advice(title="Investigation Failed", description=f"Investigation failed due to: {error}")],
            timeline=[EventTimeline(timestamp=datetime.now(timezone.utc), event_type="error", component="StructuredReportNode", description=f"Investigation failed: {error}")],
            summary=f"Investigation failed due to an internal error: {error}"
        )
