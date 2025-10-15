#!/usr/bin/env python3
"""
Sherlock Core - AI-powered root cause analysis for AWS infrastructure
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

Contact: christiangenn99+sherlock@gmail.com

Lead Orchestrator Agent - Multi-Agent System for AWS Incident Investigation
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from strands import Agent, tool
from ..models import InvestigationReport, Fact, Hypothesis, Advice, AffectedResource, SeverityAssessment, RootCauseAnalysis, EventTimeline
from ..utils import normalize_facts, get_logger
from ..utils.config import get_region
from ..agents.input_parser_agent import ParsedInputs, ParsedResource
from ..agents.specialized.lambda_agent import create_lambda_agent, create_lambda_agent_tool
from ..agents.specialized.apigateway_agent import create_apigateway_agent, create_apigateway_agent_tool
from ..agents.specialized.stepfunctions_agent import create_stepfunctions_agent, create_stepfunctions_agent_tool
from ..agents.specialized.iam_agent import create_iam_agent, create_iam_agent_tool
from ..agents.specialized.dynamodb_agent import create_dynamodb_agent, create_dynamodb_agent_tool
from ..agents.specialized.s3_agent import create_s3_agent, create_s3_agent_tool
from ..agents.specialized.sqs_agent import create_sqs_agent, create_sqs_agent_tool
from ..agents.specialized.sns_agent import create_sns_agent, create_sns_agent_tool
from ..agents.specialized.eventbridge_agent import create_eventbridge_agent, create_eventbridge_agent_tool
from ..agents.specialized.vpc_agent import create_vpc_agent, create_vpc_agent_tool
from ..tools import (
    get_xray_trace,
    get_lambda_config,
    get_api_gateway_stage_config,
    get_stepfunctions_definition,
    get_iam_role_config,
    get_lambda_logs,
    get_apigateway_logs,
    get_stepfunctions_logs
)

logger = get_logger(__name__)


@dataclass
class InvestigationContext:
    """Context for multi-agent investigation."""
    primary_targets: List[ParsedResource]
    trace_ids: List[str]
    error_messages: List[str]
    business_context: Dict[str, Any]
    time_range: Optional[Dict[str, str]] = None
    investigation_prompt: str = ""


class LeadOrchestratorAgent:
    """Lead Orchestrator Agent that coordinates specialist agents for AWS incident investigation."""
    
    def __init__(self, model, region: str = None):
        """Initialize the lead orchestrator agent."""
        self.model = model
        self.region = region or get_region()
        
        # Create specialized agents
        self.lambda_agent = create_lambda_agent(model)
        self.apigateway_agent = create_apigateway_agent(model)
        self.stepfunctions_agent = create_stepfunctions_agent(model)
        self.iam_agent = create_iam_agent(model)
        self.dynamodb_agent = create_dynamodb_agent(model)
        self.s3_agent = create_s3_agent(model)
        self.sqs_agent = create_sqs_agent(model)
        self.sns_agent = create_sns_agent(model)
        self.eventbridge_agent = create_eventbridge_agent(model)
        self.vpc_agent = create_vpc_agent(model)
        
        # Create agent tools
        self.lambda_tool = create_lambda_agent_tool(self.lambda_agent)
        self.apigateway_tool = create_apigateway_agent_tool(self.apigateway_agent)
        self.stepfunctions_tool = create_stepfunctions_agent_tool(self.stepfunctions_agent)
        self.iam_tool = create_iam_agent_tool(self.iam_agent)
        self.dynamodb_tool = create_dynamodb_agent_tool(self.dynamodb_agent)
        self.s3_tool = create_s3_agent_tool(self.s3_agent)
        self.sqs_tool = create_sqs_agent_tool(self.sqs_agent)
        self.sns_tool = create_sns_agent_tool(self.sns_agent)
        self.eventbridge_tool = create_eventbridge_agent_tool(self.eventbridge_agent)
        self.vpc_tool = create_vpc_agent_tool(self.vpc_agent)
        
        # Initialize input parser
        from .input_parser_agent import InputParserAgent
        self.input_parser = InputParserAgent()
        
        # Initialize root cause agent for synthesis
        from .root_cause_agent import RootCauseAgent
        from ..clients.aws_client import AWSClient
        from strands import Agent
        aws_client = AWSClient(region=self.region)
        # Wrap the model in a Strands Agent
        strands_agent = Agent(model=model)
        self.root_cause_agent = RootCauseAgent(aws_client=aws_client, strands_agent=strands_agent)
        
        # Create the lead orchestrator agent with all specialist tools
        self.lead_agent = self._create_lead_agent()
    
    def _create_lead_agent(self) -> Agent:
        """Create the lead orchestrator agent with all specialist tools."""
        
        system_prompt = """You are the lead AWS incident investigator. Your role: coordinate specialist agents and gather evidence.

INVESTIGATION FLOW:
1. If X-Ray trace ID provided → call get_xray_trace to discover service interactions
2. From trace/context, identify AWS services involved
3. Call appropriate specialist agent for each service (call ONCE per service)
4. Return all findings - let downstream agents synthesize

AVAILABLE SPECIALISTS:
- investigate_lambda_function(function_name, context)
- investigate_apigateway(api_id, stage, context)
- investigate_stepfunctions(state_machine_arn, context)
- investigate_iam_role(role_name, context)
- investigate_dynamodb_issue(issue_description)
- investigate_s3_issue(issue_description)
- investigate_sqs_issue(issue_description)
- investigate_sns_issue(issue_description)
- investigate_eventbridge_issue(issue_description)
- investigate_vpc_issue(issue_description)

RULES:
- Call specialists for services explicitly mentioned OR discovered in X-Ray trace
- Provide context to specialists (error messages, trace findings)
- Do NOT generate hypotheses yourself - specialists will do that
- Do NOT speculate about services not observed
- Be concise

OUTPUT: Relay specialist findings without additional interpretation"""

        return Agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=[
                # X-Ray and AWS tools
                get_xray_trace,
                get_lambda_config,
                get_api_gateway_stage_config,
                get_stepfunctions_definition,
                get_iam_role_config,
                get_lambda_logs,
                get_apigateway_logs,
                get_stepfunctions_logs,
                # Specialist agent tools
                self.lambda_tool,
                self.apigateway_tool,
                self.stepfunctions_tool,
                self.iam_tool,
                self.dynamodb_tool,
                self.s3_tool,
                self.sqs_tool,
                self.sns_tool,
                self.eventbridge_tool,
                self.vpc_tool,
            ]
        )
    
    async def investigate(self, inputs: Dict[str, Any], region: str = None) -> InvestigationReport:
        """Run multi-agent investigation using the lead orchestrator."""
        region = region or get_region()
        logger.info("🔍 Starting multi-agent investigation...")

        # Generate investigation ID
        import time
        investigation_id = f"{int(time.time() * 1000)}.{hash(str(inputs)) % 10000}"

        try:
            # 1. Parse inputs
            parsed_inputs = self._parse_inputs(inputs, region)

            # 2. Build investigation context
            context = self._build_investigation_context(parsed_inputs)

            # 3. Create investigation prompt for lead agent
            investigation_prompt = self._create_investigation_prompt(context)

            # 4. Run lead orchestrator agent
            logger.info("🤖 Running lead orchestrator agent...")
            agent_result = self.lead_agent(investigation_prompt)
            
            # 5. Parse agent response and extract structured data
            facts, hypotheses, advice = self._parse_agent_response(agent_result, context)

            # 6. Generate investigation report
            report = self._generate_investigation_report(context, facts, hypotheses, advice, region)

            return report
        
        except Exception as e:
            import traceback
            logger.error(f"❌ Investigation failed: {e}")
            logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            
            # Return error report
            from ..models.base import InvestigationReport
            from datetime import datetime, timezone
            return InvestigationReport(
                run_id=investigation_id,
                status="failed",
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                duration_seconds=0.0,
                affected_resources=[],
                severity_assessment=None,
                facts=[],
                root_cause_analysis=None,
                hypotheses=[],
                advice=[],
                timeline=[],
                summary=f"Investigation failed: {str(e)}"
            ).to_dict()
    
    def _parse_inputs(self, inputs: Dict[str, Any], region: str) -> ParsedInputs:
        """Parse inputs using the input parser agent."""
        # Check if it's free text input
        if 'free_text_input' in inputs:
            return self.input_parser.parse_inputs(inputs['free_text_input'], region)
        
        # Check if it's structured input
        elif 'investigation_inputs' in inputs:
            return self.input_parser.parse_inputs(inputs['investigation_inputs'], region)
        
        # Fallback to legacy format
        else:
            # Convert legacy format to structured format
            structured_input = {
                'primary_targets': [],
                'trace_ids': [],
                'error_messages': [],
                'context': {}
            }
            
            if 'function_name' in inputs:
                structured_input['primary_targets'].append({
                    'type': 'lambda_function',
                    'name': inputs['function_name'],
                    'region': region
                })
            
            if 'xray_trace_id' in inputs:
                structured_input['trace_ids'].append(inputs['xray_trace_id'])
            
            if 'investigation_target' in inputs:
                target = inputs['investigation_target']
                structured_input['primary_targets'].append({
                    'type': target.get('type', 'unknown'),
                    'name': target.get('name', ''),
                    'region': target.get('region', region),
                    'metadata': target.get('metadata', {})
                })
            
            return self.input_parser.parse_inputs(structured_input, region)
    
    def _build_investigation_context(self, parsed_inputs: ParsedInputs) -> InvestigationContext:
        """Build investigation context from parsed inputs."""
        logger.info(f"🏗️ Building context for {len(parsed_inputs.primary_targets)} targets...")
        
        return InvestigationContext(
            primary_targets=parsed_inputs.primary_targets,
            trace_ids=parsed_inputs.trace_ids,
            error_messages=parsed_inputs.error_messages,
            business_context=parsed_inputs.business_context,
            time_range=parsed_inputs.time_range
        )
    
    def _create_investigation_prompt(self, context: InvestigationContext) -> str:
        """Create investigation prompt for the lead orchestrator agent."""
        prompt_parts = []
        
        # Add investigation context
        prompt_parts.append("INVESTIGATION REQUEST:")
        
        if context.trace_ids:
            prompt_parts.append(f"X-Ray Trace ID: {context.trace_ids[0]}")
        
        if context.error_messages:
            prompt_parts.append(f"Error: {context.error_messages[0]}")
        
        if context.primary_targets:
            targets_text = ", ".join([f"{t.type}:{t.name}" for t in context.primary_targets])
            prompt_parts.append(f"Target Resources: {targets_text}")
        
        if context.business_context:
            prompt_parts.append(f"Business Context: {context.business_context}")
        
        # Add investigation instructions
        prompt_parts.append("\nTASK:")
        prompt_parts.append("Conduct a comprehensive root cause analysis using specialist agents.")
        prompt_parts.append("Start with X-Ray trace analysis if available, then investigate relevant services.")
        prompt_parts.append("Synthesize findings from multiple specialists to identify the root cause.")
        prompt_parts.append("Provide specific, actionable recommendations for remediation.")
        
        return "\n".join(prompt_parts)
    
    def _parse_agent_response(self, agent_result, context: InvestigationContext) -> (List[Fact], List[Hypothesis], List[Advice]):
        """Parse the lead agent's response to extract structured data."""
        # Extract response content
        response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)
        
        # For now, create basic facts from the response
        # In a full implementation, this would parse the agent's structured output
        facts = []
        hypotheses = []
        advice = []
        
        # Create a fact from the agent's analysis
        facts.append(Fact(
            source="lead_orchestrator",
            content=f"Lead orchestrator analysis: {response[:500]}...",
            confidence=0.8,
            metadata={"investigation_type": "multi_agent", "agent_count": 10}
        ))
        
        # Generate hypotheses if none provided
        if not hypotheses:
            from .hypothesis_agent import HypothesisAgent
            from strands import Agent
            # Wrap the model in a Strands Agent
            strands_agent = Agent(model=self.model)
            hypothesis_agent = HypothesisAgent(strands_agent=strands_agent)
            hypotheses = hypothesis_agent.generate_hypotheses(facts)
        
        # Generate advice if none provided
        if not advice and hypotheses:
            from .advice_agent import AdviceAgent
            advice_agent = AdviceAgent()
            advice = advice_agent.generate_advice(facts, hypotheses)
        
        return facts, hypotheses, advice
    
    def _generate_investigation_report(self, context: InvestigationContext, facts: List[Fact], hypotheses: List[Hypothesis], advice: List[Advice], region: str) -> InvestigationReport:
        """Generate investigation report from multi-agent findings."""
        logger.info("📋 Generating investigation report...")
        
        now = datetime.now(timezone.utc)
        start_time = now  # Simplified for now
        
        # Build affected resources from context
        affected_resources = []
        for target in context.primary_targets:
            affected_resources.append(AffectedResource(
                resource_type=target.type,
                resource_id=target.name,
                resource_name=target.name,
                health_status="unknown",
                detected_issues=context.error_messages,
                metadata={"region": region, "source": "multi_agent"}
            ))
        
        # Use root cause agent to analyze and synthesize findings
        root_cause = self.root_cause_agent.analyze_root_cause(hypotheses, facts)
        
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
        timeline = self._build_timeline_from_context(context)
        
        # Add investigation events
        timeline.insert(0, EventTimeline(
            timestamp=start_time,
            event_type="investigation_start",
            component="lead_orchestrator",
            description="Multi-agent investigation started",
            metadata={
                "context": {
                    "primary_targets": [{"type": t.type, "name": t.name, "region": t.region} for t in context.primary_targets],
                    "trace_ids": context.trace_ids,
                    "error_messages": context.error_messages,
                    "business_context": context.business_context
                }
            }
        ))
        timeline.append(EventTimeline(
            timestamp=now,
            event_type="investigation_complete",
            component="lead_orchestrator",
            description="Multi-agent investigation completed",
            metadata={"agent_type": "lead_orchestrator"}
        ))
        
        # Generate summary
        summary = {
            "investigation_type": "multi_agent",
            "target_count": len(context.primary_targets),
            "trace_count": len(context.trace_ids),
            "error_count": len(context.error_messages),
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
    
    def _build_timeline_from_context(self, context: InvestigationContext) -> List[EventTimeline]:
        """Build timeline from investigation context."""
        timeline = []
        
        # Add trace events if available
        for trace_id in context.trace_ids:
            timeline.append(EventTimeline(
                timestamp=datetime.now(timezone.utc),
                event_type="trace_analysis",
                component="xray",
                description=f"X-Ray trace {trace_id} analyzed",
                metadata={"trace_id": trace_id}
            ))
        
        return timeline
