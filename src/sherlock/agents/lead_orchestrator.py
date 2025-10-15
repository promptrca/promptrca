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
from ..utils.config import get_region, get_memory_config
from ..memory import MemoryClient, MemoryResult
from ..memory.graph_builder import GraphBuilder
from ..memory.models import GraphNode, GraphEdge, ObservabilityPointer, ConfigSnapshot, Incident, Pattern
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
        
        # Initialize memory client
        memory_config = get_memory_config()
        self.memory_client = MemoryClient(memory_config) if memory_config["enabled"] else None
        
        # Initialize graph builder
        # TODO: Get real account ID from AWS STS or configuration
        self.graph_builder = GraphBuilder(account_id="123456789012", region=self.region)
        
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

            # 2.5 ENRICH context by fetching X-Ray traces (NEW)
            context = await self._enrich_context_with_traces(context)

            # 3. Query memory if available (NEW)
            memory_context = await self._get_memory_context(context)

            # 4. Create investigation prompt for lead agent (enhanced with memory)
            investigation_prompt = self._create_investigation_prompt(context, memory_context)

            # 5. Run lead orchestrator agent
            logger.info("🤖 Running lead orchestrator agent...")
            agent_result = self.lead_agent(investigation_prompt)
            
            # 6. Parse agent response and extract structured data
            facts, hypotheses, advice = self._parse_agent_response(agent_result, context, memory_context)

            # 7. Generate investigation report
            report = self._generate_investigation_report(context, facts, hypotheses, advice, region)

            # 8. Build knowledge graph from investigation artifacts (NEW)
            await self._build_knowledge_graph(context, facts, report, region)

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
    
    async def _enrich_context_with_traces(self, context: InvestigationContext) -> InvestigationContext:
        """Enrich investigation context by fetching and analyzing X-Ray traces."""
        try:
            if not context.trace_ids:
                return context
            
            logger.info(f"📊 Fetching {len(context.trace_ids)} X-Ray traces...")
            
            # Import the tool for resource extraction
            import json
            from ..tools import get_all_resources_from_trace
            
            discovered_resources = []
            
            for trace_id in context.trace_ids:
                try:
                    # Use the specialized tool to extract ALL resources from trace
                    resources_json = get_all_resources_from_trace(trace_id, region=self.region)
                    resources_data = json.loads(resources_json)
                    
                    if "error" not in resources_data:
                        # Convert to ParsedResource objects
                        for resource in resources_data.get("resources", []):
                            parsed_resource = ParsedResource(
                                type=resource.get("type", "unknown"),
                                name=resource.get("name", "unknown"),
                                identifier=resource.get("arn") or resource.get("name"),
                                region=self.region,
                                metadata=resource.get("metadata", {})
                            )
                            discovered_resources.append(parsed_resource)
                            logger.info(f"✅ Discovered {resource.get('type')}: {resource.get('name')}")
                    else:
                        logger.warning(f"Failed to extract resources from trace {trace_id}: {resources_data.get('error')}")
                
                except Exception as e:
                    logger.warning(f"Failed to process trace {trace_id}: {e}")
            
            # Add discovered resources to primary targets if none were specified
            if not context.primary_targets and discovered_resources:
                logger.info(f"🎯 Setting {len(discovered_resources)} discovered resources as primary targets")
                context.primary_targets.extend(discovered_resources)
            elif discovered_resources:
                logger.info(f"📝 Adding {len(discovered_resources)} discovered resources to context")
                # Add to primary targets without duplicates
                existing_identifiers = {r.identifier for r in context.primary_targets}
                for resource in discovered_resources:
                    if resource.identifier not in existing_identifiers:
                        context.primary_targets.append(resource)
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to enrich context with traces: {e}")
            return context
    
    async def _get_memory_context(self, context: InvestigationContext) -> Optional[str]:
        """Query memory using RAG and format context for prompt"""
        if not self.memory_client or not context.primary_targets:
            return None
        
        try:
            # Use primary target as seed for RAG retrieval
            seed = context.primary_targets[0].name
            if context.trace_ids:
                seed = context.trace_ids[0]  # Prefer trace ID if available
            
            # Retrieve context using new RAG system
            rag_result = await self.memory_client.retrieve_context(seed, k_hop=2)
            
            if not rag_result:
                return None
            
            # Format RAG context for prompt
            memory_context = "RELEVANT KNOWLEDGE GRAPH CONTEXT:\n\n"
            
            # Add subgraph info
            if rag_result.subgraph['nodes']:
                memory_context += f"DISCOVERED RESOURCES ({len(rag_result.subgraph['nodes'])}):\n"
                for node in rag_result.subgraph['nodes'][:5]:  # Limit to 5 nodes
                    memory_context += f"- {node.get('type', 'unknown')}: {node.get('name', 'unknown')}\n"
                memory_context += "\n"
            
            # Add relationships
            if rag_result.subgraph['edges']:
                memory_context += f"RELATIONSHIPS ({len(rag_result.subgraph['edges'])}):\n"
                for edge in rag_result.subgraph['edges'][:5]:  # Limit to 5 edges
                    from_name = edge.get('from_arn', '').split(':')[-1]
                    to_name = edge.get('to_arn', '').split(':')[-1]
                    memory_context += f"- {from_name} {edge.get('rel', '')} {to_name} (confidence: {edge.get('confidence', 0):.2f})\n"
                memory_context += "\n"
            
            # Add patterns
            if rag_result.patterns:
                memory_context += f"MATCHED PATTERNS ({len(rag_result.patterns)}):\n"
                for pattern in rag_result.patterns[:3]:  # Limit to 3 patterns
                    memory_context += f"- {pattern.get('title', 'Unknown Pattern')}\n"
                    memory_context += f"  Tags: {', '.join(pattern.get('tags', []))}\n"
                    memory_context += f"  Steps: {pattern.get('playbook_steps', '')[:200]}...\n\n"
            
            # Add related incidents
            if rag_result.related_incidents:
                memory_context += f"RELATED INCIDENTS ({len(rag_result.related_incidents)}):\n"
                for incident in rag_result.related_incidents[:3]:  # Limit to 3 incidents
                    memory_context += f"- {incident.get('incident_id', 'Unknown')}\n"
                    memory_context += f"  Root Cause: {incident.get('root_cause', '')[:200]}...\n"
                    memory_context += f"  Fix: {incident.get('fix', '')[:200]}...\n\n"
            
            return memory_context
            
        except Exception as e:
            logger.warning(f"Memory RAG query failed: {e}")
            return None
    
    def _format_memory_context(self, similar: List[MemoryResult]) -> str:
        """Format memory results for prompt injection"""
        context = "\n" + "="*60 + "\n"
        context += "RELEVANT PAST INVESTIGATIONS (from memory system)\n"
        context += "="*60 + "\n\n"
        
        for i, mem in enumerate(similar, 1):
            outcome_icon = "✓" if mem.outcome == "resolved" else "⚠" if mem.outcome == "partial" else "✗"
            
            context += f"{i}. Investigation #{mem.investigation_id} (similarity: {mem.similarity_score:.2f})\n"
            context += f"   Resource: {mem.resource_type}:{mem.resource_name}\n"
            context += f"   Root Cause: {mem.root_cause_summary}\n"
            context += f"   Solution: {mem.advice_summary}\n"
            context += f"   Outcome: {outcome_icon} {mem.outcome.upper()} (quality: {mem.quality_score:.2f})\n"
            context += f"   Date: {mem.created_at}\n\n"
        
        # Add learned patterns
        patterns = self._extract_patterns(similar)
        if patterns:
            context += "\nLEARNED PATTERNS:\n"
            context += patterns + "\n"
        
        context += "="*60 + "\n"
        context += "Use the above historical context to inform your investigation.\n"
        context += "Prioritize solutions that have been proven effective.\n"
        context += "="*60 + "\n\n"
        
        return context
    
    def _extract_patterns(self, similar: List[MemoryResult]) -> str:
        """Extract common patterns from similar investigations"""
        # Count most common root causes
        root_causes = {}
        successful_advice = {}
        
        for mem in similar:
            if mem.outcome == "resolved":
                root_causes[mem.error_type] = root_causes.get(mem.error_type, 0) + 1
                successful_advice[mem.advice_summary] = successful_advice.get(mem.advice_summary, 0) + 1
        
        patterns = []
        
        if root_causes:
            most_common = max(root_causes.items(), key=lambda x: x[1])
            patterns.append(f"- {most_common[0]} is the most common root cause ({most_common[1]}/{len(similar)} cases)")
        
        if successful_advice:
            top_advice = max(successful_advice.items(), key=lambda x: x[1])
            patterns.append(f"- Successfully resolved {top_advice[1]} times with: {top_advice[0]}")
        
        return "\n".join(patterns) if patterns else ""
    
    def _create_investigation_prompt(self, context: InvestigationContext, memory_context: Optional[str] = None) -> str:
        """Create investigation prompt for the lead orchestrator agent"""
        prompt_parts = []
        
        prompt_parts.append("INVESTIGATION REQUEST:")
        
        if context.trace_ids:
            prompt_parts.append(f"X-Ray Trace ID: {context.trace_ids[0]}")
        
        if context.error_messages:
            prompt_parts.append(f"Error: {context.error_messages[0]}")
        
        if context.primary_targets:
            targets_text = ", ".join([f"{t.type}:{t.name}" for t in context.primary_targets])
            prompt_parts.append(f"Target Resources: {targets_text}")
        else:
            prompt_parts.append("\n⚠️ CRITICAL: No AWS resources identified.")
            prompt_parts.append("DO NOT assume, infer, or hallucinate resource names.")
            prompt_parts.append("Respond: 'Unable to investigate - no resources found.'\n")
        
        if context.business_context:
            prompt_parts.append(f"Business Context: {context.business_context}")
        
        if memory_context:
            prompt_parts.append(memory_context)
        
        prompt_parts.append("\nTASK:")
        prompt_parts.append("Conduct root cause analysis using specialist agents.")
        
        prompt_parts.append("\nIMPORTANT RULES:")
        prompt_parts.append("1. ONLY investigate resources explicitly listed above")
        prompt_parts.append("2. DO NOT make up resource names, ARNs, or identifiers")
        prompt_parts.append("3. Base analysis ONLY on data returned from tools")
        prompt_parts.append("4. If tool returns 'ResourceNotFoundException', report as fact")
        prompt_parts.append("5. If no data available, state 'Insufficient data'")
        
        if memory_context:
            prompt_parts.append("6. Use historical context to inform analysis")
        
        prompt_parts.append("\nWORKFLOW:")
        prompt_parts.append("1. Analyze X-Ray trace if available")
        prompt_parts.append("2. Call specialist tools for listed resources only")
        prompt_parts.append("3. Synthesize findings from tool outputs")
        prompt_parts.append("4. Provide recommendations based on actual data")
        
        return "\n".join(prompt_parts)
    
    def _parse_agent_response(self, agent_result, context: InvestigationContext, memory_context: Optional[str] = None) -> (List[Fact], List[Hypothesis], List[Advice]):
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
        
        # Extract memory results if available
        memory_results = None
        if memory_context and self.memory_client:
            # Try to extract memory results from the context
            # This is a simplified approach - in practice, you'd want to store the actual MemoryResult objects
            memory_results = []  # For now, we'll pass empty list
        
        # Generate hypotheses if none provided
        if not hypotheses:
            from .hypothesis_agent import HypothesisAgent
            from strands import Agent
            # Wrap the model in a Strands Agent
            strands_agent = Agent(model=self.model)
            hypothesis_agent = HypothesisAgent(strands_agent=strands_agent)
            hypotheses = hypothesis_agent.generate_hypotheses(facts, memory_results)
        
        # Generate advice if none provided
        if not advice and hypotheses:
            from .advice_agent import AdviceAgent
            advice_agent = AdviceAgent()
            advice = advice_agent.generate_advice(facts, hypotheses, memory_results)
        
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
    
    async def _build_knowledge_graph(self, context: InvestigationContext, facts: List[Fact], report: InvestigationReport, region: str) -> None:
        """Build knowledge graph from investigation artifacts."""
        if not self.memory_client:
            return
        
        try:
            logger.info("🏗️ Building knowledge graph from investigation artifacts...")
            
            # Extract nodes and edges from X-Ray traces
            all_nodes = []
            all_edges = []
            all_pointers = []
            
            for trace_id in context.trace_ids:
                try:
                    # Get trace data (this would need to be implemented)
                    trace_data = await self._get_trace_data(trace_id)
                    if trace_data:
                        nodes, edges, pointers = self.graph_builder.extract_from_trace(trace_data)
                        all_nodes.extend(nodes)
                        all_edges.extend(edges)
                        all_pointers.extend(pointers)
                except Exception as e:
                    logger.warning(f"Failed to extract from trace {trace_id}: {e}")
            
            # Extract edges from logs for primary targets
            for target in context.primary_targets:
                try:
                    # Get log data (this would need to be implemented)
                    log_data = await self._get_log_data(target.name, target.type)
                    if log_data:
                        edges = self.graph_builder.extract_from_logs(log_data, target.name)
                        all_edges.extend(edges)
                except Exception as e:
                    logger.warning(f"Failed to extract from logs for {target.name}: {e}")
            
            # Save nodes to memory
            for node in all_nodes:
                await self.memory_client.upsert_node(node)
            
            # Save edges to memory
            for edge in all_edges:
                await self.memory_client.upsert_edge(edge)
            
            # Save pointers to memory
            for pointer in all_pointers:
                await self.memory_client.upsert_pointer(pointer)
            
            # Save incident to memory
            incident = self._create_incident_from_report(report, context, all_nodes)
            if incident:
                await self.memory_client.save_incident(incident)
            
            # Optionally create pattern if investigation was successful
            if report.status == "completed" and len(facts) > 5:
                pattern = await self._create_pattern_from_investigation(facts, report.hypotheses, report.advice, all_nodes, all_edges)
                if pattern:
                    await self.memory_client.save_pattern(pattern)
            
            logger.info(f"✅ Knowledge graph updated: {len(all_nodes)} nodes, {len(all_edges)} edges")
            
        except Exception as e:
            logger.error(f"Failed to build knowledge graph: {e}")
    
    def _create_incident_from_report(self, report: InvestigationReport, context: InvestigationContext, nodes: List[GraphNode]) -> Optional[Incident]:
        """Create incident record from investigation report."""
        try:
            # Extract root cause from report
            root_cause = ""
            if report.root_cause_analysis and report.root_cause_analysis.primary_root_cause:
                root_cause = report.root_cause_analysis.primary_root_cause
            
            # Extract signals from facts
            signals = []
            for fact in report.facts:
                if "error" in fact.description.lower() or "exception" in fact.description.lower():
                    signals.append(fact.description[:100])
            
            # Extract fix from advice
            fix = ""
            if report.advice:
                fix = "; ".join([advice.description for advice in report.advice[:3]])
            
            # Extract useful queries from facts
            useful_queries = ""
            for fact in report.facts:
                if "query" in fact.description.lower() or "command" in fact.description.lower():
                    useful_queries += fact.description + "\n"
            
            incident = Incident(
                incident_id=report.run_id,
                nodes=[node.arn for node in nodes],
                root_cause=root_cause,
                signals=signals,
                fix=fix,
                useful_queries=useful_queries,
                pattern_ids=[],  # Will be populated if patterns are created
                created_at=report.started_at.isoformat(),
                account_id=self.graph_builder.account_id,
                region=self.region
            )
            
            return incident
            
        except Exception as e:
            logger.error(f"Failed to create incident from report: {e}")
            return None
    
    async def _create_pattern_from_investigation(self, facts: List[Fact], hypotheses: List[Hypothesis], advice: List[Advice], nodes: List[GraphNode], edges: List[GraphEdge]) -> Optional[Pattern]:
        """Create pattern from successful investigation using structural signatures."""
        try:
            # Build pattern content
            pattern_title = f"Pattern: {len(nodes)} resource investigation"
            
            # Extract tags from node types
            node_types = sorted(list(set([node.type for node in nodes])))
            tags = node_types + ["investigation", "pattern"]
            
            # Build playbook steps from advice
            playbook_steps = "\n".join([f"{i+1}. {adv.description}" for i, adv in enumerate(advice[:5])])
            
            # Build structural signatures
            topology_sig = self._build_topology_signature_from_graph(nodes, edges)
            relationship_types = sorted(list(set([e.rel for e in edges])))
            
            signatures = {
                "topology_signature": topology_sig,
                "resource_types": node_types,
                "relationship_types": relationship_types,
                "depth": self._calculate_graph_depth(edges),
                "stack_signature": self._build_stack_signature(nodes, edges),
                "topology_motif": self._build_topology_motif(edges)
            }
            
            pattern = Pattern(
                pattern_id=f"P-{int(datetime.now().timestamp())}",
                title=pattern_title,
                tags=tags,
                signatures=signatures,
                playbook_steps=playbook_steps,
                popularity=0.0,
                last_used_at=datetime.now(timezone.utc).isoformat(),
                match_count=0
            )
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to create pattern from investigation: {e}")
            return None
    
    def _build_stack_signature(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
        """Build stack signature from nodes and edges."""
        node_types = sorted([node.type for node in nodes])
        edge_types = sorted([edge.rel for edge in edges])
        return f"{'-'.join(node_types)}:{'-'.join(edge_types)}"
    
    def _build_topology_motif(self, edges: List[GraphEdge]) -> List[str]:
        """Build topology motif from edges."""
        motifs = []
        for edge in edges:
            from_type = edge.from_arn.split(':')[2] if ':' in edge.from_arn else 'unknown'
            to_type = edge.to_arn.split(':')[2] if ':' in edge.to_arn else 'unknown'
            motifs.append(f"{from_type}->{to_type}({edge.rel})")
        return motifs

    def _build_topology_signature_from_graph(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> str:
        """Generate topology signature from graph nodes and edges."""
        import hashlib
        node_types = sorted([n.type for n in nodes])
        edge_rels = sorted([e.rel for e in edges])
        content = f"nodes:{','.join(node_types)}|edges:{','.join(edge_rels)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_graph_depth(self, edges: List[GraphEdge]) -> int:
        """Calculate maximum depth of graph."""
        # Simple approximation: max path length
        return min(len(edges), 10)
    
    async def _get_trace_data(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get X-Ray trace data using the xray tool."""
        try:
            import json
            from ..tools import get_xray_trace
            
            # Call the actual X-Ray trace tool
            trace_json = get_xray_trace(trace_id, region=self.region)
            trace_data = json.loads(trace_json)
            
            # Check for errors
            if "error" in trace_data:
                logger.warning(f"Failed to fetch trace {trace_id}: {trace_data['error']}")
                return None
            
            return trace_data
        except Exception as e:
            logger.error(f"Error fetching trace {trace_id}: {e}")
            return None
    
    async def _get_log_data(self, resource_name: str, resource_type: str) -> Optional[List[Dict[str, Any]]]:
        """Get log data for resource using CloudWatch logs tool."""
        try:
            import json
            from ..tools import get_cloudwatch_logs
            
            log_group_map = {
                "lambda": f"/aws/lambda/{resource_name}",
                "apigateway": f"/aws/apigateway/{resource_name}",
                "stepfunctions": f"/aws/states/{resource_name}"
            }
            
            log_group = log_group_map.get(resource_type.lower())
            if not log_group:
                logger.warning(f"Unknown resource type for logs: {resource_type}")
                return None
            
            logs_json = get_cloudwatch_logs(log_group, hours_back=1, region=self.region)
            logs_data = json.loads(logs_json)
            
            if "error" in logs_data:
                logger.warning(f"Failed to fetch logs for {resource_name}: {logs_data['error']}")
                return None
            
            return logs_data.get("events", [])
            
        except Exception as e:
            logger.error(f"Error fetching logs for {resource_name}: {e}")
            return None
