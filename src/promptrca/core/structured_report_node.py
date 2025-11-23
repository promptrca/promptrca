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
        
        # The task contains results from all previous nodes in the graph
        # Extract the structured outputs from previous nodes
        logger.info(f"🔍 Debug: Extracting structured data from graph execution...")

        # Create prompt - let structured output handle the schema automatically
        findings_text = f"""
INVESTIGATION FINDINGS FROM GRAPH EXECUTION:

{task}

RESOURCES:
{resources}

Create an InvestigationReport based on these findings from the Graph execution. Use the actual data provided above - do not invent or hallucinate any data.

The graph has already performed:
1. Input parsing - extracted resources and context
2. Investigation - specialist agents gathered facts
3. Hypothesis generation - generated possible root causes
4. Root cause analysis - identified primary root cause and contributing factors

Extract the findings and populate the InvestigationReport with the data from above.
"""
        
        # Create agent for structured output using synthesis model (from env config)
        synthesis_model = create_synthesis_model()
        agent = Agent(model=synthesis_model)
        
        # Generate structured report using Strands structured output with retry
        logger.info("🤖 Generating structured InvestigationReport...")
        from ..utils.agent_retry import invoke_agent_async_with_retry
        result = await invoke_agent_async_with_retry(
            agent,
            findings_text,
            structured_output_model=InvestigationReport
        )
        # Access structured output according to Strands API
        if hasattr(result, 'structured_output'):
            report = result.structured_output
        else:
            # Fallback: result might be the structured output directly
            report = result
        
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
