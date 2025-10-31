from strands import Agent
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status

from ..models.base import InvestigationReport
from ..utils import get_logger
from ..utils.config import create_synthesis_model

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
        logger.info("🔧 StructuredReportNode: Processing investigation findings...")
        
        # Extract data from invocation state
        resources = invocation_state.get("resources", [])
        
        # The 'task' parameter contains the combined input from Graph execution
        # This includes the original task + results from all dependency nodes
        
        logger.info(f"🔍 Debug: Task type: {type(task)}")
        logger.info(f"🔍 Debug: Task content preview: {str(task)[:200]}...")
        
        # Create detailed prompt with explicit schema guidance
        findings_text = f"""
INVESTIGATION FINDINGS FROM GRAPH EXECUTION:

{task}

RESOURCES:
{resources}

Create an InvestigationReport based ONLY on these actual findings from the Graph execution. Do not invent or hallucinate any data.

IMPORTANT: Follow the exact schema structure:
- severity_assessment must include ALL fields: severity (str), impact_scope (str: "single_resource", "service", or "system_wide"), affected_resource_count (int), user_impact (str: "none", "minimal", "moderate", or "severe"), confidence (float 0.0-1.0), reasoning (str)
- root_cause_analysis must include ALL fields: primary_root_cause (Hypothesis or null), contributing_factors (List[Hypothesis], can be empty list), confidence_score (float 0.0-1.0), analysis_summary (str)
- All other fields must match the InvestigationReport schema exactly
"""
        
        # Create agent for structured output using synthesis model (from env config)
        synthesis_model = create_synthesis_model()
        agent = Agent(model=synthesis_model)
        
        # Generate structured report using Strands structured output
        logger.info("🤖 Generating structured InvestigationReport...")
        result = await agent.invoke_async(
            findings_text,
            structured_output_model=InvestigationReport
        )
        
        # Access structured output according to Strands API
        report = result.structured_output
        
        logger.info("✅ StructuredReportNode: Generated structured InvestigationReport")
        
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
