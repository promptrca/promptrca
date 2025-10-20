#!/usr/bin/env python3
"""
Focused Direct Orchestrator - Prioritizes Core Investigation

This orchestrator focuses on the ESSENTIAL investigation steps:
1. Parse inputs
2. Analyze X-Ray traces (DEEP)
3. Get resource configs and logs
4. Generate hypotheses
5. Analyze root cause

It skips optional tools (AWS Health, CloudTrail) that may fail due to permissions.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

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

logger = get_logger(__name__)


class FocusedDirectOrchestrator:
    """
    Focused orchestrator that prioritizes core investigation over optional tools.
    
    Key principles:
    - Skip optional tools that may fail (AWS Health, CloudTrail)
    - Focus on essential data (X-Ray traces, logs, configs)
    - Ensure investigation completes even with permission issues
    """

    def __init__(self, region: str = None):
        """Initialize the focused orchestrator."""
        self.region = region or get_region()

        # Initialize input parser
        from ..agents.input_parser_agent import InputParserAgent
        self.input_parser = InputParserAgent()

        logger.info("✨ FocusedDirectOrchestrator initialized (core investigation only)")

    async def investigate(
        self,
        inputs: Dict[str, Any],
        region: str = None,
        assume_role_arn: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> InvestigationReport:
        """
        Run focused investigation prioritizing core analysis.
        """
        region = region or self.region
        investigation_start_time = datetime.now(timezone.utc)

        logger.info("=" * 80)
        logger.info("🎯 FOCUSED INVESTIGATION STARTED (Core Analysis Priority)")
        logger.info("=" * 80)

        try:
            # Setup AWS client
            aws_client = AWSClient(
                region=region,
                role_arn=assume_role_arn,
                external_id=external_id
            )
            set_aws_client(aws_client)

            # STEP 1: Parse inputs
            logger.info("📝 Step 1: Parsing inputs...")
            parsed_inputs = self._parse_inputs(inputs, region)
            logger.info(f"   ✓ Parsed {len(parsed_inputs.primary_targets)} targets, "
                       f"{len(parsed_inputs.trace_ids)} trace IDs")

            # STEP 2: Discover resources from traces
            logger.info("🔍 Step 2: Discovering resources from traces...")
            resources = await self._discover_resources(parsed_inputs)
            logger.info(f"   ✓ Discovered {len(resources)} resources")

            # STEP 3: Core evidence collection (skip optional tools)
            logger.info("🧾 Step 3: Collecting core evidence...")
            facts = await self._collect_core_evidence(resources, parsed_inputs)
            logger.info(f"   ✓ Collected {len(facts)} facts")

            # STEP 4: Generate hypotheses
            logger.info("🧠 Step 4: Generating hypotheses...")
            hypotheses = self._run_hypothesis_agent(facts)
            logger.info(f"   ✓ Generated {len(hypotheses)} hypotheses")

            # STEP 5: Root cause analysis
            logger.info("🔬 Step 5: Analyzing root cause...")
            root_cause = self._analyze_root_cause(hypotheses, facts)
            logger.info(f"   ✓ Root cause identified (confidence: {root_cause.confidence_score:.2f})")

            # STEP 6: Generate report
            logger.info("📄 Step 6: Generating investigation report...")
            report = self._generate_report(
                facts, hypotheses, [], root_cause,
                resources, investigation_start_time, region
            )

            duration = (datetime.now(timezone.utc) - investigation_start_time).total_seconds()
            logger.info("=" * 80)
            logger.info(f"✅ INVESTIGATION COMPLETE in {duration:.2f}s")
            logger.info("=" * 80)

            return report

        except Exception as e:
            logger.error(f"❌ Investigation failed: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._generate_error_report(str(e), investigation_start_time)

        finally:
            clear_aws_client()

    def _parse_inputs(self, inputs: Dict[str, Any], region: str):
        """Parse investigation inputs."""
        if 'free_text_input' in inputs:
            return self.input_parser.parse_inputs(inputs['free_text_input'], region)
        elif 'investigation_inputs' in inputs:
            return self.input_parser.parse_inputs(inputs['investigation_inputs'], region)
        else:
            # Build structured input from legacy format
            structured = {}
            if 'xray_trace_id' in inputs:
                structured['trace_ids'] = [inputs['xray_trace_id']]
            if 'function_name' in inputs:
                structured['primary_targets'] = [{"type": "lambda", "name": inputs['function_name'], "region": region}]
            return self.input_parser.parse_inputs(structured, region)

    async def _discover_resources(self, parsed_inputs) -> List[Dict[str, Any]]:
        """Discover AWS resources from traces and explicit targets."""
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
                    logger.info(f"   → Extracting resources from trace {trace_id}...")
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
                            logger.info(f"     ✓ Found {resource.get('type')}: {resource.get('name')}")
                    else:
                        logger.warning(f"Failed to extract resources from trace {trace_id}: {trace_resources.get('error')}")
                except Exception as e:
                    logger.warning(f"Failed to extract resources from trace {trace_id}: {e}")

        # Deduplicate resources
        unique_resources = {}
        for resource in resources:
            key = resource.get('arn') or resource.get('name')
            if key and key not in unique_resources:
                unique_resources[key] = resource

        return list(unique_resources.values())

    async def _collect_core_evidence(self, resources: List[Dict[str, Any]], parsed_inputs) -> List[Fact]:
        """
        Collect CORE evidence only - skip optional tools that may fail.
        
        Focus on:
        1. X-Ray trace analysis (DEEP)
        2. Resource configurations
        3. CloudWatch logs
        4. Metrics
        """
        facts: List[Fact] = []

        # CORE 1: Deep X-Ray trace analysis
        logger.info("   → Analyzing X-Ray traces...")
        for trace_id in parsed_inputs.trace_ids:
            trace_facts = await self._analyze_xray_trace_deep(trace_id)
            facts.extend(trace_facts)

        # CORE 2: Resource configurations and logs
        logger.info("   → Collecting resource data...")
        resource_tasks = []
        for resource in resources:
            resource_tasks.append(self._collect_resource_data(resource))

        if resource_tasks:
            resource_results = await asyncio.gather(*resource_tasks, return_exceptions=True)
            for result in resource_results:
                if isinstance(result, list):
                    facts.extend(result)

        # Cap facts globally
        MAX_FACTS = 50
        return facts[:MAX_FACTS]

    async def _analyze_xray_trace_deep(self, trace_id: str) -> List[Fact]:
        """Deep X-Ray trace analysis - extract ALL meaningful information."""
        facts = []
        
        try:
            from ..tools import get_xray_trace
            logger.info(f"     → Getting trace data for {trace_id}...")
            
            trace_json = get_xray_trace(trace_id)
            trace_data = json.loads(trace_json)

            if "error" in trace_data:
                facts.append(Fact(
                    source='xray_trace',
                    content=f"Failed to retrieve trace {trace_id}: {trace_data['error']}",
                    confidence=0.9,
                    metadata={'trace_id': trace_id, 'error': True}
                ))
                return facts

            # Extract trace summary
            if "Traces" in trace_data and len(trace_data["Traces"]) > 0:
                trace = trace_data["Traces"][0]
                duration = trace.get('Duration', 0)
                
                facts.append(Fact(
                    source='xray_trace',
                    content=f"Trace {trace_id} duration: {duration:.3f}s",
                    confidence=0.9,
                    metadata={'trace_id': trace_id, 'duration': duration}
                ))

                # Analyze segments for errors
                segments = trace.get("Segments", [])
                error_segments = []
                fault_segments = []
                
                for segment_doc in segments:
                    try:
                        segment = json.loads(segment_doc["Document"])
                        segment_name = segment.get('name', 'unknown')
                        
                        # Check for faults
                        if segment.get('fault'):
                            fault_segments.append(segment_name)
                            
                        # Check for errors
                        if segment.get('error'):
                            error_segments.append(segment_name)
                            
                        # Check HTTP status
                        http_status = segment.get('http', {}).get('response', {}).get('status')
                        if http_status and http_status >= 400:
                            facts.append(Fact(
                                source='xray_trace',
                                content=f"Service {segment_name} returned HTTP {http_status}",
                                confidence=0.95,
                                metadata={'trace_id': trace_id, 'service': segment_name, 'http_status': http_status}
                            ))
                        
                        # Check for cause/exception
                        if segment.get('cause'):
                            cause = segment.get('cause', {})
                            exception_id = cause.get('id')
                            message = cause.get('message', 'Unknown error')
                            facts.append(Fact(
                                source='xray_trace',
                                content=f"Service {segment_name} error: {message}",
                                confidence=0.95,
                                metadata={'trace_id': trace_id, 'service': segment_name, 'exception_id': exception_id}
                            ))
                            
                    except Exception as e:
                        logger.debug(f"Failed to parse segment: {e}")

                # Summary facts
                if fault_segments:
                    facts.append(Fact(
                        source='xray_trace',
                        content=f"Faulted services in trace: {', '.join(fault_segments)}",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'faulted_services': fault_segments}
                    ))
                
                if error_segments:
                    facts.append(Fact(
                        source='xray_trace',
                        content=f"Services with errors in trace: {', '.join(error_segments)}",
                        confidence=0.95,
                        metadata={'trace_id': trace_id, 'error_services': error_segments}
                    ))

        except Exception as e:
            logger.error(f"Failed to analyze trace {trace_id}: {e}")
            facts.append(Fact(
                source='xray_trace',
                content=f"Trace analysis failed for {trace_id}: {str(e)}",
                confidence=0.8,
                metadata={'trace_id': trace_id, 'error': True}
            ))

        return facts

    async def _collect_resource_data(self, resource: Dict[str, Any]) -> List[Fact]:
        """Collect data for a specific resource."""
        facts = []
        resource_type = resource.get('type', '').lower()
        resource_name = resource.get('name')

        if not resource_name:
            return facts

        try:
            # Lambda resources
            if resource_type == 'lambda':
                facts.extend(await self._collect_lambda_data(resource_name))
            
            # API Gateway resources
            elif resource_type == 'apigateway':
                facts.extend(await self._collect_apigateway_data(resource_name))
            
            # Step Functions resources
            elif resource_type == 'stepfunctions':
                facts.extend(await self._collect_stepfunctions_data(resource_name))

        except Exception as e:
            logger.error(f"Failed to collect data for {resource_type}:{resource_name}: {e}")
            facts.append(Fact(
                source=f'{resource_type}_data',
                content=f"Failed to collect data for {resource_name}: {str(e)}",
                confidence=0.7,
                metadata={'resource_type': resource_type, 'resource_name': resource_name, 'error': True}
            ))

        return facts

    async def _collect_lambda_data(self, function_name: str) -> List[Fact]:
        """Collect Lambda function data."""
        facts = []
        
        try:
            # Get configuration
            from ..tools.lambda_tools import get_lambda_config
            config_json = get_lambda_config(function_name)
            config = json.loads(config_json)
            
            if 'error' not in config:
                timeout = config.get('timeout', 0)
                memory = config.get('memory_size', 0)
                runtime = config.get('runtime', 'unknown')
                
                facts.append(Fact(
                    source='lambda_config',
                    content=f"Lambda {function_name}: timeout={timeout}s, memory={memory}MB, runtime={runtime}",
                    confidence=0.9,
                    metadata={'function_name': function_name, 'timeout': timeout, 'memory': memory, 'runtime': runtime}
                ))

            # Get recent failed invocations
            from ..tools.lambda_tools import get_lambda_failed_invocations
            failures_json = get_lambda_failed_invocations(function_name, hours_back=24, limit=10)
            failures = json.loads(failures_json)
            
            if 'error' not in failures:
                failure_count = failures.get('failure_count', 0)
                if failure_count > 0:
                    facts.append(Fact(
                        source='lambda_logs',
                        content=f"Lambda {function_name} had {failure_count} failed invocations in last 24h",
                        confidence=0.9,
                        metadata={'function_name': function_name, 'failure_count': failure_count}
                    ))
                    
                    # Extract error patterns
                    failed_invocations = failures.get('failed_invocations', [])
                    for invocation in failed_invocations[:3]:  # Top 3 errors
                        error_msg = invocation.get('error_message', 'Unknown error')
                        facts.append(Fact(
                            source='lambda_logs',
                            content=f"Lambda {function_name} error: {error_msg}",
                            confidence=0.85,
                            metadata={'function_name': function_name, 'error_message': error_msg}
                        ))

        except Exception as e:
            logger.debug(f"Failed to collect Lambda data for {function_name}: {e}")

        return facts

    async def _collect_apigateway_data(self, api_name: str) -> List[Fact]:
        """Collect API Gateway data."""
        facts = []
        
        try:
            # Extract API ID and stage from name
            parts = api_name.split('/')
            api_id = parts[0] if parts else api_name
            stage = parts[1] if len(parts) > 1 else 'prod'
            
            # Get stage configuration
            from ..tools.apigateway_tools import get_api_gateway_stage_config
            config_json = get_api_gateway_stage_config(api_id, stage)
            config = json.loads(config_json)
            
            if 'error' not in config:
                xray_enabled = config.get('xray_tracing_enabled', False)
                facts.append(Fact(
                    source='apigateway_config',
                    content=f"API Gateway {api_id}/{stage}: X-Ray tracing={'enabled' if xray_enabled else 'disabled'}",
                    confidence=0.9,
                    metadata={'api_id': api_id, 'stage': stage, 'xray_enabled': xray_enabled}
                ))

        except Exception as e:
            logger.debug(f"Failed to collect API Gateway data for {api_name}: {e}")

        return facts

    async def _collect_stepfunctions_data(self, state_machine_name: str) -> List[Fact]:
        """Collect Step Functions data."""
        facts = []
        
        try:
            # Get state machine definition
            from ..tools.stepfunctions_tools import get_stepfunctions_definition
            definition_json = get_stepfunctions_definition(state_machine_name)
            definition = json.loads(definition_json)
            
            if 'error' not in definition:
                status = definition.get('status', 'unknown')
                facts.append(Fact(
                    source='stepfunctions_config',
                    content=f"Step Functions {state_machine_name}: status={status}",
                    confidence=0.9,
                    metadata={'state_machine': state_machine_name, 'status': status}
                ))

        except Exception as e:
            logger.debug(f"Failed to collect Step Functions data for {state_machine_name}: {e}")

        return facts

    def _run_hypothesis_agent(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses from facts."""
        from ..agents.hypothesis_agent import HypothesisAgent
        from strands import Agent
        
        model = create_hypothesis_agent_model()
        strands_agent = Agent(model=model)
        agent = HypothesisAgent(strands_agent=strands_agent)
        
        return agent.generate_hypotheses(facts)

    def _analyze_root_cause(self, hypotheses: List[Hypothesis], facts: List[Fact]) -> RootCauseAnalysis:
        """Analyze root cause from hypotheses."""
        from ..agents.root_cause_agent import RootCauseAgent
        from strands import Agent
        
        model = create_root_cause_agent_model()
        strands_agent = Agent(model=model)
        agent = RootCauseAgent(strands_agent=strands_agent)
        
        return agent.analyze_root_cause(hypotheses, facts)

    def _generate_report(self, facts, hypotheses, advice, root_cause, resources, start_time, region) -> InvestigationReport:
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

        severity = SeverityAssessment(
            severity="medium",
            impact_scope="service",
            affected_resource_count=len(affected_resources),
            user_impact="moderate",
            confidence=root_cause.confidence_score,
            reasoning=root_cause.analysis_summary
        )

        timeline = [
            EventTimeline(
                timestamp=start_time,
                event_type="investigation_start",
                component="focused_orchestrator",
                description="Focused investigation started",
                metadata={"orchestration_type": "focused_core_analysis"}
            ),
            EventTimeline(
                timestamp=now,
                event_type="investigation_complete",
                component="focused_orchestrator",
                description="Investigation completed",
                metadata={"orchestration_type": "focused_core_analysis"}
            )
        ]

        summary = {
            "investigation_type": "focused_direct",
            "orchestration": "core_analysis_priority",
            "resources_investigated": len(resources),
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
                analysis_summary=f"Investigation failed: {error}"
            ),
            hypotheses=[],
            advice=[],
            timeline=[],
            summary=json.dumps({"error": error, "investigation_success": False})
        )