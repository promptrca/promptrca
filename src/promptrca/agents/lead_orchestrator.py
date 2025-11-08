#!/usr/bin/env python3
"""
PromptRCA Core - AI-powered root cause analysis for AWS infrastructure
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

Lead Orchestrator Agent - Multi-Agent System for AWS Incident Investigation
"""

import asyncio
import json
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field

from strands import Agent, tool

from ..models import InvestigationReport, Fact, Hypothesis, Advice, AffectedResource, SeverityAssessment, RootCauseAnalysis, EventTimeline
from ..utils import normalize_facts, get_logger
from ..utils.config import get_region, create_orchestrator_model, create_lambda_agent_model, create_apigateway_agent_model, create_stepfunctions_agent_model, create_iam_agent_model, create_dynamodb_agent_model, create_s3_agent_model, create_sqs_agent_model, create_sns_agent_model, create_eventbridge_agent_model, create_vpc_agent_model, create_hypothesis_agent_model, create_root_cause_agent_model
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
    start_time: Optional[datetime] = None


class LeadOrchestratorAgent:
    """Lead Orchestrator Agent that coordinates specialist agents for AWS incident investigation."""
    
    def __init__(self, model=None, region: str = None):
        """Initialize the lead orchestrator agent."""
        # Use provided model or create orchestrator-specific model
        self.model = model or create_orchestrator_model()
        self.region = region or get_region()
        
        # Create specialized agents with their specific models
        self.lambda_agent = create_lambda_agent(create_lambda_agent_model())
        self.apigateway_agent = create_apigateway_agent(create_apigateway_agent_model())
        self.stepfunctions_agent = create_stepfunctions_agent(create_stepfunctions_agent_model())
        self.iam_agent = create_iam_agent(create_iam_agent_model())
        self.dynamodb_agent = create_dynamodb_agent(create_dynamodb_agent_model())
        self.s3_agent = create_s3_agent(create_s3_agent_model())
        self.sqs_agent = create_sqs_agent(create_sqs_agent_model())
        self.sns_agent = create_sns_agent(create_sns_agent_model())
        self.eventbridge_agent = create_eventbridge_agent(create_eventbridge_agent_model())
        self.vpc_agent = create_vpc_agent(create_vpc_agent_model())
        
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
        
        # Initialize synthesis model for root cause analysis
        from strands import Agent
        from ..utils.config import create_synthesis_model
        # AWSClient will be created per investigation with the appropriate role
        self.region = region
        # Use synthesis model for conservative root cause analysis
        synthesis_model = create_synthesis_model()
        strands_agent = Agent(model=synthesis_model)
        # Root cause agent will be initialized per investigation
        self.synthesis_model = synthesis_model
        self.strands_agent = strands_agent
        
        
        # Create the lead orchestrator agent with all specialist tools
        self.lead_agent = self._create_lead_agent()
    
    
    def _create_lead_agent(self) -> Agent:
        """Create the lead orchestrator agent with all specialist tools."""
        
        # Check if AWS Knowledge MCP is enabled
        from ..utils.config import get_mcp_config
        mcp_config = get_mcp_config()
        mcp_enabled = mcp_config.get("enabled", False)
        
        # Build system prompt based on MCP availability
        if mcp_enabled:
            system_prompt = """You are the lead AWS incident investigator. Your role: coordinate specialist agents and gather evidence.

INVESTIGATION FLOW (CRITICAL ORDER):
1. **FIRST: Check AWS Service Health** → Use check_aws_service_health() to rule out AWS-side issues
2. **SECOND: Check CloudTrail** → Use get_recent_cloudtrail_events() to find recent configuration changes
3. If X-Ray trace ID provided → analyze trace data to discover service interactions and error flows
4. From trace/context, identify AWS services involved in the incident
5. Delegate to appropriate specialist agents based on discovered services and error patterns
6. Use AWS Knowledge tools to get official documentation and best practices when relevant
7. Synthesize findings from all specialists into a comprehensive analysis

WHY THIS ORDER MATTERS:
- AWS Service Health: If AWS is down, don't waste time investigating your code
- CloudTrail: 80% of incidents are caused by recent configuration changes
- X-Ray: Shows the actual error flow and affected services
- Specialists: Deep dive into specific service issues

SPECIALIST DELEGATION STRATEGY:
- Lambda functions: Delegate to Lambda specialist for function configuration, logs, and performance issues
- API Gateway: Delegate to API Gateway specialist for integration, routing, and request/response problems
- Step Functions: Delegate to Step Functions specialist for workflow execution and state machine issues
- DynamoDB: Delegate to DynamoDB specialist for table performance, capacity, and throttling issues
- IAM: Delegate to IAM specialist for permission and access control problems
- S3: Delegate to S3 specialist for storage, access, and bucket configuration issues
- SQS/SNS: Delegate to messaging specialists for queue and notification delivery problems
- EventBridge: Delegate to EventBridge specialist for event routing and rule execution issues
- VPC: Delegate to VPC specialist for networking, security groups, and connectivity problems

AWS KNOWLEDGE INTEGRATION:
- Use AWS documentation tools to enhance findings with official best practices
- Cross-reference specialist findings with AWS guidance and recommendations
- Provide authoritative context for complex AWS service interactions

COORDINATION RULES:
- Delegate to specialists for services explicitly mentioned OR discovered in X-Ray trace
- Provide rich context to specialists (error messages, trace findings, business impact)
- Focus on the actual error source identified in trace analysis, not just mentioned services
- Use AWS Knowledge tools to validate findings and provide authoritative guidance
- Synthesize specialist findings into coherent root cause analysis
- Do NOT generate hypotheses yourself - let specialists do their domain-specific analysis
- Do NOT speculate about services not observed in traces or context

OUTPUT: Relay specialist findings with AWS documentation context when relevant"""
        else:
            system_prompt = """You are the lead AWS incident investigator. Your role: coordinate specialist agents and gather evidence.

INVESTIGATION FLOW (CRITICAL ORDER):
1. **FIRST: Check AWS Service Health** → Use check_aws_service_health() to rule out AWS-side issues
2. **SECOND: Check CloudTrail** → Use get_recent_cloudtrail_events() to find recent configuration changes
3. If X-Ray trace ID provided → call get_xray_trace to discover service interactions
4. From trace/context, identify AWS services involved
5. Call appropriate specialist agent for each service (call ONCE per service)
6. Return all findings - let downstream agents synthesize

WHY THIS ORDER MATTERS:
- AWS Service Health: If AWS is down, don't waste time investigating your code
- CloudTrail: 80% of incidents are caused by recent configuration changes
- X-Ray: Shows the actual error flow and affected services
- Specialists: Deep dive into specific service issues

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

DELEGATION DECISION PROCESS:
1. Extract service names/ARNs from trace data (DO NOT invent)
2. For EACH discovered service → call its specialist ONCE
3. Pass rich context (error messages, trace excerpts, timing info)
4. Aggregate all specialist responses
5. Return structured output with findings from ALL specialists

EVIDENCE-BASED DELEGATION:
- ONLY delegate to specialists for services with evidence:
  * Service name appears in trace subsegments
  * Service mentioned in error messages
  * Service ARN in target resources list
- DO NOT delegate to services based on assumptions
- If unsure whether to investigate a service → DON'T

QUALITY CONTROL:
- Verify tool outputs before relaying them
- If specialist returns empty results → include that fact
- If specialist call fails → report the failure
- Distinguish between "no issues found" vs "couldn't investigate"

RULES:
- Call specialists for services explicitly mentioned OR discovered in X-Ray trace
- Provide context to specialists (error messages, trace findings)
- Do NOT generate hypotheses yourself - specialists will do that
- Do NOT speculate about services not observed
- Be concise

OUTPUT: Relay specialist findings"""
        
        # Build tools list - no binding needed since tools get client from context
        from ..tools import (
            # AWS Health and CloudTrail tools (CHECK THESE FIRST!)
            check_aws_service_health,
            get_account_health_events,
            check_service_quota_status,
            get_recent_cloudtrail_events,
            find_correlated_changes,
            get_iam_policy_changes,
            # X-Ray tools
            get_xray_trace,
            get_xray_service_graph,
            get_xray_trace_summaries,
            get_all_resources_from_trace,
            query_logs_by_trace_id,
            # Lambda tools
            get_lambda_config,
            get_lambda_logs,
            get_lambda_metrics,
            get_lambda_layers,
            # API Gateway tools
            get_api_gateway_stage_config,
            get_apigateway_logs,
            get_api_gateway_metrics,
            resolve_api_gateway_id,
            # Step Functions tools
            get_stepfunctions_definition,
            get_stepfunctions_logs,
            get_stepfunctions_execution_details,
            get_stepfunctions_metrics,
            # IAM tools
            get_iam_role_config,
            get_iam_policy_document,
            simulate_iam_policy,
            get_iam_user_policies,
            # CloudWatch tools
            get_cloudwatch_logs,
            get_cloudwatch_metrics,
            get_cloudwatch_alarms,
            list_cloudwatch_dashboards,
            # VPC tools
            get_vpc_config,
            get_subnet_config,
            get_security_group_config,
            get_network_interface_config,
            get_nat_gateway_config,
            get_internet_gateway_config,
            # SQS tools
            get_sqs_queue_config,
            get_sqs_queue_metrics,
            get_sqs_dead_letter_queue,
            list_sqs_queues,
            # DynamoDB tools
            get_dynamodb_table_config,
            get_dynamodb_table_metrics,
            describe_dynamodb_streams,
            list_dynamodb_tables,
            # SNS tools
            get_sns_topic_config,
            get_sns_topic_metrics,
            get_sns_subscriptions,
            list_sns_topics,
            # S3 tools
            get_s3_bucket_config,
            get_s3_bucket_metrics,
            list_s3_bucket_objects,
            get_s3_bucket_policy,
            # EventBridge tools
            get_eventbridge_rule_config,
            get_eventbridge_targets,
            get_eventbridge_metrics,
            list_eventbridge_rules,
            get_eventbridge_bus_config,
        )
        
        tools = [
            # AWS Health and CloudTrail tools (PRIORITY - check these first!)
            check_aws_service_health,
            get_account_health_events,
            check_service_quota_status,
            get_recent_cloudtrail_events,
            find_correlated_changes,
            get_iam_policy_changes,
            # All AWS service tools (get client from context)
            get_xray_trace,
            get_xray_service_graph,
            get_xray_trace_summaries,
            get_all_resources_from_trace,
            query_logs_by_trace_id,
            get_lambda_config,
            get_lambda_logs,
            get_lambda_metrics,
            get_lambda_layers,
            get_api_gateway_stage_config,
            get_apigateway_logs,
            get_api_gateway_metrics,
            resolve_api_gateway_id,
            get_stepfunctions_definition,
            get_stepfunctions_logs,
            get_stepfunctions_execution_details,
            get_stepfunctions_metrics,
            get_iam_role_config,
            get_iam_policy_document,
            simulate_iam_policy,
            get_iam_user_policies,
            get_cloudwatch_logs,
            get_cloudwatch_metrics,
            get_cloudwatch_alarms,
            list_cloudwatch_dashboards,
            get_vpc_config,
            get_subnet_config,
            get_security_group_config,
            get_network_interface_config,
            get_nat_gateway_config,
            get_internet_gateway_config,
            get_sqs_queue_config,
            get_sqs_queue_metrics,
            get_sqs_dead_letter_queue,
            list_sqs_queues,
            get_dynamodb_table_config,
            get_dynamodb_table_metrics,
            describe_dynamodb_streams,
            list_dynamodb_tables,
            get_sns_topic_config,
            get_sns_topic_metrics,
            get_sns_subscriptions,
            list_sns_topics,
            get_s3_bucket_config,
            get_s3_bucket_metrics,
            list_s3_bucket_objects,
            get_s3_bucket_policy,
            get_eventbridge_rule_config,
            get_eventbridge_targets,
            get_eventbridge_metrics,
            list_eventbridge_rules,
            get_eventbridge_bus_config,
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
        
        # Add AWS Knowledge MCP tools only if enabled
        if mcp_enabled:
            from ..tools import (
                search_aws_documentation,
                read_aws_documentation,
                get_aws_documentation_recommendations
            )
            tools.extend([
                search_aws_documentation,
                read_aws_documentation,
                get_aws_documentation_recommendations
            ])

        return Agent(
            model=self.model,
            system_prompt=system_prompt,
            tools=tools,
            trace_attributes={
                "service.name": "promptrca-orchestrator",
                "service.version": "1.0.0",
                "agent.type": "lead_orchestrator",
                "agent.region": self.region
            }
        )
    
    async def investigate(self, inputs: Dict[str, Any], region: str = None, assume_role_arn: Optional[str] = None, external_id: Optional[str] = None) -> InvestigationReport:
        """Run multi-agent investigation using the lead orchestrator."""
        region = region or get_region()
        logger.info("🔍 Starting multi-agent investigation...")
        logger.info(f"🔍 [DEBUG] LeadOrchestrator received assume_role_arn: {assume_role_arn}")
        logger.info(f"🔍 [DEBUG] LeadOrchestrator received external_id: {external_id}")

        # Capture investigation start time
        investigation_start_time = datetime.now(timezone.utc)

        # Generate investigation ID
        import time
        investigation_id = f"{int(time.time() * 1000)}.{hash(str(inputs)) % 10000}"


        # Create root span for entire investigation
        from opentelemetry import trace
        tracer = trace.get_tracer(__name__)
        
        with tracer.start_as_current_span(
            "promptrca.investigation",
            attributes={
                "investigation.id": investigation_id,
                "investigation.region": region,
                "investigation.type": "multi_agent",
                "investigation.assume_role_arn": assume_role_arn or "",
                "investigation.external_id": external_id or ""
            }
        ) as investigation_span:
            
            # Record input for Langfuse trace-level display
            input_data = json.dumps(inputs, default=str)
            investigation_span.set_attribute("langfuse.trace.input", input_data)
            
            # Also add as OTEL event for standards compliance
            investigation_span.add_event("investigation.input", attributes={"data": input_data})

            try:
                # 0. Create AWSClient with assumed role for entire investigation
                from ..clients import AWSClient
                from ..context import set_aws_client, clear_aws_client
                
                aws_client = AWSClient(
                    region=region,
                    role_arn=assume_role_arn,
                    external_id=external_id
                )
                logger.info(f"Created AWSClient for account: {aws_client.account_id}")
                
                # Set AWS client in context for all tools to access
                # Tools will retrieve it programmatically via get_aws_client()
                set_aws_client(aws_client)
                
                # 1. Parse inputs
                parsed_inputs = self._parse_inputs(inputs, region)

                # 2. Build investigation context
                context = self._build_investigation_context(parsed_inputs, investigation_start_time)

                # 2.5 ENRICH context by fetching X-Ray traces (NEW)
                context = await self._enrich_context_with_traces(context)

                # 2.6 Insufficient data check
                if not context.primary_targets and not context.trace_ids:
                    logger.warning("Insufficient data: no resources or traces identified")
                    return self._create_insufficient_data_report(investigation_id, 
                        "No AWS resources or trace IDs identified. Cannot investigate.", investigation_start_time)

                # 3. Create investigation prompt for lead agent
                investigation_prompt = self._create_investigation_prompt(context)
                
                # Debug: Log the prompt to see what the AI is receiving
                logger.info(f"🔍 DEBUG: Investigation prompt:\n{investigation_prompt}")

                # 5. Run lead orchestrator agent
                logger.info("🤖 Running lead orchestrator agent...")
                agent_result = self.lead_agent(investigation_prompt)
            
                
                # 6. Parse agent response and extract structured data
                facts, hypotheses, advice = self._parse_agent_response(agent_result, context)

                # 7. Generate investigation report
                report = self._generate_investigation_report(context, facts, hypotheses, advice, region, assume_role_arn, external_id)

                # Record output for Langfuse trace-level display
                output_data = json.dumps(report.to_dict() if hasattr(report, 'to_dict') else {"summary": str(report)}, default=str)
                investigation_span.set_attribute("langfuse.trace.output", output_data)

                # Also add as OTEL event
                investigation_span.add_event("investigation.output", attributes={"data": output_data})

                # Set metadata attributes for filtering
                if hasattr(report, 'status'):
                    investigation_span.set_attribute("output.status", report.status)
                if hasattr(report, 'facts'):
                    investigation_span.set_attribute("output.facts_count", len(report.facts))
                if hasattr(report, 'hypotheses'):
                    investigation_span.set_attribute("output.hypotheses_count", len(report.hypotheses))

                return report
            
            except Exception as e:
                logger.error(f"❌ Investigation failed: {e}")
                logger.error(f"❌ Full traceback: {traceback.format_exc()}")
                
                # Create error report
                from ..models.base import InvestigationReport
                error_report = InvestigationReport(
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
                )
                
                # Record error output for Langfuse
                error_output = json.dumps(
                    error_report.to_dict() if hasattr(error_report, 'to_dict') else {"error": str(e)},
                    default=str
                )
                investigation_span.set_attribute("langfuse.trace.output", error_output)
                investigation_span.add_event("investigation.output", attributes={"data": error_output})
                
                # Set error metadata
                investigation_span.set_attribute("output.status", "failed")
                investigation_span.set_attribute("error", True)
                investigation_span.set_attribute("error.type", type(e).__name__)
                investigation_span.set_attribute("error.message", str(e))
                
                return error_report
            
            finally:
                # Always clear AWS client context after investigation
                clear_aws_client()
    
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
    
    def _build_investigation_context(self, parsed_inputs: ParsedInputs, start_time: Optional[datetime] = None) -> InvestigationContext:
        """Build investigation context from parsed inputs."""
        logger.info(f"🏗️ Building context for {len(parsed_inputs.primary_targets)} targets...")
        
        return InvestigationContext(
            primary_targets=parsed_inputs.primary_targets,
            trace_ids=parsed_inputs.trace_ids,
            error_messages=parsed_inputs.error_messages,
            business_context=parsed_inputs.business_context,
            time_range=parsed_inputs.time_range,
            start_time=start_time
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
                    resources_json = get_all_resources_from_trace(trace_id)
                    resources_data = json.loads(resources_json)
                    
                    if "error" not in resources_data:
                        # Convert to ParsedResource objects
                        for resource in resources_data.get("resources", []):
                            parsed_resource = ParsedResource(
                                type=resource.get("type", "unknown"),
                                name=resource.get("name", "unknown"),
                                arn=resource.get("arn") or resource.get("name"),
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
                existing_identifiers = {r.arn for r in context.primary_targets}
                for resource in discovered_resources:
                    if resource.arn not in existing_identifiers:
                        context.primary_targets.append(resource)
            
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to enrich context with traces: {e}")
            return context
    
    
    
    def _create_investigation_prompt(self, context: InvestigationContext) -> str:
        """Create investigation prompt for the lead orchestrator agent"""
        prompt_parts = []
        
        prompt_parts.append("INVESTIGATION REQUEST:")
        
        if context.trace_ids:
            prompt_parts.append(f"X-Ray Trace ID: {context.trace_ids[0]}")
            
            # Add trace data for immediate analysis
            try:
                from ..tools import get_xray_trace
                trace_data = get_xray_trace(context.trace_ids[0])
                if trace_data and "error" not in trace_data:
                    prompt_parts.append(f"\nTRACE DATA FOR ANALYSIS:")
                    prompt_parts.append(f"```json")
                    prompt_parts.append(trace_data)
                    prompt_parts.append(f"```")
            except Exception as e:
                prompt_parts.append(f"\nNote: Could not retrieve trace data: {e}")
        
        if context.error_messages:
            prompt_parts.append(f"Error: {context.error_messages[0]}")
        
        if context.primary_targets:
            targets_text = ", ".join([f"{t.type}:{t.name}" for t in context.primary_targets])
            prompt_parts.append(f"Target Resources: {targets_text}")
            
            # Add specific resource details to prevent hallucination
            for target in context.primary_targets:
                if target.type == "apigateway" and target.arn:
                    # Extract API ID from ARN to prevent hallucination
                    if "restapis/" in target.arn:
                        api_id = target.arn.split("restapis/")[1].split("/")[0]
                        prompt_parts.append(f"  - API Gateway ID: {api_id} (use this exact ID, not 'shp123456')")
                elif target.type == "lambda_function":
                    prompt_parts.append(f"  - Lambda Function: {target.name} (only investigate if explicitly listed)")
        else:
            prompt_parts.append("\n⚠️ CRITICAL: No AWS resources identified.")
            prompt_parts.append("DO NOT assume, infer, or hallucinate resource names.")
            prompt_parts.append("Respond: 'Unable to investigate - no resources found.'\n")
        
        if context.business_context:
            prompt_parts.append(f"Business Context: {context.business_context}")
        
        
        prompt_parts.append("\nTASK:")
        prompt_parts.append("Conduct root cause analysis by FIRST analyzing trace data, THEN using specialist agents.")
        
        prompt_parts.append("\n🔍 CRITICAL TRACE ANALYSIS RULES:")
        prompt_parts.append("1. ALWAYS start by analyzing the X-Ray trace data to understand the error flow")
        prompt_parts.append("2. Look for HTTP status codes, fault/error flags, and response content lengths")
        prompt_parts.append("3. Identify which component actually failed (Lambda 500, API Gateway fault, etc.)")
        prompt_parts.append("4. Focus investigation on the component that shows the actual error")
        prompt_parts.append("5. DO NOT assume configuration issues if the trace shows code errors")
        
        prompt_parts.append("\n🚨 ANTI-HALLUCINATION RULES:")
        prompt_parts.append("1. ONLY investigate resources explicitly listed in 'Target Resources' above")
        prompt_parts.append("2. DO NOT make up, assume, or infer resource names, ARNs, or identifiers")
        prompt_parts.append("3. DO NOT investigate Lambda functions unless explicitly listed in Target Resources")
        prompt_parts.append("4. DO NOT investigate Step Functions unless explicitly listed in Target Resources")
        prompt_parts.append("5. DO NOT use placeholder API IDs like 'shp123456' - use actual IDs from trace data")
        prompt_parts.append("6. Base analysis ONLY on data returned from tools")
        prompt_parts.append("7. If tool returns 'ResourceNotFoundException', report as fact")
        prompt_parts.append("8. If no data available, state 'Insufficient data'")
        prompt_parts.append("9. If you see 'STEPFUNCTIONS' in trace data, it is NOT a Lambda function")
        prompt_parts.append("10. If you see 'promptrca-handler' or similar names, DO NOT investigate unless listed in Target Resources")
        
        prompt_parts.append("\nWORKFLOW:")
        prompt_parts.append("1. FIRST: Analyze X-Ray trace data to identify the actual error source")
        prompt_parts.append("2. SECOND: Call specialist tools for the failing component")
        prompt_parts.append("3. THIRD: Synthesize findings from trace analysis + tool outputs")
        prompt_parts.append("4. FOURTH: Provide recommendations based on actual error evidence")
        
        prompt_parts.append("\nTRACE ANALYSIS PRINCIPLES:")
        prompt_parts.append("- Look for HTTP status codes: 500 = server error, 400 = client error, 200 = success")
        prompt_parts.append("- Check fault/error flags: fault=true indicates a problem, error=true indicates downstream issues")
        prompt_parts.append("- Follow the error flow: if a service calls another service and gets an error, investigate the called service")
        prompt_parts.append("- Check response content_length: > 0 means there's an error response body with details")
        prompt_parts.append("- Look at subsegments: they show the actual service calls and their results")
        
        prompt_parts.append("\nEXAMPLE OF CORRECT BEHAVIOR:")
        prompt_parts.append("- Trace shows Service A calls Service B, Service B returns HTTP 500 → Investigate Service B")
        prompt_parts.append("- Trace shows Service A fault:true + Service B returns 500 → Root cause is Service B, not Service A config")
        prompt_parts.append("- Trace shows HTTP 500 + content_length > 0 → Check the error response body for details")
        
        return "\n".join(prompt_parts)
    
    def _parse_agent_response(self, agent_result, context: InvestigationContext) -> (List[Fact], List[Hypothesis], List[Advice]):
        """Parse specialist responses and extract structured data."""
        response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)
        
        all_facts = []
        all_hypotheses = []
        all_advice = []
        
        # 1. Try to extract JSON from code fences first
        json_blocks = self._extract_json_from_fences(response)
        
        # 2. If no code fences, search for JSON objects with brace balancing
        if not json_blocks:
            json_blocks = self._extract_json_with_brace_balancer(response)
        
        # 3. Parse each JSON block
        for data in json_blocks:
            if not isinstance(data, dict):
                continue
                
            # Parse facts into Fact objects
            for fact_data in data.get('facts', []):
                if isinstance(fact_data, str):
                    all_facts.append(Fact(
                        source='specialist', 
                        content=fact_data, 
                        confidence=0.8,
                        metadata={"parsing_method": "string_fact"}
                    ))
                elif isinstance(fact_data, dict):
                    all_facts.append(Fact(
                        source=fact_data.get('source', 'specialist'),
                        content=fact_data.get('content', ''),
                        confidence=fact_data.get('confidence', 0.8),
                        metadata=fact_data.get('metadata', {})
                    ))
            
            # Parse hypotheses into Hypothesis objects
            for hyp_data in data.get('hypotheses', []):
                if isinstance(hyp_data, dict):
                    all_hypotheses.append(Hypothesis(
                        type=hyp_data.get('type', 'unknown'),
                        description=hyp_data.get('description', ''),
                        confidence=hyp_data.get('confidence', 0.5),
                        evidence=hyp_data.get('evidence', [])
                    ))
            
            # Parse advice into Advice objects
            for advice_data in data.get('advice', []):
                if isinstance(advice_data, dict):
                    all_advice.append(Advice(
                        title=advice_data.get('title', ''),
                        description=advice_data.get('description', ''),
                        priority=advice_data.get('priority', 'medium'),
                        category=advice_data.get('category', 'general')
                    ))
        
        # Fallback: create low-confidence fact only if nothing structured found
        if not all_facts and not all_hypotheses and not all_advice:
            all_facts.append(Fact(
                source="lead_orchestrator",
                content=f"Orchestrator summary: {response[:500]}",
                confidence=0.5,
                metadata={"investigation_type": "multi_agent", "fallback": True}
            ))
        
        
        # Generate additional hypotheses if none provided from specialists
        if not all_hypotheses:
            from .hypothesis_agent import HypothesisAgent
            from strands import Agent
            # Use hypothesis agent specific model
            hypothesis_model = create_hypothesis_agent_model()
            strands_agent = Agent(model=hypothesis_model)
            hypothesis_agent = HypothesisAgent(strands_agent=strands_agent)
            all_hypotheses = hypothesis_agent.generate_hypotheses(all_facts)
        
        # Generate additional advice if none provided from specialists
        if not all_advice and all_hypotheses:
            from .advice_agent import AdviceAgent
            advice_agent = AdviceAgent()
            all_advice = advice_agent.generate_advice(all_facts, all_hypotheses)
        
        return all_facts, all_hypotheses, all_advice
    
    def _extract_json_from_fences(self, response: str) -> List[dict]:
        """Extract and parse JSON from markdown code blocks."""
        import json
        import re
        
        json_blocks = []
        
        # Look for ```json ... ``` blocks
        json_fence_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_fence_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                json_blocks.append(data)
            except json.JSONDecodeError:
                continue
        
        # Also look for ``` ... ``` blocks (without json specifier)
        fence_pattern = r'```\s*\n(.*?)\n```'
        matches = re.findall(fence_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match.strip())
                # Only include if it looks like our expected structure
                if isinstance(data, dict) and any(key in data for key in ['facts', 'hypotheses', 'advice']):
                    json_blocks.append(data)
            except json.JSONDecodeError:
                continue
        
        return json_blocks
    
    def _extract_json_with_brace_balancer(self, response: str) -> List[dict]:
        """Find JSON objects containing facts/hypotheses/advice using brace counting."""
        import json
        import re
        
        json_blocks = []
        
        # Find potential JSON objects by looking for opening braces
        brace_positions = []
        for i, char in enumerate(response):
            if char == '{':
                brace_positions.append(i)
        
        for start_pos in brace_positions:
            # Use brace balancing to find the end of the JSON object
            brace_count = 0
            end_pos = start_pos
            
            for i in range(start_pos, len(response)):
                if response[i] == '{':
                    brace_count += 1
                elif response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i
                        break
            
            if brace_count == 0:  # Found balanced braces
                json_str = response[start_pos:end_pos + 1]
                try:
                    data = json.loads(json_str)
                    # Only include if it has our expected structure
                    if isinstance(data, dict) and any(key in data for key in ['facts', 'hypotheses', 'advice']):
                        json_blocks.append(data)
                except json.JSONDecodeError:
                    continue
        
        return json_blocks
    
    def _create_insufficient_data_report(self, investigation_id: str, reason: str, start_time: Optional[datetime] = None) -> InvestigationReport:
        """Create a report when there's insufficient data to investigate."""
        from ..models.base import InvestigationReport
        
        now = datetime.now(timezone.utc)
        actual_start_time = start_time or now
        
        return InvestigationReport(
            run_id=investigation_id,
            status="insufficient_data",
            started_at=actual_start_time,
            completed_at=now,
            duration_seconds=(now - actual_start_time).total_seconds(),
            affected_resources=[],
            severity_assessment=None,
            facts=[],
            root_cause_analysis=None,
            hypotheses=[],
            advice=[],
            timeline=[],
            summary=json.dumps({
                "investigation_type": "insufficient_data",
                "reason": reason,
                "status": "aborted"
            })
        )
    
    def _generate_investigation_report(self, context: InvestigationContext, facts: List[Fact], hypotheses: List[Hypothesis], advice: List[Advice], region: str, assume_role_arn: Optional[str] = None, external_id: Optional[str] = None) -> InvestigationReport:
        """Generate investigation report from multi-agent findings."""
        logger.info("📋 Generating investigation report...")
        
        now = datetime.now(timezone.utc)
        start_time = context.start_time or now  # Use actual start time from context
        
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
        
        # Create root cause agent for analysis (no AWS client needed - purely analytical)
        from .root_cause_agent import RootCauseAgent
        from strands import Agent
        # Use root cause agent specific model
        root_cause_model = create_root_cause_agent_model()
        root_cause_strands_agent = Agent(model=root_cause_model)
        root_cause_agent = RootCauseAgent(strands_agent=root_cause_strands_agent)
        
        # Use root cause agent to analyze and synthesize findings
        root_cause = root_cause_agent.analyze_root_cause(hypotheses, facts)
        
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
    
    
    
    async def _get_trace_data(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get X-Ray trace data using the xray tool."""
        try:
            import json
            from ..tools import get_xray_trace
            
            # Call the actual X-Ray trace tool
            trace_json = get_xray_trace(trace_id)
            trace_data = json.loads(trace_json)
            
            # Debug: Log the full trace data structure
            logger.info(f"DEBUG: Full trace data for {trace_id}: {json.dumps(trace_data, indent=2)}")
            
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
                "stepfunctions": f"/aws/states/{resource_name}",
                "xray_trace": None,  # X-Ray traces don't have log groups
                "trace": None,  # Alternative name for traces
                "unknown": None  # Skip unknown types
            }
            
            log_group = log_group_map.get(resource_type.lower())
            if not log_group:
                if resource_type.lower() in ["xray_trace", "trace", "unknown"]:
                    logger.info(f"Skipping log extraction for {resource_type} - no log group available")
                    return None
                else:
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
