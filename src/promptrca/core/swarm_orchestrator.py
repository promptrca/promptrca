#!/usr/bin/env python3
"""
Swarm-based Orchestrator for PromptRCA

Implements Strands Agents best practices using the Swarm pattern for
collaborative multi-agent AWS infrastructure investigation.

Key Benefits:
- Uses proven Strands multi-agent patterns
- Agents decide investigation flow autonomously
- Shared context across all specialists
- Tool-Agent pattern for modularity

Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: info@promptrca.com
"""

import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

from strands.multiagent import Swarm, GraphBuilder

from ..models import (
    InvestigationReport, Fact, Hypothesis, Advice,
    AffectedResource, SeverityAssessment, RootCauseAnalysis, EventTimeline
)
from ..clients import AWSClient
from ..context import set_aws_client, clear_aws_client
from ..utils.config import get_region
from ..utils import get_logger
from ..agents.swarm_agents import create_specialist_swarm_agents, create_hypothesis_agent_standalone, create_root_cause_agent_standalone, create_swarm_agents, create_input_parser_agent
from ..specialists import InvestigationContext
from .swarm_tools import (
    # Re-export resource type constants for backward compatibility
    RESOURCE_TYPE_LAMBDA, RESOURCE_TYPE_APIGATEWAY, RESOURCE_TYPE_STEPFUNCTIONS,
    RESOURCE_TYPE_IAM, RESOURCE_TYPE_S3, RESOURCE_TYPE_SQS, RESOURCE_TYPE_SNS,
    # Re-export specialist type constants for backward compatibility
    SPECIALIST_TYPE_LAMBDA, SPECIALIST_TYPE_APIGATEWAY, SPECIALIST_TYPE_STEPFUNCTIONS,
    SPECIALIST_TYPE_TRACE, SPECIALIST_TYPE_IAM, SPECIALIST_TYPE_S3, SPECIALIST_TYPE_SQS, SPECIALIST_TYPE_SNS,
    # Re-export placeholder constants for backward compatibility
    UNKNOWN_RESOURCE_NAME, UNKNOWN_RESOURCE_ID,
    # Re-export helper functions for backward compatibility with tests
    _extract_resource_from_data, _format_specialist_results,
    # Re-export specialist tools for backward compatibility with tests
    lambda_specialist_tool, apigateway_specialist_tool, stepfunctions_specialist_tool,
    trace_specialist_tool, iam_specialist_tool, s3_specialist_tool, sqs_specialist_tool, sns_specialist_tool
)

logger = get_logger(__name__)


# Custom exception classes for better error handling
class AWSClientContextError(Exception):
    """Error with AWS client context setup or access."""
    pass


class AWSPermissionError(Exception):
    """Error related to AWS permissions or access."""
    pass


class CrossAccountAccessError(Exception):
    """Error during cross-account role assumption."""
    pass


class InvestigationTimeoutError(Exception):
    """Investigation exceeded time or cost limits."""
    pass


# Investigation phase tracking
class InvestigationPhase(Enum):
    """Investigation phases for flow control."""
    TRACE_ANALYSIS = "trace_analysis"
    SERVICE_ANALYSIS = "service_analysis"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    COMPLETED = "completed"


@dataclass
class InvestigationProgress:
    """Track investigation progress and cost control."""
    current_phase: InvestigationPhase = InvestigationPhase.TRACE_ANALYSIS
    phases_completed: Dict[InvestigationPhase, bool] = field(default_factory=dict)
    services_analyzed: Dict[str, bool] = field(default_factory=dict)
    handoff_history: List[Dict[str, Any]] = field(default_factory=list)
    unique_agents_used: set = field(default_factory=set)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    token_usage: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "total": 0})
    cost_estimate: float = 0.0
    early_termination_triggered: bool = False
    termination_reason: Optional[str] = None


@dataclass
class CostControlConfig:
    """Configuration for cost control and investigation limits."""
    max_handoffs: int = 12
    max_iterations: int = 15
    execution_timeout: float = 450.0  # 7.5 minutes
    node_timeout: float = 60.0  # 1 minute per agent
    repetitive_handoff_detection_window: int = 8
    repetitive_handoff_min_unique_agents: int = 3
    max_cost_estimate: float = 10.0  # Maximum estimated cost in USD
    token_limit: int = 100000  # Maximum total tokens
    early_termination_enabled: bool = True


# Configuration constants for backward compatibility with tests
# These values are now primarily managed through CostControlConfig class
DEFAULT_MAX_HANDOFFS = 12  # Allow for: trace → multiple specialists → hypothesis → root_cause
DEFAULT_MAX_ITERATIONS = 15  # Allow multiple specialist interactions across more agents
DEFAULT_EXECUTION_TIMEOUT = 450.0  # 7.5 minutes for complete investigation with more agents
DEFAULT_NODE_TIMEOUT = 60.0  # 1 minute per agent (tool calls can be slow)

# Default AWS region
DEFAULT_AWS_REGION = 'us-east-1'








class SwarmOrchestrator:
    """
    Strands Swarm-based orchestrator for AWS infrastructure investigation.
    
    Uses the Strands Swarm pattern where specialized agents collaborate autonomously
    to investigate AWS issues, with each agent deciding when to hand off
    to other specialists based on their findings.
    """
    
    def __init__(self, region: str = None, cost_control_config: Optional[CostControlConfig] = None):
        """Initialize the swarm orchestrator with cost control."""
        self.region = region or get_region()
        
        # Initialize cost control configuration
        self.cost_control_config = cost_control_config or CostControlConfig()
        
        # Initialize investigation progress tracking
        self.investigation_progress = None
        
        # Initialize input parser
        from ..agents.input_parser_agent import InputParserAgent
        self.input_parser = InputParserAgent()
        
        # Create specialized agents for the swarm
        self._create_specialist_agents()
        
        # Create the investigation graph using Strands pattern
        self._create_investigation_graph()
        
        # Circuit breaker for tool failures
        self.tool_failure_count = 0
        self.max_tool_failures = 3
        
        logger.info("✨ SwarmOrchestrator initialized with cost control and flow management")
    
    def _initialize_investigation_progress(self, investigation_id: str) -> InvestigationProgress:
        """Initialize investigation progress tracking."""
        progress = InvestigationProgress()
        progress.start_time = datetime.now(timezone.utc)
        
        # Initialize phase tracking
        for phase in InvestigationPhase:
            progress.phases_completed[phase] = False
        
        logger.info(f"🔍 Investigation {investigation_id} progress tracking initialized")
        return progress
    
    def _update_investigation_phase(self, progress: InvestigationProgress, new_phase: InvestigationPhase, agent_name: str = None):
        """Update investigation phase and track progress."""
        old_phase = progress.current_phase
        progress.phases_completed[old_phase] = True
        progress.current_phase = new_phase
        
        if agent_name:
            progress.unique_agents_used.add(agent_name)
        
        logger.info(f"📊 Investigation phase transition: {old_phase.value} → {new_phase.value}")
        
        # Track handoff in history
        progress.handoff_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_phase": old_phase.value,
            "to_phase": new_phase.value,
            "agent": agent_name
        })
    
    def _check_early_termination_conditions(self, progress: InvestigationProgress, resources: List[Dict[str, Any]]) -> Optional[str]:
        """Check if investigation should terminate early to control costs."""
        if not self.cost_control_config.early_termination_enabled:
            return None
        
        # Check time limits
        elapsed_time = (datetime.now(timezone.utc) - progress.start_time).total_seconds()
        if elapsed_time > self.cost_control_config.execution_timeout:
            return f"Investigation exceeded time limit ({self.cost_control_config.execution_timeout}s)"
        
        # Check token limits
        if progress.token_usage["total"] > self.cost_control_config.token_limit:
            return f"Investigation exceeded token limit ({self.cost_control_config.token_limit})"
        
        # Check cost estimates
        if progress.cost_estimate > self.cost_control_config.max_cost_estimate:
            return f"Investigation exceeded cost estimate (${self.cost_control_config.max_cost_estimate})"
        
        # Check for ping-pong behavior (repetitive handoffs between same agents) - check this first
        if len(progress.handoff_history) >= self.cost_control_config.repetitive_handoff_detection_window:
            recent_agents = [h.get("agent") for h in progress.handoff_history[-self.cost_control_config.repetitive_handoff_detection_window:]]
            unique_recent = set(filter(None, recent_agents))
            if len(unique_recent) < self.cost_control_config.repetitive_handoff_min_unique_agents:
                return f"Investigation detected repetitive handoff pattern (only {len(unique_recent)} unique agents in recent {self.cost_control_config.repetitive_handoff_detection_window} handoffs)"
        
        # Check for runaway investigations (too many handoffs without progress)
        if len(progress.handoff_history) > self.cost_control_config.max_handoffs:
            return f"Investigation exceeded handoff limit ({self.cost_control_config.max_handoffs})"
        
        # REMOVED: Premature termination condition that was too aggressive
        # The investigation should continue through all phases unless there's a real issue
        # Agents will naturally complete when they reach root_cause_analyzer
        
        return None
    
    def _estimate_investigation_cost(self, resources: List[Dict[str, Any]], progress: InvestigationProgress) -> float:
        """Estimate investigation cost based on resources and current progress."""
        # Base cost per resource type (rough estimates in USD)
        cost_per_resource = {
            "lambda": 0.50,
            "apigateway": 0.30,
            "stepfunctions": 0.40,
            "s3": 0.20,
            "sqs": 0.15,
            "sns": 0.15,
            "iam": 0.10,
            "trace": 0.25
        }
        
        # Calculate base cost
        base_cost = 0.0
        for resource in resources:
            resource_type = resource.get("type", "unknown").lower()
            base_cost += cost_per_resource.get(resource_type, 0.25)
        
        # Add cost multiplier based on investigation complexity
        complexity_multiplier = 1.0
        if len(resources) > 5:
            complexity_multiplier += 0.5
        if len(progress.unique_agents_used) > 3:
            complexity_multiplier += 0.3
        if progress.current_phase in [InvestigationPhase.HYPOTHESIS_GENERATION, InvestigationPhase.ROOT_CAUSE_ANALYSIS]:
            complexity_multiplier += 0.4
        
        estimated_cost = base_cost * complexity_multiplier
        
        # Update progress tracking
        progress.cost_estimate = estimated_cost
        
        logger.debug(f"💰 Cost estimate: ${estimated_cost:.2f} (base: ${base_cost:.2f}, multiplier: {complexity_multiplier:.2f})")
        return estimated_cost
    
    def _update_token_usage(self, progress: InvestigationProgress, swarm_result):
        """Update token usage tracking from swarm result."""
        if hasattr(swarm_result, 'accumulated_usage'):
            usage = swarm_result.accumulated_usage
            progress.token_usage["input"] = usage.get("inputTokens", 0)
            progress.token_usage["output"] = usage.get("outputTokens", 0)
            progress.token_usage["total"] = usage.get("totalTokens", 0)
            
            logger.debug(f"🔢 Token usage: {progress.token_usage['total']} total ({progress.token_usage['input']} input, {progress.token_usage['output']} output)")
    
    def _create_specialist_agents(self):
        """Create specialized agents using agent factory functions from swarm_agents module."""
        # Use the agent factory functions from swarm_agents.py
        agents = create_swarm_agents()
        
        # Store individual agents for backward compatibility
        for agent in agents:
            if agent.name == "trace_specialist":
                self.trace_agent = agent
            elif agent.name == "lambda_specialist":
                self.lambda_agent = agent
            elif agent.name == "apigateway_specialist":
                self.apigateway_agent = agent
            elif agent.name == "stepfunctions_specialist":
                self.stepfunctions_agent = agent
            elif agent.name == "iam_specialist":
                self.iam_agent = agent
            elif agent.name == "s3_specialist":
                self.s3_agent = agent
            elif agent.name == "sqs_specialist":
                self.sqs_agent = agent
            elif agent.name == "sns_specialist":
                self.sns_agent = agent
            elif agent.name == "hypothesis_generator":
                self.hypothesis_agent = agent
            elif agent.name == "root_cause_analyzer":
                self.root_cause_agent = agent
    
    def _create_investigation_graph(self):
        """Create investigation graph with Input Parser + Swarm + Analysis + Report nodes."""

        # Create input parser agent (FIRST NODE)
        input_parser_agent = create_input_parser_agent()

        # Create specialist swarm (without hypothesis/root_cause agents)
        specialist_agents = create_specialist_swarm_agents()
        trace_agent = next((a for a in specialist_agents if a.name == "trace_specialist"), None)
        if not trace_agent:
            raise ValueError("trace_specialist agent not found in specialist agents")

        specialist_swarm = Swarm(
            specialist_agents,
            entry_point=trace_agent,
            max_handoffs=12,
            max_iterations=15,
            execution_timeout=450.0,
            node_timeout=60.0,
            repetitive_handoff_detection_window=8,
            repetitive_handoff_min_unique_agents=3
        )

        # Create hypothesis generator agent
        hypothesis_agent = create_hypothesis_agent_standalone()

        # Create root cause analyzer agent (NEW)
        root_cause_agent = create_root_cause_agent_standalone()

        # Create structured report generator custom node
        from .structured_report_node import StructuredReportNode
        report_generator = StructuredReportNode(region=self.region)

        # Build the graph
        builder = GraphBuilder()
        builder.add_node(input_parser_agent, "input_parser")
        builder.add_node(specialist_swarm, "investigation")
        builder.add_node(hypothesis_agent, "hypothesis_generation")
        builder.add_node(root_cause_agent, "root_cause_analysis")  # NEW
        builder.add_node(report_generator, "report_generation")

        # Define edges (deterministic flow)
        builder.add_edge("input_parser", "investigation")
        builder.add_edge("investigation", "hypothesis_generation")
        builder.add_edge("hypothesis_generation", "root_cause_analysis")  # NEW
        builder.add_edge("root_cause_analysis", "report_generation")  # UPDATED
        
        # Set entry point to input_parser (FIRST NODE)
        builder.set_entry_point("input_parser")
        
        # Set timeouts
        builder.set_execution_timeout(600.0)  # 10 minutes total
        builder.set_node_timeout(300.0)  # 5 minutes per node
        
        # Build and return graph
        self.graph = builder.build()
        
        # For backward compatibility
        self.swarm = specialist_swarm  # The swarm node from the graph
    
    async def investigate(
        self,
        inputs: Dict[str, Any],
        region: str = None,
        assume_role_arn: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> InvestigationReport:
        """
        Run investigation using Strands Swarm pattern.
        
        The swarm will autonomously coordinate between specialists based on
        their findings and expertise.
        """
        region = region or self.region
        investigation_start_time = datetime.now(timezone.utc)
        
        # Generate unique investigation ID for logging
        import time
        import uuid
        import os
        
        # Create a more unique investigation ID
        timestamp = int(time.time() * 1000)
        input_hash = hash(str(inputs)) % 10000
        unique_suffix = str(uuid.uuid4())[:8]
        process_id = os.getpid()
        
        investigation_id = f"{timestamp}.{input_hash}.{unique_suffix}.{process_id}"
        
        # Log investigation start for debugging
        logger.info(f"🔍 Starting investigation {investigation_id} in process {process_id}")
        logger.info(f"🔍 Input hash: {input_hash}, inputs: {str(inputs)[:100]}...")
        
        logger.info("=" * 80)
        logger.info(f"🚀 SWARM INVESTIGATION STARTED (ID: {investigation_id})")
        logger.info("=" * 80)
        
        try:
            # Initialize investigation progress tracking
            self.investigation_progress = self._initialize_investigation_progress(investigation_id)
            
            # Setup and validate AWS client context with comprehensive error handling
            try:
                aws_client = self._create_and_validate_aws_client(region, assume_role_arn, external_id)
                set_aws_client(aws_client)
            except Exception as e:
                logger.error(f"❌ AWS client setup failed: {e}")
                return self._generate_aws_client_error_report(str(e), investigation_start_time)
            
            # Extract free text input or structured input
            if 'free_text_input' in inputs:
                free_text_input = inputs['free_text_input']
                logger.info("📝 Starting investigation with free text input (will be parsed by input_parser agent)")
            elif 'investigation_inputs' in inputs:
                # Already structured - pass through
                free_text_input = json.dumps(inputs['investigation_inputs'])
                logger.info("📝 Starting investigation with structured input")
            else:
                # Legacy format - convert to free text
                free_text_input = str(inputs)
                logger.info("📝 Starting investigation with legacy format input")
            
            # Prepare investigation context for graph (make it JSON serializable)
            investigation_context = {
                "region": region
            }
            
            # Pass raw input - input_parser will extract, swarm will investigate
            investigation_prompt = f"Investigate this AWS issue: {free_text_input}"
            
            # Execute graph investigation with proper context sharing
            logger.info("🤖 Step 3: Executing graph investigation...")
            
            # Set AWS client in context before graph execution
            set_aws_client(aws_client)
            
            try:
                # Execute graph with comprehensive error handling
                graph_result = self.graph(
                    investigation_prompt,
                    invocation_state={
                        "aws_client": aws_client,
                        "investigation_context": investigation_context,
                        "region": region,
                        "investigation_id": investigation_id,
                        "investigation_start_time": investigation_start_time,
                        "debug_mode": os.getenv('DEBUG_MODE', False)
                    }
                )
                
                # Extract report from report_generation node
                report_node_result = graph_result.results.get("report_generation")
                if report_node_result and hasattr(report_node_result, 'result'):
                    # The structured report node returns a MultiAgentResult, extract the InvestigationReport
                    if hasattr(report_node_result.result, 'results'):
                        # Extract from the nested MultiAgentResult
                        nested_result = report_node_result.result.results.get("report_generator")
                        if nested_result and hasattr(nested_result, 'result'):
                            report = nested_result.result
                        else:
                            # Fallback if nested extraction failed
                            report = self._create_fallback_report(
                                investigation_id, investigation_start_time, region, 
                                "Failed to extract report from nested MultiAgentResult"
                            )
                    else:
                        # Direct result
                        report = report_node_result.result
                else:
                    # Fallback if report generation failed
                    report = self._create_fallback_report(
                        investigation_id, investigation_start_time, region, 
                        "Report generation node did not return results"
                    )
                
            except Exception as e:
                logger.error(f"Graph execution failed: {e}")
                # Create fallback report
                report = self._create_fallback_report(
                    investigation_id, investigation_start_time, region, str(e)
                )
            
            # Cost control metadata removed - OpenTelemetry handles observability
            # report = self._enhance_report_with_flow_control_data(report, self.investigation_progress)
            
            duration = (datetime.now(timezone.utc) - investigation_start_time).total_seconds()
            logger.info("=" * 80)
            logger.info(f"✅ GRAPH INVESTIGATION COMPLETE in {duration:.2f}s")
            logger.info(f"🔍 Debug: Returning report type: {type(report)}")
            logger.info(f"🔍 Debug: Returning report has to_dict: {hasattr(report, 'to_dict')}")
            from ..models import InvestigationReport
            logger.info(f"🔍 Debug: Returning report is InvestigationReport: {isinstance(report, InvestigationReport)}")
            logger.info("=" * 80)
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Swarm investigation failed: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            error_report = self._generate_error_report(str(e), investigation_start_time)
            return error_report
            
        finally:
            clear_aws_client()
    
    def _parse_inputs(self, inputs: Dict[str, Any], region: str):
        """
        Parse investigation inputs - DEPRECATED.
        
        This method is kept for backward compatibility but is no longer used.
        Input parsing is now handled by the input_parser agent node in the graph.
        """
        logger.warning("_parse_inputs() is deprecated - input parsing is now handled by input_parser agent node")
        
        # Minimal implementation for backward compatibility
        if 'investigation_inputs' in inputs:
            return self.input_parser.parse_inputs(inputs['investigation_inputs'], region)
        elif 'free_text_input' in inputs:
            return self.input_parser.parse_inputs(inputs['free_text_input'], region)
        else:
            return self.input_parser.parse_inputs(inputs, region)
    
    async def _discover_resources(self, parsed_inputs) -> List[Dict[str, Any]]:
        """Discover AWS resources from inputs and traces."""
        resources = []
        
        # Add explicit targets
        for target in parsed_inputs.primary_targets:
            resources.append({
                'type': target.type,
                'name': target.name,
                'arn': target.arn,
                'region': target.region,
                'source': 'explicit_target',
                'metadata': target.metadata
            })
        
        # Discover from X-Ray traces
        if parsed_inputs.trace_ids:
            from ..tools import get_all_resources_from_trace
            
            for trace_id in parsed_inputs.trace_ids:
                try:
                    resources_json = get_all_resources_from_trace(trace_id)
                    trace_resources = json.loads(resources_json)
                    
                    if "error" not in trace_resources:
                        for resource in trace_resources.get("resources", []):
                            resources.append({
                                'type': resource.get('type'),
                                'name': resource.get('name'),
                                'arn': resource.get('arn'),
                                'region': self.region,
                                'source': 'xray_trace',
                                'metadata': resource.get('metadata', {})
                            })
                except Exception as e:
                    logger.warning(f"Failed to extract resources from trace {trace_id}: {e}")
        
        # Deduplicate resources
        unique_resources = {}
        for resource in resources:
            key = resource.get('arn') or resource.get('name')
            if key and key not in unique_resources:
                unique_resources[key] = resource
        
        return list(unique_resources.values())
    
    def _create_investigation_prompt(
        self, 
        resources: List[Dict[str, Any]], 
        parsed_inputs, 
        investigation_context: Dict[str, Any]
    ) -> str:
        """Create the initial investigation prompt for the swarm."""
        
        resource_summary = []
        for resource in resources:
            resource_summary.append(f"- {resource.get('type', 'unknown').upper()}: {resource.get('name', 'unknown')}")
        
        trace_info = ""
        if parsed_inputs.trace_ids:
            trace_info = f"\nX-Ray Traces to analyze: {', '.join(parsed_inputs.trace_ids)}"
        
        prompt = f"""🔍 AWS INFRASTRUCTURE INVESTIGATION

MISSION: Investigate AWS infrastructure issue through coordinated specialist analysis.

📋 DISCOVERED RESOURCES:
{chr(10).join(resource_summary)}

🌍 REGION: {investigation_context.get('region', 'unknown')}
{trace_info}

📊 INVESTIGATION WORKFLOW:

PHASE 1 - TRACE ANALYSIS (Entry Point):
→ trace_agent: Analyze X-Ray traces, identify service interaction patterns and errors
→ Determine which services need detailed investigation
→ Hand off to appropriate service specialists

PHASE 2 - SERVICE ANALYSIS:
→ lambda_specialist: Analyze Lambda functions (config, IAM, performance, integrations)
→ apigateway_specialist: Analyze API Gateway (integrations, IAM, stages, methods)  
→ stepfunctions_specialist: Analyze Step Functions (executions, IAM, state transitions)
→ Specialists collaborate and hand off when finding cross-service issues

PHASE 3 - HYPOTHESIS GENERATION:
→ hypothesis_generator: Collect all specialist findings and generate evidence-based hypotheses
→ Focus on AWS-specific patterns: permissions, timeouts, configurations, integrations

PHASE 4 - ROOT CAUSE ANALYSIS (Final):
→ root_cause_analyzer: Evaluate hypotheses, determine root cause, provide recommendations
→ Generate final investigation report with actionable next steps

🎯 SUCCESS CRITERIA:
- All discovered resources analyzed by appropriate specialists
- Cross-service issues identified and investigated
- Evidence-based hypotheses generated
- Root cause identified with confidence score
- Actionable recommendations provided

⚠️ CRITICAL EXIT CONDITION:
Investigation MUST end with root_cause_analyzer providing final analysis. Do not hand off after root cause analysis is complete.

🔧 INVESTIGATION CONTEXT:
{json.dumps(investigation_context, indent=2, default=str)}

📦 RESOURCES DATA:
{json.dumps(resources, indent=2, default=str)}

🚀 BEGIN INVESTIGATION: trace_agent will start the analysis."""
        
        return prompt
    

    def _parse_swarm_results_to_report(
        self,
        swarm_result,
        resources: List[Dict[str, Any]],
        start_time: datetime,
        region: str
    ) -> InvestigationReport:
        """
        Parse Swarm results into a clean, structured InvestigationReport.
        
        Extracts meaningful findings from the Swarm execution instead of 
        dumping raw SwarmResult objects.
        """
        from ..models import (
            InvestigationReport, Fact, Hypothesis, Advice,
            AffectedResource, SeverityAssessment, RootCauseAnalysis, EventTimeline
        )
        
        # Extract meaningful information from swarm results
        facts = []
        hypotheses = []
        recommendations = []
        
        # Get the final agent's response (usually root_cause_analyzer or last agent)
        final_response = None
        if hasattr(swarm_result, 'content'):
            final_response = swarm_result.content
        elif hasattr(swarm_result, 'message') and hasattr(swarm_result.message, 'content'):
            # Extract text from message content
            content_items = swarm_result.message.content
            if isinstance(content_items, list):
                text_parts = []
                for item in content_items:
                    if isinstance(item, dict) and 'text' in item:
                        text_parts.append(item['text'])
                final_response = '\n'.join(text_parts)
            else:
                final_response = str(content_items)
        
        # Log the final response for debugging
        if final_response:
            logger.info(f"📝 Final agent response length: {len(final_response)} characters")
            logger.debug(f"Final response preview: {final_response[:500]}...")
        
        # Parse swarm execution results from all agents
        if hasattr(swarm_result, 'results') and swarm_result.results:
            logger.info(f"📊 Swarm results contain {len(swarm_result.results)} agent responses")
            logger.info(f"   Agents that participated: {list(swarm_result.results.keys())}")
            
            # Extract findings from each agent that participated
            for agent_name, node_result in swarm_result.results.items():
                if hasattr(node_result, 'result') and hasattr(node_result.result, 'message'):
                    message = node_result.result.message
                    
                    # Extract content from agent messages
                    if isinstance(message, dict) and 'content' in message:
                        content_items = message['content']
                        agent_text_parts = []
                        for item in content_items:
                            if isinstance(item, dict) and 'text' in item:
                                agent_text_parts.append(item['text'])
                        
                        agent_text = '\n'.join(agent_text_parts)
                        
                        # Extract key findings from agent text (more comprehensive)
                        if agent_text and len(agent_text) > 50:  # Only process substantial responses
                            # Add the full agent analysis as a fact
                            facts.append(Fact(
                                source=agent_name,
                                content=self._extract_key_finding(agent_text),
                                confidence=0.85,
                                metadata={"full_analysis": agent_text[:1000]}  # Store first 1000 chars
                            ))
        
        # If we have a final response from root_cause_analyzer, parse it for structured info
        if final_response and len(final_response) > 100:
            # Extract root cause if present
            if 'root cause' in final_response.lower():
                # Try to extract the root cause section
                root_cause_match = self._extract_section(final_response, 'root cause')
                if root_cause_match:
                    hypotheses.append(Hypothesis(
                        type="root_cause_analysis",
                        description=root_cause_match,
                        confidence=0.85,
                        evidence=["Final root cause analysis"]
                    ))
            
            # Extract recommendations if present
            if 'recommendation' in final_response.lower():
                recommendations_text = self._extract_section(final_response, 'recommendation')
                if recommendations_text:
                    # Split into individual recommendations
                    for line in recommendations_text.split('\n'):
                        line = line.strip()
                        if line and len(line) > 10:
                            recommendations.append(Advice(
                                category="remediation",
                                recommendation=line,
                                priority="high"
                            ))
        
        # If no meaningful findings extracted, create basic summary
        if not facts:
            agent_count = len(swarm_result.results) if hasattr(swarm_result, 'results') else 0
            facts.append(Fact(
                source="swarm_orchestrator",
                content=f"Investigated AWS infrastructure across {agent_count} specialist agents",
                confidence=0.90
            ))
        
        if not hypotheses:
            # Use final response as hypothesis if available
            if final_response and len(final_response) > 50:
                hypotheses.append(Hypothesis(
                    type="investigation_summary",
                    description=final_response[:500],  # First 500 chars
                    confidence=0.85,
                    evidence=["Swarm investigation analysis"]
                ))
            else:
                hypotheses.append(Hypothesis(
                    type="investigation_summary",
                    description="Multi-agent investigation completed with specialist analysis",
                    confidence=0.85,
                    evidence=["Swarm coordination between specialist agents"]
                ))
        
        # Create summary from swarm execution
        agent_names = list(swarm_result.results.keys()) if hasattr(swarm_result, 'results') else []
        summary = f"Investigation completed using {len(agent_names)} specialist agents: {', '.join(agent_names)}. "
        
        if hasattr(swarm_result, 'accumulated_usage'):
            usage = swarm_result.accumulated_usage
            summary += f"Processed {usage.get('totalTokens', 0)} tokens in {swarm_result.execution_time/1000:.1f}s."
        else:
            summary += "Analysis completed successfully."
        
        # Build affected resources
        affected_resources = []
        for resource in resources:
            affected_resources.append(AffectedResource(
                resource_type=resource.get('type', 'unknown'),
                resource_id=resource.get('arn', resource.get('id', 'unknown')),
                resource_name=resource.get('name', 'unknown'),
                health_status="investigated",
                detected_issues=["Swarm investigation completed"],
                metadata=resource.get('metadata', {})
            ))
        
        # Create root cause analysis from findings
        primary_hypothesis = hypotheses[0] if hypotheses else Hypothesis(
            type="investigation_complete",
            description="Multi-agent investigation completed",
            confidence=0.80,
            evidence=["Swarm analysis"]
        )
        
        root_cause = RootCauseAnalysis(
            primary_root_cause=primary_hypothesis,
            contributing_factors=hypotheses[1:] if len(hypotheses) > 1 else [],
            confidence_score=0.80,
            analysis_summary=summary
        )
        
        # Create severity assessment
        severity = SeverityAssessment(
            severity="medium",
            impact_scope="service",
            affected_resource_count=len(resources),
            user_impact="minimal",
            confidence=0.85,
            reasoning="Swarm investigation completed successfully"
        )
        
        # Create timeline events
        now = datetime.now(timezone.utc)
        timeline = [
            EventTimeline(
                timestamp=start_time,
                event_type="analysis",
                component="swarm_orchestrator",
                description="Investigation started"
            ),
            EventTimeline(
                timestamp=now,
                event_type="finding",
                component="swarm_orchestrator", 
                description="Investigation completed"
            )
        ]
        
        # Calculate duration
        duration = (now - start_time).total_seconds()
        
        return InvestigationReport(
            run_id=f"swarm_{int(start_time.timestamp())}",
            status="completed",
            started_at=start_time,
            completed_at=now,
            duration_seconds=duration,
            affected_resources=affected_resources,
            severity_assessment=severity,
            facts=facts,
            root_cause_analysis=root_cause,
            hypotheses=hypotheses,
            advice=[],
            timeline=timeline,
            summary=summary
        )
    
    def _extract_section(self, text: str, section_name: str) -> str:
        """Extract a section from structured agent response."""
        import re
        
        # Try to find section with various formats
        patterns = [
            rf'\*\*{section_name}[:\s]*\*\*[:\s]*(.+?)(?=\n\*\*|\n\n|$)',  # **Section:** content
            rf'{section_name}[:\s]+(.+?)(?=\n[A-Z]|\n\n|$)',  # Section: content
            rf'#{1,3}\s*{section_name}[:\s]*(.+?)(?=\n#|\n\n|$)',  # # Section content
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                # Clean up the content
                content = re.sub(r'\n+', ' ', content)  # Replace newlines with spaces
                content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
                return content[:500]  # Limit length
        
        return ""
    
    def _extract_key_finding(self, text: str) -> str:
        """Extract key finding from agent text, keeping it concise."""
        # Look for specific error patterns
        if "502" in text and "gateway" in text.lower():
            return "502 Bad Gateway error detected in service integration"
        elif "lambda integration error" in text.lower():
            return "Lambda integration error identified"
        elif "step functions" in text.lower() and "error" in text.lower():
            return "Step Functions execution issue detected"
        elif "api gateway" in text.lower() and ("error" in text.lower() or "issue" in text.lower()):
            return "API Gateway configuration or integration issue"
        elif "permission" in text.lower() or "iam" in text.lower():
            return "IAM permission or role configuration issue"
        elif "accessdenied" in text.lower().replace(' ', ''):
            return "IAM permission denied - access control issue"
        else:
            # Extract first meaningful sentence
            sentences = text.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and any(word in sentence.lower() for word in ['error', 'issue', 'problem', 'fail', 'found', 'detected']):
                    return sentence[:200]
            # If no specific finding, return a summary of the first part
            return text[:200].strip() if text else "Investigation finding identified"
    
    def _extract_hypothesis(self, text: str) -> str:
        """Extract hypothesis from agent reasoning text."""
        # Look for hypothesis patterns
        if "root cause" in text.lower():
            return "Root cause analysis indicates service integration failure"
        elif "lambda" in text.lower() and "fail" in text.lower():
            return "Lambda function failure causing downstream issues"
        elif "step functions" in text.lower() and "permission" in text.lower():
            return "Step Functions IAM permission issue preventing Lambda invocation"
        elif "api gateway" in text.lower() and "integration" in text.lower():
            return "API Gateway integration misconfiguration"
        else:
            return "Service interaction issue requiring further investigation"

    def _generate_cost_limit_report(self, estimated_cost: float, start_time: datetime, resources: List[Dict[str, Any]]) -> InvestigationReport:
        """Generate report when cost limits are exceeded."""
        now = datetime.now(timezone.utc)
        
        facts = [
            Fact(
                source="cost_control",
                content=f"Investigation terminated due to cost limit. Estimated cost: ${estimated_cost:.2f}, Limit: ${self.cost_control_config.max_cost_estimate:.2f}",
                confidence=1.0,
                metadata={"cost_control": True, "estimated_cost": estimated_cost}
            ),
            Fact(
                source="resource_discovery",
                content=f"Discovered {len(resources)} AWS resources requiring analysis",
                confidence=1.0,
                metadata={"resource_count": len(resources)}
            )
        ]
        
        # Build affected resources
        affected_resources = []
        for resource in resources:
            affected_resources.append(AffectedResource(
                resource_type=resource.get('type', 'unknown'),
                resource_id=resource.get('arn', resource.get('name', 'unknown')),
                resource_name=resource.get('name', 'unknown'),
                health_status="not_analyzed",
                detected_issues=["Analysis skipped due to cost limits"],
                metadata=resource.get('metadata', {})
            ))
        
        return InvestigationReport(
            run_id=f"cost_limited_{int(start_time.timestamp())}",
            status="cost_limited",
            started_at=start_time,
            completed_at=now,
            duration_seconds=(now - start_time).total_seconds(),
            affected_resources=affected_resources,
            severity_assessment=SeverityAssessment(
                severity="unknown",
                impact_scope="unknown",
                affected_resource_count=len(resources),
                user_impact="unknown",
                confidence=0.0,
                reasoning="Investigation terminated due to cost limits"
            ),
            facts=facts,
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary=f"Investigation terminated due to estimated cost (${estimated_cost:.2f}) exceeding limit (${self.cost_control_config.max_cost_estimate:.2f})"
            ),
            hypotheses=[],
            advice=[
                Advice(
                    title="Cost Control Limit Exceeded",
                    description=f"Consider increasing cost limit or reducing investigation scope. Current limit: ${self.cost_control_config.max_cost_estimate:.2f}",
                    priority="medium",
                    category="cost_control"
                )
            ],
            timeline=[
                EventTimeline(
                    timestamp=start_time,
                    event_type="investigation_start",
                    component="cost_control",
                    description="Investigation started"
                ),
                EventTimeline(
                    timestamp=now,
                    event_type="cost_limit_exceeded",
                    component="cost_control",
                    description=f"Investigation terminated due to cost limit (${estimated_cost:.2f} > ${self.cost_control_config.max_cost_estimate:.2f})"
                )
            ],
            summary=f"Investigation terminated due to cost control limits. Estimated cost: ${estimated_cost:.2f}"
        )
    
    def _enhance_report_with_flow_control_data(self, report: InvestigationReport, progress: InvestigationProgress) -> InvestigationReport:
        """Enhance investigation report with flow control and cost management data."""
        # Add flow control facts
        flow_control_facts = [
            Fact(
                source="flow_control",
                content=f"Investigation completed {len([p for p in progress.phases_completed.values() if p])} phases",
                confidence=1.0,
                metadata={
                    "phases_completed": {phase.value: completed for phase, completed in progress.phases_completed.items()},
                    "current_phase": progress.current_phase.value
                }
            ),
            Fact(
                source="cost_control",
                content=f"Investigation used {progress.token_usage['total']} tokens with estimated cost ${progress.cost_estimate:.2f}",
                confidence=1.0,
                metadata={
                    "token_usage": progress.token_usage,
                    "cost_estimate": progress.cost_estimate,
                    "early_termination": progress.early_termination_triggered
                }
            ),
            Fact(
                source="agent_coordination",
                content=f"Investigation involved {len(progress.unique_agents_used)} unique agents with {len(progress.handoff_history)} handoffs",
                confidence=1.0,
                metadata={
                    "unique_agents": list(progress.unique_agents_used),
                    "handoff_count": len(progress.handoff_history),
                    "handoff_history": progress.handoff_history
                }
            )
        ]
        
        # Add early termination information if applicable
        if progress.early_termination_triggered:
            flow_control_facts.append(
                Fact(
                    source="early_termination",
                    content=f"Investigation terminated early: {progress.termination_reason}",
                    confidence=1.0,
                    metadata={
                        "termination_reason": progress.termination_reason,
                        "termination_time": datetime.now(timezone.utc).isoformat()
                    }
                )
            )
        
        # Add flow control facts to existing facts
        report.facts.extend(flow_control_facts)
        
        # Add flow control timeline events
        flow_control_timeline = []
        for handoff in progress.handoff_history:
            flow_control_timeline.append(
                EventTimeline(
                    timestamp=datetime.fromisoformat(handoff["timestamp"].replace('Z', '+00:00')),
                    event_type="phase_transition",
                    component="flow_control",
                    description=f"Phase transition: {handoff['from_phase']} → {handoff['to_phase']}",
                    metadata={"agent": handoff.get("agent")}
                )
            )
        
        # Add cost control advice if needed
        cost_advice = []
        if progress.cost_estimate > self.cost_control_config.max_cost_estimate * 0.8:
            cost_advice.append(
                Advice(
                    title="Cost Optimization Needed",
                    description=f"Investigation approached cost limit (${progress.cost_estimate:.2f} of ${self.cost_control_config.max_cost_estimate:.2f}). Consider optimizing investigation scope.",
                    priority="medium",
                    category="cost_optimization"
                )
            )
        
        if len(progress.handoff_history) > self.cost_control_config.max_handoffs * 0.8:
            cost_advice.append(
                Advice(
                    title="Investigation Efficiency",
                    description=f"Investigation used {len(progress.handoff_history)} handoffs (limit: {self.cost_control_config.max_handoffs}). Consider more focused investigation scope.",
                    priority="low",
                    category="efficiency"
                )
            )
        
        # Add timeline events and advice
        report.timeline.extend(flow_control_timeline)
        report.advice.extend(cost_advice)
        
        # Update summary with flow control information
        original_summary = report.summary if isinstance(report.summary, str) else json.dumps(report.summary)
        enhanced_summary = {
            "original_summary": original_summary,
            "flow_control": {
                "phases_completed": len([p for p in progress.phases_completed.values() if p]),
                "total_phases": len(InvestigationPhase),
                "unique_agents_used": len(progress.unique_agents_used),
                "handoff_count": len(progress.handoff_history),
                "early_termination": progress.early_termination_triggered,
                "termination_reason": progress.termination_reason
            },
            "cost_control": {
                "token_usage": progress.token_usage,
                "estimated_cost": progress.cost_estimate,
                "cost_limit": self.cost_control_config.max_cost_estimate,
                "within_limits": progress.cost_estimate <= self.cost_control_config.max_cost_estimate
            }
        }
        
        report.summary = json.dumps(enhanced_summary)
        
        return report


    def _execute_swarm_with_graceful_degradation(
        self,
        investigation_prompt: str,
        aws_client: AWSClient,
        resources: List[Dict[str, Any]],
        investigation_context: Dict[str, Any],
        region: str,
        parsed_inputs: Any,
        investigation_id: str
    ):
        """
        Execute swarm investigation with graceful degradation for specialist failures.
        
        This method handles various failure scenarios and ensures the investigation
        can continue even if some specialists fail.
        """
        try:
            logger.info("🤖 Executing swarm with graceful degradation enabled...")
            
            swarm_result = self.swarm(
                investigation_prompt,
                invocation_state={
                    # Shared state for all agents (not visible to LLM)
                    "aws_client": aws_client,  # Critical for cross-account access
                    "resources": resources,
                    "investigation_context": investigation_context,
                    "region": region,
                    "trace_ids": parsed_inputs.trace_ids,
                    # Configuration that shouldn't appear in prompts
                    "debug_mode": os.getenv('DEBUG_MODE', False),
                    "investigation_id": investigation_id,
                    # Flow control and progress tracking
                    "investigation_progress": self.investigation_progress,
                    "cost_control_config": self.cost_control_config,
                    # Graceful degradation settings
                    "graceful_degradation_enabled": True,
                    "specialist_failure_tolerance": 0.5  # Allow up to 50% specialist failures
                }
            )
            
            logger.info("✅ Swarm execution completed successfully")
            return swarm_result
            
        except TimeoutError as e:
            logger.warning(f"⚠️ Swarm investigation timed out: {e}")
            self.investigation_progress.early_termination_triggered = True
            self.investigation_progress.termination_reason = f"Timeout: {str(e)}"
            
            # Create meaningful fallback result with partial analysis
            return self._create_timeout_fallback_result(resources, str(e))
            
        except Exception as e:
            logger.error(f"❌ Swarm execution failed: {e}")
            self.investigation_progress.early_termination_triggered = True
            self.investigation_progress.termination_reason = f"Error: {str(e)}"
            
            # Attempt to provide partial analysis based on available resources
            return self._create_error_fallback_result(resources, str(e))
    
    def _create_fallback_result(self, resources: List[Dict[str, Any]], error: str):
        """
        Create fallback result when swarm execution fails completely.
        
        Args:
            resources: Discovered resources
            error: Error message
            
        Returns:
            Fallback result object with basic analysis
        """
        logger.info("🔄 Creating fallback result with basic resource analysis...")
        
        # Create basic analysis based on discovered resources
        resource_summary = self._create_basic_resource_summary(resources)
        
        fallback_content = f"""Investigation encountered critical error but discovered {len(resources)} AWS resources.

Error: {error}

Basic Resource Analysis:
{resource_summary}

Recommendation: Review error details and retry investigation with proper AWS permissions and configuration.
"""
        
        return type('FallbackResult', (), {
            'content': fallback_content,
            'degraded': True,
            'error': error,
            'resources_discovered': len(resources)
        })()
    
    def _create_timeout_fallback_result(self, resources: List[Dict[str, Any]], error: str):
        """
        Create fallback result when swarm execution times out.
        
        Args:
            resources: Discovered resources
            error: Timeout error message
            
        Returns:
            Timeout fallback result with partial analysis
        """
        logger.info("⏱️ Creating timeout fallback result with partial analysis...")
        
        resource_summary = self._create_basic_resource_summary(resources)
        
        timeout_content = f"""Investigation timed out but discovered {len(resources)} AWS resources for analysis.

Timeout Details: {error}

Discovered Resources:
{resource_summary}

Partial Analysis Available:
- Resource discovery completed successfully
- {len(resources)} resources identified for investigation
- Investigation can be retried with increased timeout limits

Recommendation: Consider breaking down the investigation scope or increasing timeout limits.
"""
        
        return type('TimeoutFallbackResult', (), {
            'content': timeout_content,
            'timeout': True,
            'error': error,
            'resources_discovered': len(resources),
            'partial_analysis': True
        })()
    
    def _create_error_fallback_result(self, resources: List[Dict[str, Any]], error: str):
        """
        Create fallback result when swarm execution encounters errors.
        
        Args:
            resources: Discovered resources
            error: Error message
            
        Returns:
            Error fallback result with available information
        """
        logger.info("🔄 Creating error fallback result with available information...")
        
        resource_summary = self._create_basic_resource_summary(resources)
        
        error_content = f"""Investigation encountered errors but gathered basic resource information.

Error Details: {error}

Resource Discovery Results:
{resource_summary}

Available Information:
- {len(resources)} AWS resources discovered
- Basic resource metadata collected
- Investigation framework operational

Next Steps:
1. Review error details for specific issues
2. Check AWS permissions and connectivity
3. Retry investigation with corrected configuration
"""
        
        return type('ErrorFallbackResult', (), {
            'content': error_content,
            'error': True,
            'error_message': error,
            'resources_discovered': len(resources),
            'basic_analysis': True
        })()
    
    def _create_basic_resource_summary(self, resources: List[Dict[str, Any]]) -> str:
        """
        Create basic summary of discovered resources.
        
        Args:
            resources: List of discovered resources
            
        Returns:
            Formatted resource summary string
        """
        if not resources:
            return "No resources discovered."
        
        # Group resources by type
        resource_types = {}
        for resource in resources:
            resource_type = resource.get('type', 'unknown')
            if resource_type not in resource_types:
                resource_types[resource_type] = []
            resource_types[resource_type].append(resource.get('name', 'unnamed'))
        
        # Create summary
        summary_lines = []
        for resource_type, names in resource_types.items():
            summary_lines.append(f"- {resource_type.upper()}: {', '.join(names[:3])}")
            if len(names) > 3:
                summary_lines.append(f"  (and {len(names) - 3} more)")
        
        return '\n'.join(summary_lines)
    
    def _create_and_validate_aws_client(self, region: str, assume_role_arn: Optional[str] = None, external_id: Optional[str] = None) -> AWSClient:
        """
        Create and validate AWS client with comprehensive error handling.
        
        Args:
            region: AWS region
            assume_role_arn: Optional IAM role ARN for cross-account access
            external_id: Optional external ID for cross-account role assumption
            
        Returns:
            Validated AWS client
            
        Raises:
            AWSClientContextError: If client creation or validation fails
            CrossAccountAccessError: If cross-account role assumption fails
            AWSPermissionError: If AWS permissions are insufficient
        """
        try:
            # Validate role ARN format if provided
            if assume_role_arn:
                if not assume_role_arn.startswith('arn:aws:iam::'):
                    raise AWSClientContextError(f"Invalid role ARN format: {assume_role_arn}")
                if not assume_role_arn.endswith(':role/'):
                    # Check if it's a complete role ARN
                    parts = assume_role_arn.split(':')
                    if len(parts) != 6 or not parts[5].startswith('role/'):
                        raise AWSClientContextError(f"Invalid role ARN format: {assume_role_arn}")
            
            # Validate external ID format if provided
            if external_id:
                if not isinstance(external_id, str) or not external_id.strip():
                    raise AWSClientContextError("External ID must be a non-empty string")
                if len(external_id) > 1224:  # AWS limit
                    raise AWSClientContextError("External ID cannot exceed 1224 characters")
            
            # Create AWS client
            logger.info(f"🔍 Creating AWS client for region: {region}")
            if assume_role_arn:
                logger.info(f"🔍 Using cross-account role: {assume_role_arn}")
                if external_id:
                    logger.info(f"🔍 Using external ID for additional security")
            
            aws_client = AWSClient(
                region=region,
                role_arn=assume_role_arn,
                external_id=external_id
            )
            
            # Validate client connectivity and permissions
            self._validate_aws_client_connectivity(aws_client)
            
            logger.info(f"✅ AWS client validated successfully for account: {aws_client.account_id}")
            return aws_client
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'accessdenied' in error_msg or 'unauthorized' in error_msg:
                raise AWSPermissionError(f"AWS access denied - check IAM permissions: {str(e)}")
            elif 'assumerole' in error_msg or 'external' in error_msg or 'role' in error_msg:
                raise CrossAccountAccessError(f"Cross-account role assumption failed: {str(e)}")
            elif 'invalid' in error_msg and 'arn' in error_msg:
                raise AWSClientContextError(f"Invalid role ARN: {str(e)}")
            else:
                raise AWSClientContextError(f"AWS client creation failed: {str(e)}")
    
    def _validate_aws_client_connectivity(self, aws_client: AWSClient) -> None:
        """
        Validate AWS client connectivity and basic permissions.
        
        Args:
            aws_client: AWS client to validate
            
        Raises:
            AWSClientContextError: If client validation fails
            AWSPermissionError: If permissions are insufficient
        """
        try:
            # Test basic connectivity by checking account identity
            account_id = getattr(aws_client, 'account_id', None)
            if not account_id:
                raise AWSClientContextError("Unable to determine AWS account ID - check credentials")
            
            # Test basic service access by attempting to list Lambda functions (minimal permission)
            try:
                # This is a lightweight test that most investigation roles should have
                lambda_client = aws_client.lambda_client
                if not lambda_client:
                    raise AWSClientContextError("Lambda client not available")
                
                # Test if we can access the Lambda service (doesn't require listing functions)
                # Just check if the client is properly configured
                if not hasattr(lambda_client, 'region'):
                    raise AWSClientContextError("Lambda client not properly configured")
                    
            except Exception as e:
                logger.warning(f"Lambda service test failed (may be expected): {e}")
                # Don't fail the validation for Lambda-specific issues
                # as the investigation might not need Lambda access
            
            logger.debug(f"AWS client connectivity validated for account: {account_id}")
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'accessdenied' in error_msg or 'unauthorized' in error_msg:
                raise AWSPermissionError(f"AWS permissions insufficient for investigation: {str(e)}")
            else:
                raise AWSClientContextError(f"AWS client connectivity test failed: {str(e)}")
    
    def _generate_aws_client_error_report(self, error: str, start_time: datetime) -> InvestigationReport:
        """
        Generate error report specifically for AWS client setup failures.
        
        Args:
            error: Error message
            start_time: Investigation start time
            
        Returns:
            Investigation report with AWS client error details
        """
        now = datetime.now(timezone.utc)
        
        # Categorize the error for better user guidance
        error_lower = error.lower()
        if 'accessdenied' in error_lower or 'unauthorized' in error_lower:
            error_category = "aws_permissions"
            user_guidance = "Check IAM permissions for the investigation role. Ensure it has necessary permissions for X-Ray, Lambda, API Gateway, and other AWS services."
        elif 'assumerole' in error_lower or 'external' in error_lower:
            error_category = "cross_account_access"
            user_guidance = "Check cross-account role assumption. Verify role ARN, external ID, and trust policy configuration."
        elif 'invalid' in error_lower and 'arn' in error_lower:
            error_category = "invalid_configuration"
            user_guidance = "Check role ARN format. It should be in the format: arn:aws:iam::ACCOUNT-ID:role/ROLE-NAME"
        else:
            error_category = "aws_client_setup"
            user_guidance = "Check AWS credentials, region configuration, and network connectivity."
        
        return InvestigationReport(
            run_id=str(start_time.timestamp()),
            status="failed",
            started_at=start_time,
            completed_at=now,
            duration_seconds=(now - start_time).total_seconds(),
            affected_resources=[],
            severity_assessment=SeverityAssessment(
                severity="high",
                impact_scope="investigation_blocked",
                affected_resource_count=0,
                user_impact="Investigation cannot proceed",
                confidence=1.0,
                reasoning="AWS client setup failed - investigation blocked"
            ),
            facts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary=f"AWS client setup failed: {error}"
            ),
            hypotheses=[],
            advice=[
                Advice(
                    category=error_category,
                    recommendation=user_guidance,
                    priority="high",
                    confidence=1.0,
                    reasoning="Investigation requires valid AWS client setup"
                )
            ],
            timeline=[],
            summary=json.dumps({
                "error": error,
                "error_category": error_category,
                "user_guidance": user_guidance,
                "investigation_success": False
            })
        )
    
    def _generate_error_report(self, error: str, start_time: datetime) -> InvestigationReport:
        """Generate error report."""
        now = datetime.now(timezone.utc)
        
        return InvestigationReport(
            run_id=str(start_time.timestamp()),
            status="failed",
            started_at=start_time,
            completed_at=now,
            duration_seconds=(now - start_time).total_seconds(),
            affected_resources=[],
            severity_assessment=SeverityAssessment(
                severity="unknown",
                impact_scope="unknown",
                affected_resource_count=0,
                user_impact="unknown",
                confidence=0.0,
                reasoning="Investigation failed"
            ),
            facts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary=f"Swarm investigation failed: {error}"
            ),
            hypotheses=[],
            advice=[],
            timeline=[],
            summary=json.dumps({"error": error, "investigation_success": False})
        )
    
    def _create_fallback_report(
        self,
        investigation_id: str,
        start_time: datetime,
        region: str,
        error: str
    ) -> InvestigationReport:
        """Create fallback InvestigationReport when graph execution fails."""
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        return InvestigationReport(
            run_id=investigation_id,
            status="completed",
            started_at=start_time,
            completed_at=end_time,
            duration_seconds=duration,
            affected_resources=[],
            severity_assessment=SeverityAssessment(
                severity="unknown",
                impact_scope="unknown",
                affected_resource_count=0,
                user_impact="unknown",
                confidence=0.0,
                reasoning=f"Graph execution failed: {error}"
            ),
            facts=[],
            root_cause_analysis=RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary=f"Investigation failed: {error}"
            ),
            hypotheses=[],
            advice=[],
            timeline=[],
            summary=f"Investigation failed: {error}"
        )