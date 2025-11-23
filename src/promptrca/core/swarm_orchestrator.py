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
                            # Set metadata fields that should NOT be generated by AI
                            report.run_id = investigation_id
                            report.status = "completed"
                            report.started_at = investigation_start_time
                            report.completed_at = datetime.now(timezone.utc)
                            report.duration_seconds = (datetime.now(timezone.utc) - investigation_start_time).total_seconds()
                        else:
                            # Failed to extract report - raise exception
                            raise ValueError("Failed to extract report from nested MultiAgentResult")
                    else:
                        # Direct result
                        report = report_node_result.result
                        # Set metadata fields that should NOT be generated by AI
                        report.run_id = investigation_id
                        report.status = "completed"
                        report.started_at = investigation_start_time
                        report.completed_at = datetime.now(timezone.utc)
                        report.duration_seconds = (datetime.now(timezone.utc) - investigation_start_time).total_seconds()
                else:
                    # Report generation failed - raise exception
                    raise ValueError("Report generation node did not return results")
                
            except Exception as e:
                logger.error(f"Graph execution failed: {e}")
                # Re-raise - failure is failure, no fallbacks
                raise
            
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
    