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
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from strands import Agent, tool
from strands.multiagent import Swarm

from ..models import (
    InvestigationReport, Fact, Hypothesis, Advice,
    AffectedResource, SeverityAssessment, RootCauseAnalysis, EventTimeline
)
from ..clients import AWSClient
from ..context import set_aws_client, clear_aws_client
from ..utils.config import (
    create_hypothesis_agent_model,
    create_root_cause_agent_model,
    get_region
)
from ..utils import get_logger
from ..specialists import (
    LambdaSpecialist, APIGatewaySpecialist, 
    StepFunctionsSpecialist, TraceSpecialist,
    InvestigationContext
)

logger = get_logger(__name__)


# Tool-wrapped specialists following Strands best practices
@tool
def lambda_specialist_tool(resource_data: str, investigation_context: str) -> str:
    """
    Analyze Lambda function configuration, logs, and performance issues.
    
    Args:
        resource_data: JSON string containing Lambda resource information
        investigation_context: JSON string with trace IDs, region, and context
    
    Returns:
        JSON string with analysis results including facts and findings
    """
    try:
        resource = json.loads(resource_data)
        context_data = json.loads(investigation_context)
        
        specialist = LambdaSpecialist()
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=context_data.get('parsed_inputs')
        )
        
        # Run analysis synchronously (Strands tools are sync)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            facts = loop.run_until_complete(specialist.analyze(resource, context))
        finally:
            loop.close()
        
        # Convert facts to serializable format
        results = {
            "specialist_type": "lambda",
            "resource_name": resource.get('name', 'unknown'),
            "facts": [
                {
                    "source": fact.source,
                    "content": fact.content,
                    "confidence": fact.confidence,
                    "metadata": fact.metadata
                }
                for fact in facts
            ],
            "analysis_summary": f"Analyzed Lambda function {resource.get('name')} - found {len(facts)} facts"
        }
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Lambda specialist tool failed: {e}")
        return json.dumps({
            "specialist_type": "lambda",
            "error": str(e),
            "facts": []
        })


@tool
def apigateway_specialist_tool(resource_data: str, investigation_context: str) -> str:
    """
    Analyze API Gateway configuration, stage settings, and integration issues.
    
    Args:
        resource_data: JSON string containing API Gateway resource information
        investigation_context: JSON string with trace IDs, region, and context
    
    Returns:
        JSON string with analysis results including facts and findings
    """
    try:
        resource = json.loads(resource_data)
        context_data = json.loads(investigation_context)
        
        specialist = APIGatewaySpecialist()
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=context_data.get('parsed_inputs')
        )
        
        # Run analysis synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            facts = loop.run_until_complete(specialist.analyze(resource, context))
        finally:
            loop.close()
        
        results = {
            "specialist_type": "apigateway",
            "resource_name": resource.get('name', 'unknown'),
            "facts": [
                {
                    "source": fact.source,
                    "content": fact.content,
                    "confidence": fact.confidence,
                    "metadata": fact.metadata
                }
                for fact in facts
            ],
            "analysis_summary": f"Analyzed API Gateway {resource.get('name')} - found {len(facts)} facts"
        }
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"API Gateway specialist tool failed: {e}")
        return json.dumps({
            "specialist_type": "apigateway",
            "error": str(e),
            "facts": []
        })


@tool
def stepfunctions_specialist_tool(resource_data: str, investigation_context: str) -> str:
    """
    Analyze Step Functions state machine executions, errors, and permissions.
    
    Args:
        resource_data: JSON string containing Step Functions resource information
        investigation_context: JSON string with trace IDs, region, and context
    
    Returns:
        JSON string with analysis results including facts and findings
    """
    try:
        resource = json.loads(resource_data)
        context_data = json.loads(investigation_context)
        
        specialist = StepFunctionsSpecialist()
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=context_data.get('parsed_inputs')
        )
        
        # Run analysis synchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            facts = loop.run_until_complete(specialist.analyze(resource, context))
        finally:
            loop.close()
        
        results = {
            "specialist_type": "stepfunctions",
            "resource_name": resource.get('name', 'unknown'),
            "facts": [
                {
                    "source": fact.source,
                    "content": fact.content,
                    "confidence": fact.confidence,
                    "metadata": fact.metadata
                }
                for fact in facts
            ],
            "analysis_summary": f"Analyzed Step Functions {resource.get('name')} - found {len(facts)} facts"
        }
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Step Functions specialist tool failed: {e}")
        return json.dumps({
            "specialist_type": "stepfunctions",
            "error": str(e),
            "facts": []
        })


@tool
def trace_specialist_tool(trace_ids: str, investigation_context: str) -> str:
    """
    Perform deep X-Ray trace analysis to extract service interactions and errors.
    
    Args:
        trace_ids: JSON array of trace IDs to analyze
        investigation_context: JSON string with region and context
    
    Returns:
        JSON string with trace analysis results
    """
    try:
        trace_id_list = json.loads(trace_ids)
        context_data = json.loads(investigation_context)
        
        specialist = TraceSpecialist()
        context = InvestigationContext(
            trace_ids=trace_id_list,
            region=context_data.get('region', 'us-east-1'),
            parsed_inputs=context_data.get('parsed_inputs')
        )
        
        all_facts = []
        
        # Analyze each trace
        for trace_id in trace_id_list:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                facts = loop.run_until_complete(specialist.analyze_trace(trace_id, context))
                all_facts.extend(facts)
            finally:
                loop.close()
        
        results = {
            "specialist_type": "trace",
            "trace_count": len(trace_id_list),
            "facts": [
                {
                    "source": fact.source,
                    "content": fact.content,
                    "confidence": fact.confidence,
                    "metadata": fact.metadata
                }
                for fact in all_facts
            ],
            "analysis_summary": f"Analyzed {len(trace_id_list)} traces - found {len(all_facts)} facts"
        }
        
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"Trace specialist tool failed: {e}")
        return json.dumps({
            "specialist_type": "trace",
            "error": str(e),
            "facts": []
        })


class SwarmOrchestrator:
    """
    Strands Swarm-based orchestrator for AWS infrastructure investigation.
    
    Uses the Swarm pattern where specialized agents collaborate autonomously
    to investigate AWS issues, with each agent deciding when to hand off
    to other specialists based on their findings.
    """
    
    def __init__(self, region: str = None):
        """Initialize the swarm orchestrator."""
        self.region = region or get_region()
        
        # Initialize input parser
        from ..agents.input_parser_agent import InputParserAgent
        self.input_parser = InputParserAgent()
        
        # Create specialized agents
        self._create_specialist_agents()
        
        # Create the investigation swarm
        self._create_swarm()
        
        logger.info("✨ SwarmOrchestrator initialized with Strands best practices")
    
    def _create_specialist_agents(self):
        """Create specialized agents following Strands patterns."""
        
        # Lambda Specialist Agent
        self.lambda_agent = Agent(
            name="lambda_specialist",
            system_prompt="""You are a Lambda specialist agent for AWS infrastructure investigation.

Your expertise includes:
- Lambda function configuration analysis
- CloudWatch logs analysis for Lambda errors
- Performance and timeout issues
- IAM permission problems for Lambda
- Integration issues with other AWS services

When you receive investigation requests:
1. Use the lambda_specialist_tool to analyze Lambda resources
2. Look for patterns in errors, timeouts, and permission issues
3. If you find issues related to API Gateway or Step Functions, hand off to those specialists
4. Provide clear, actionable findings about Lambda-specific problems

Always use the handoff_to_agent tool when you discover issues outside your Lambda expertise.""",
            tools=[lambda_specialist_tool]
        )
        
        # API Gateway Specialist Agent  
        self.apigateway_agent = Agent(
            name="apigateway_specialist",
            system_prompt="""You are an API Gateway specialist agent for AWS infrastructure investigation.

Your expertise includes:
- API Gateway configuration and stage analysis
- Integration configurations and mapping templates
- IAM roles and permissions for API Gateway
- Execution logs and error patterns
- Integration with Lambda and Step Functions

When you receive investigation requests:
1. Use the apigateway_specialist_tool to analyze API Gateway resources
2. Focus on integration errors, permission issues, and configuration problems
3. If you find Lambda function errors, hand off to the Lambda specialist
4. If you find Step Functions integration issues, hand off to the Step Functions specialist
5. Provide clear findings about API Gateway-specific problems

Always use the handoff_to_agent tool when you discover issues outside your API Gateway expertise.""",
            tools=[apigateway_specialist_tool]
        )
        
        # Step Functions Specialist Agent
        self.stepfunctions_agent = Agent(
            name="stepfunctions_specialist",
            system_prompt="""You are a Step Functions specialist agent for AWS infrastructure investigation.

Your expertise includes:
- State machine execution analysis
- Step Functions error patterns and causes
- IAM permissions for state machine execution
- Integration with Lambda functions and other services
- Execution history and failure analysis

When you receive investigation requests:
1. Use the stepfunctions_specialist_tool to analyze Step Functions resources
2. Focus on execution failures, permission errors, and state transitions
3. If you find Lambda function issues, hand off to the Lambda specialist
4. If you find API Gateway integration problems, hand off to the API Gateway specialist
5. Provide clear findings about Step Functions-specific problems

Always use the handoff_to_agent tool when you discover issues outside your Step Functions expertise.""",
            tools=[stepfunctions_specialist_tool]
        )
        
        # Trace Analysis Specialist Agent
        self.trace_agent = Agent(
            name="trace_specialist",
            system_prompt="""You are a trace analysis specialist agent for AWS infrastructure investigation.

Your expertise includes:
- X-Ray trace analysis and service mapping
- Service interaction patterns and timing
- Error propagation across services
- Performance bottlenecks and latency issues
- Cross-service communication problems

When you receive investigation requests:
1. Use the trace_specialist_tool to analyze X-Ray traces
2. Identify service interaction patterns and errors
3. Hand off to specific service specialists (Lambda, API Gateway, Step Functions) when you find service-specific issues
4. Provide insights about cross-service communication and timing

Always use the handoff_to_agent tool to route service-specific findings to the appropriate specialist.""",
            tools=[trace_specialist_tool]
        )
    
    def _create_swarm(self):
        """Create the investigation swarm with all specialist agents."""
        self.swarm = Swarm(
            nodes=[
                self.lambda_agent,
                self.apigateway_agent, 
                self.stepfunctions_agent,
                self.trace_agent
            ],
            entry_point=self.trace_agent,  # Start with trace analysis
            max_handoffs=20,
            max_iterations=10,  # Prevent infinite loops
            execution_timeout=900.0,  # 15 minutes
            node_timeout=300.0  # 5 minutes per agent
        )
    
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
        
        logger.info("=" * 80)
        logger.info("🚀 SWARM INVESTIGATION STARTED (Strands Best Practices)")
        logger.info("=" * 80)
        
        try:
            # Setup AWS client context
            aws_client = AWSClient(
                region=region,
                role_arn=assume_role_arn,
                external_id=external_id
            )
            set_aws_client(aws_client)
            
            # Parse inputs
            logger.info("📝 Step 1: Parsing inputs...")
            parsed_inputs = self._parse_inputs(inputs, region)
            logger.info(f"   ✓ Parsed {len(parsed_inputs.primary_targets)} targets, "
                       f"{len(parsed_inputs.trace_ids)} traces")
            
            # Discover resources
            logger.info("🔍 Step 2: Discovering resources...")
            resources = await self._discover_resources(parsed_inputs)
            logger.info(f"   ✓ Discovered {len(resources)} resources")
            
            # Prepare investigation context for swarm (make it JSON serializable)
            investigation_context = {
                "trace_ids": parsed_inputs.trace_ids,
                "region": region,
                "parsed_inputs": {
                    "trace_ids": parsed_inputs.trace_ids,
                    "primary_targets": [
                        {
                            "type": target.type,
                            "name": target.name,
                            "arn": target.arn,
                            "region": target.region,
                            "metadata": target.metadata
                        }
                        for target in parsed_inputs.primary_targets
                    ]
                }
            }
            
            # Create investigation prompt for swarm
            investigation_prompt = self._create_investigation_prompt(
                resources, parsed_inputs, investigation_context
            )
            
            # Execute swarm investigation
            logger.info("🤖 Step 3: Executing swarm investigation...")
            swarm_result = self.swarm(
                investigation_prompt,
                invocation_state={
                    "resources": resources,
                    "investigation_context": investigation_context,
                    "region": region,
                    "trace_ids": parsed_inputs.trace_ids
                }
            )
            
            # Extract facts from swarm results
            facts = self._extract_facts_from_swarm_result(swarm_result)
            logger.info(f"   ✓ Extracted {len(facts)} facts from swarm")
            
            # Generate hypotheses
            logger.info("🧠 Step 4: Generating hypotheses...")
            hypotheses = self._run_hypothesis_agent(facts)
            logger.info(f"   ✓ Generated {len(hypotheses)} hypotheses")
            
            # Analyze root cause
            logger.info("🔬 Step 5: Analyzing root cause...")
            root_cause = self._analyze_root_cause(hypotheses, facts, region,
                                                   assume_role_arn, external_id)
            logger.info(f"   ✓ Root cause identified (confidence: {root_cause.confidence_score:.2f})")
            
            # Generate report
            logger.info("📄 Step 6: Generating investigation report...")
            report = self._generate_report(
                facts, hypotheses, [], root_cause,
                resources, investigation_start_time, region
            )
            
            duration = (datetime.now(timezone.utc) - investigation_start_time).total_seconds()
            logger.info("=" * 80)
            logger.info(f"✅ SWARM INVESTIGATION COMPLETE in {duration:.2f}s")
            logger.info("=" * 80)
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Swarm investigation failed: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            
            return self._generate_error_report(str(e), investigation_start_time)
            
        finally:
            clear_aws_client()    

    def _parse_inputs(self, inputs: Dict[str, Any], region: str):
        """Parse investigation inputs using existing parser."""
        logger.debug(f"[DEBUG] _parse_inputs received: {json.dumps(inputs, default=str)}")
        
        # Use existing input parser logic
        if 'investigation_inputs' in inputs:
            logger.debug("[DEBUG] Using investigation_inputs (structured path)")
            return self.input_parser.parse_inputs(inputs['investigation_inputs'], region)
        
        # Handle legacy formats
        structured: Dict[str, Any] = {}
        if 'xray_trace_id' in inputs:
            structured['trace_ids'] = [inputs['xray_trace_id']]
        if 'function_name' in inputs:
            structured['primary_targets'] = [{"type": "lambda", "name": inputs['function_name'], "region": region}]
        if 'investigation_target' in inputs:
            t = inputs['investigation_target']
            structured.setdefault('primary_targets', []).append({
                "type": t.get('type'), "name": t.get('name'), "region": t.get('region', region), "metadata": t.get('metadata', {})
            })
        if structured:
            logger.debug("[DEBUG] Converted legacy/direct format to structured")
            return self.input_parser.parse_inputs(structured, region)
        
        if 'free_text_input' in inputs:
            logger.debug("[DEBUG] Using free_text_input")
            return self.input_parser.parse_inputs(inputs['free_text_input'], region)
        
        # Default: treat dict as structured
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
        
        prompt = f"""AWS Infrastructure Investigation Request

I need you to investigate an AWS infrastructure issue. Here's what we know:

DISCOVERED RESOURCES:
{chr(10).join(resource_summary)}

REGION: {investigation_context.get('region', 'unknown')}
{trace_info}

INVESTIGATION CONTEXT:
{json.dumps(investigation_context, indent=2)}

RESOURCES DATA:
{json.dumps(resources, indent=2)}

Please coordinate as a team to thoroughly investigate this issue:

1. **Trace Specialist**: Start by analyzing any X-Ray traces to understand service interactions and identify error patterns
2. **Service Specialists**: Each specialist should analyze their respective resources using their specialized tools
3. **Collaboration**: Hand off findings between specialists when you discover cross-service issues
4. **Comprehensive Analysis**: Ensure all resources are thoroughly analyzed for configuration, permissions, and runtime issues

Focus on finding the root cause of any errors, performance issues, or misconfigurations. Pay special attention to:
- Permission errors (IAM roles and policies)
- Service integration problems
- Configuration mismatches
- Runtime errors and exceptions

Begin the investigation now."""
        
        return prompt
    
    def _extract_facts_from_swarm_result(self, swarm_result) -> List[Fact]:
        """Extract facts from the swarm investigation result."""
        facts = []
        
        try:
            # The swarm result should contain the conversation history
            # We need to parse the tool calls and responses to extract facts
            result_content = str(swarm_result.content) if hasattr(swarm_result, 'content') else str(swarm_result)
            
            # Look for JSON blocks in the result that contain facts
            import re
            json_blocks = re.findall(r'```json\s*\n(.*?)\n```', result_content, re.DOTALL)
            
            for json_block in json_blocks:
                try:
                    data = json.loads(json_block)
                    if 'facts' in data:
                        for fact_data in data['facts']:
                            facts.append(Fact(
                                source=fact_data.get('source', 'swarm'),
                                content=fact_data.get('content', ''),
                                confidence=fact_data.get('confidence', 0.8),
                                metadata=fact_data.get('metadata', {})
                            ))
                except json.JSONDecodeError:
                    continue
            
            # Also look for direct JSON objects in the result
            json_objects = re.findall(r'\{[^{}]*"facts"[^{}]*\}', result_content, re.DOTALL)
            for json_obj in json_objects:
                try:
                    data = json.loads(json_obj)
                    if 'facts' in data:
                        for fact_data in data['facts']:
                            facts.append(Fact(
                                source=fact_data.get('source', 'swarm'),
                                content=fact_data.get('content', ''),
                                confidence=fact_data.get('confidence', 0.8),
                                metadata=fact_data.get('metadata', {})
                            ))
                except json.JSONDecodeError:
                    continue
            
            # If no structured facts found, create summary facts from the result
            if not facts:
                facts.append(Fact(
                    source='swarm_investigation',
                    content=f"Swarm investigation completed with {len(result_content)} characters of analysis",
                    confidence=0.9,
                    metadata={'result_length': len(result_content)}
                ))
                
                # Extract key findings from the text
                if 'error' in result_content.lower():
                    facts.append(Fact(
                        source='swarm_investigation',
                        content="Swarm investigation identified error conditions",
                        confidence=0.8,
                        metadata={'contains_errors': True}
                    ))
                
                if 'permission' in result_content.lower():
                    facts.append(Fact(
                        source='swarm_investigation',
                        content="Swarm investigation identified potential permission issues",
                        confidence=0.8,
                        metadata={'permission_related': True}
                    ))
            
        except Exception as e:
            logger.error(f"Failed to extract facts from swarm result: {e}")
            facts.append(Fact(
                source='swarm_investigation',
                content=f"Swarm investigation completed but fact extraction failed: {str(e)}",
                confidence=0.7,
                metadata={'extraction_error': True}
            ))
        
        return facts
    
    def _run_hypothesis_agent(self, facts: List[Fact]) -> List[Hypothesis]:
        """Run the hypotheses phase with existing agent."""
        from ..agents.hypothesis_agent import HypothesisAgent
        from strands import Agent
        
        model = create_hypothesis_agent_model()
        strands_agent = Agent(model=model)
        agent = HypothesisAgent(strands_agent=strands_agent)
        return agent.generate_hypotheses(facts)
    
    def _analyze_root_cause(
        self,
        hypotheses: List[Hypothesis],
        facts: List[Fact],
        region: str,
        assume_role_arn: Optional[str],
        external_id: Optional[str]
    ):
        """Analyze root cause from hypotheses."""
        from ..agents.root_cause_agent import RootCauseAgent
        from strands import Agent
        
        root_cause_model = create_root_cause_agent_model()
        root_cause_strands_agent = Agent(model=root_cause_model)
        root_cause_agent = RootCauseAgent(strands_agent=root_cause_strands_agent)
        
        return root_cause_agent.analyze_root_cause(hypotheses, facts)
    
    def _generate_report(
        self,
        facts: List[Fact],
        hypotheses: List[Hypothesis],
        advice: List[Advice],
        root_cause,
        resources: List[Dict[str, Any]],
        start_time: datetime,
        region: str
    ) -> InvestigationReport:
        """Generate investigation report."""
        now = datetime.now(timezone.utc)
        
        # Build affected resources
        affected_resources = []
        for resource in resources:
            affected_resources.append(AffectedResource(
                resource_type=resource.get('type', 'unknown'),
                resource_id=resource.get('arn', resource.get('name', 'unknown')),
                resource_name=resource.get('name', 'unknown'),
                health_status='unknown',
                detected_issues=[],
                metadata={'region': region, 'source': resource.get('source', 'discovery')}
            ))
        
        # Create severity assessment
        severity = SeverityAssessment(
            severity="medium",
            impact_scope="service",
            affected_resource_count=len(affected_resources),
            user_impact="moderate",
            confidence=root_cause.confidence_score,
            reasoning=root_cause.analysis_summary
        )
        
        # Build timeline
        timeline = [
            EventTimeline(
                timestamp=start_time,
                event_type="investigation_start",
                component="swarm_orchestrator",
                description="Swarm investigation started",
                metadata={"orchestration_type": "strands_swarm"}
            ),
            EventTimeline(
                timestamp=now,
                event_type="investigation_complete",
                component="swarm_orchestrator",
                description="Swarm investigation completed successfully",
                metadata={"orchestration_type": "strands_swarm"}
            )
        ]
        
        # Generate summary
        summary = {
            "investigation_type": "swarm_orchestration",
            "orchestration": "strands_swarm",
            "resources_investigated": len(resources),
            "specialists_available": 4,  # lambda, apigateway, stepfunctions, trace
            "facts": len(facts),
            "hypotheses": len(hypotheses),
            "advice": len(advice),
            "region": region
        }
        
        return InvestigationReport(
            run_id=str(start_time.timestamp()),
            status="completed",
            started_at=start_time,
            completed_at=now,
            duration_seconds=(now - start_time).total_seconds(),
            affected_resources=affected_resources,
            severity_assessment=severity,
            facts=facts,
            root_cause_analysis=root_cause,
            hypotheses=hypotheses,
            advice=advice,
            timeline=timeline,
            summary=json.dumps(summary)
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