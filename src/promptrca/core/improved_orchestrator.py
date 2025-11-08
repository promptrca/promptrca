#!/usr/bin/env python3
"""
Improved Direct Invocation Orchestrator - Deep Analysis with Deterministic Flow

This orchestrator ensures DEEP investigation by:
1. Actually analyzing X-Ray traces (not just mentioning them)
2. Pulling and analyzing execution logs
3. Summarizing raw data before passing to AI
4. Using deterministic Python for orchestration

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

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

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


class ImprovedDirectOrchestrator:
    """
    Deterministic orchestrator that ensures deep investigation.
    
    Key improvements:
    - Actually analyzes X-Ray traces (extracts all segments)
    - Pulls execution logs for each resource
    - Summarizes raw data with AI before analysis
    - Deterministic Python orchestration (no AI routing)
    """

    def __init__(self, region: str = None):
        """Initialize the improved orchestrator."""
        self.region = region or get_region()

        # Initialize input parser
        from ..agents.input_parser_agent import InputParserAgent
        self.input_parser = InputParserAgent()

        logger.info("✨ ImprovedDirectOrchestrator initialized")

    async def investigate(
        self,
        inputs: Dict[str, Any],
        region: str = None,
        assume_role_arn: Optional[str] = None,
        external_id: Optional[str] = None
    ) -> InvestigationReport:
        """
        Run deep investigation with deterministic flow.
        
        Flow:
        1. Parse inputs
        2. Collect ALL raw data (traces, logs, configs, metrics)
        3. Summarize raw data with AI
        4. Extract structured facts
        5. Generate hypotheses
        6. Analyze root cause
        7. Generate report
        """
        region = region or self.region
        investigation_start_time = datetime.now(timezone.utc)

        logger.info("=" * 80)
        logger.info("🚀 IMPROVED INVESTIGATION STARTED (Deep Analysis)")
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
                       f"{len(parsed_inputs.trace_ids)} traces")

            # STEP 2: Collect ALL raw data (deterministic)
            logger.info("📊 Step 2: Collecting raw data (traces, logs, configs)...")
            raw_data = await self._collect_all_raw_data(parsed_inputs, region)
            logger.info(f"   ✓ Collected {len(raw_data)} data sources")

            # STEP 3: Summarize raw data with AI (small model)
            logger.info("🤖 Step 3: Summarizing raw data with AI...")
            summaries = await self._summarize_raw_data(raw_data)
            logger.info(f"   ✓ Generated {len(summaries)} summaries")

            # STEP 4: Extract structured facts
            logger.info("📋 Step 4: Extracting structured facts...")
            facts = self._extract_facts_from_summaries(summaries, raw_data)
            logger.info(f"   ✓ Extracted {len(facts)} facts")

            # STEP 5: Generate hypotheses
            logger.info("🧠 Step 5: Generating hypotheses...")
            hypotheses = self._generate_hypotheses(facts)
            logger.info(f"   ✓ Generated {len(hypotheses)} hypotheses")

            # STEP 6: Analyze root cause
            logger.info("🔬 Step 6: Analyzing root cause...")
            root_cause = self._analyze_root_cause(hypotheses, facts)
            logger.info(f"   ✓ Root cause identified (confidence: {root_cause.confidence_score:.2f})")

            # STEP 7: Generate report
            logger.info("📄 Step 7: Generating report...")
            report = self._generate_report(
                facts, hypotheses, [], root_cause,
                raw_data, investigation_start_time, region
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
        # Use existing input parser
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

    async def _collect_all_raw_data(self, parsed_inputs, region: str) -> List[Dict[str, Any]]:
        """
        Collect ALL raw data deterministically.
        
        This is the KEY improvement - we actually pull and analyze everything.
        """
        raw_data = []

        # 1. X-Ray Traces (DEEP ANALYSIS)
        for trace_id in parsed_inputs.trace_ids:
            logger.info(f"   → Analyzing X-Ray trace {trace_id}...")
            trace_data = await self._analyze_xray_trace_deep(trace_id)
            if trace_data:
                raw_data.append({
                    'type': 'xray_trace',
                    'trace_id': trace_id,
                    'data': trace_data
                })

        # 2. Execution Logs for each resource
        for target in parsed_inputs.primary_targets:
            logger.info(f"   → Collecting logs for {target.type}:{target.name}...")
            logs = await self._collect_execution_logs(target.type, target.name, region)
            if logs:
                raw_data.append({
                    'type': 'execution_logs',
                    'resource_type': target.type,
                    'resource_name': target.name,
                    'data': logs
                })

            # 3. Configuration for each resource
            logger.info(f"   → Getting configuration for {target.type}:{target.name}...")
            config = await self._get_resource_configuration(target.type, target.name)
            if config:
                raw_data.append({
                    'type': 'configuration',
                    'resource_type': target.type,
                    'resource_name': target.name,
                    'data': config
                })

            # 4. Metrics for each resource
            logger.info(f"   → Getting metrics for {target.type}:{target.name}...")
            metrics = await self._get_resource_metrics(target.type, target.name)
            if metrics:
                raw_data.append({
                    'type': 'metrics',
                    'resource_type': target.type,
                    'resource_name': target.name,
                    'data': metrics
                })

        return raw_data

    async def _analyze_xray_trace_deep(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        DEEP X-Ray trace analysis - extract ALL segments and errors.
        
        This is what was missing - we now actually analyze the trace!
        """
        try:
            from ..tools import get_xray_trace
            trace_json = get_xray_trace(trace_id)
            trace_data = json.loads(trace_json)

            if "error" in trace_data:
                return None

            # Extract ALL segments
            segments = []
            if "Traces" in trace_data and len(trace_data["Traces"]) > 0:
                trace = trace_data["Traces"][0]
                for segment_doc in trace.get("Segments", []):
                    segment = json.loads(segment_doc["Document"])
                    segments.append({
                        'name': segment.get('name'),
                        'id': segment.get('id'),
                        'start_time': segment.get('start_time'),
                        'end_time': segment.get('end_time'),
                        'duration': segment.get('end_time', 0) - segment.get('start_time', 0),
                        'http_status': segment.get('http', {}).get('response', {}).get('status'),
                        'fault': segment.get('fault', False),
                        'error': segment.get('error', False),
                        'cause': segment.get('cause'),
                        'subsegments': segment.get('subsegments', [])
                    })

            return {
                'trace_id': trace_id,
                'duration': trace_data["Traces"][0].get('Duration'),
                'segments': segments,
                'total_segments': len(segments),
                'faulted_segments': [s for s in segments if s['fault']],
                'error_segments': [s for s in segments if s['error']]
            }

        except Exception as e:
            logger.error(f"Failed to analyze trace {trace_id}: {e}")
            return None

    async def _collect_execution_logs(self, resource_type: str, resource_name: str, region: str) -> Optional[Dict[str, Any]]:
        """
        Collect execution logs for a resource.
        
        This is critical - we need actual log data, not just config!
        """
        try:
            from ..tools import get_cloudwatch_logs

            log_group_map = {
                'lambda': f'/aws/lambda/{resource_name}',
                'apigateway': f'/aws/apigateway/{resource_name}',
                'stepfunctions': f'/aws/states/{resource_name}'
            }

            log_group = log_group_map.get(resource_type.lower())
            if not log_group:
                return None

            # Get logs from last hour
            logs_json = get_cloudwatch_logs(log_group, hours_back=1, region=region)
            logs_data = json.loads(logs_json)

            if "error" in logs_data:
                return None

            events = logs_data.get("events", [])
            
            # Extract error logs
            error_logs = [e for e in events if any(keyword in e.get('message', '').lower() 
                                                   for keyword in ['error', 'exception', 'failed', 'timeout'])]

            return {
                'log_group': log_group,
                'total_events': len(events),
                'error_events': len(error_logs),
                'sample_errors': error_logs[:10],  # Top 10 errors
                'all_events': events[:50]  # Top 50 events for context
            }

        except Exception as e:
            logger.error(f"Failed to collect logs for {resource_name}: {e}")
            return None

    async def _get_resource_configuration(self, resource_type: str, resource_name: str) -> Optional[Dict[str, Any]]:
        """Get resource configuration."""
        try:
            if resource_type.lower() == 'lambda':
                from ..tools import get_lambda_config
                config_json = get_lambda_config(resource_name)
                return json.loads(config_json)
            elif resource_type.lower() == 'apigateway':
                from ..tools import get_api_gateway_stage_config
                # Extract API ID and stage from resource_name
                parts = resource_name.split('/')
                api_id = parts[0] if parts else resource_name
                stage = parts[1] if len(parts) > 1 else 'prod'
                config_json = get_api_gateway_stage_config(api_id, stage)
                return json.loads(config_json)
            # Add more resource types as needed
            return None
        except Exception as e:
            logger.error(f"Failed to get config for {resource_name}: {e}")
            return None

    async def _get_resource_metrics(self, resource_type: str, resource_name: str) -> Optional[Dict[str, Any]]:
        """Get resource metrics."""
        try:
            if resource_type.lower() == 'lambda':
                from ..tools import get_lambda_metrics
                metrics_json = get_lambda_metrics(resource_name)
                return json.loads(metrics_json)
            elif resource_type.lower() == 'apigateway':
                from ..tools import get_api_gateway_metrics
                parts = resource_name.split('/')
                api_id = parts[0] if parts else resource_name
                stage = parts[1] if len(parts) > 1 else 'prod'
                metrics_json = get_api_gateway_metrics(api_id, stage)
                return json.loads(metrics_json)
            return None
        except Exception as e:
            logger.error(f"Failed to get metrics for {resource_name}: {e}")
            return None

    async def _summarize_raw_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Summarize raw data with AI (small model).
        
        This is KEY - we use AI to extract ONLY relevant info from raw data.
        """
        from strands import Agent
        from ..utils.config import create_hypothesis_agent_model  # Use small model

        summaries = []
        model = create_hypothesis_agent_model()  # Small, fast model
        agent = Agent(model=model)

        for data_source in raw_data:
            try:
                summary = await self._summarize_single_source(agent, data_source)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                logger.error(f"Failed to summarize {data_source['type']}: {e}")

        return summaries

    async def _summarize_single_source(self, agent, data_source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Summarize a single data source."""
        data_type = data_source['type']
        data = data_source['data']

        if data_type == 'xray_trace':
            prompt = f"""Summarize this X-Ray trace in 2-3 sentences. Focus on:
- Which services were called
- HTTP status codes
- Any faults or errors
- Duration/timing issues

Trace data:
{json.dumps(data, indent=2)[:2000]}  # Limit to 2000 chars

Provide a concise summary."""

        elif data_type == 'execution_logs':
            error_logs = data.get('sample_errors', [])
            prompt = f"""Summarize these execution logs in 2-3 sentences. Focus on:
- Error messages
- Exception types
- Patterns in failures

Log data:
Total events: {data.get('total_events')}
Error events: {data.get('error_events')}
Sample errors:
{json.dumps(error_logs[:5], indent=2)[:2000]}

Provide a concise summary of what went wrong."""

        elif data_type == 'configuration':
            prompt = f"""Summarize this resource configuration in 1-2 sentences. Focus on:
- Key settings (timeout, memory, etc.)
- Potential misconfigurations

Config:
{json.dumps(data, indent=2)[:1000]}

Provide a concise summary."""

        elif data_type == 'metrics':
            prompt = f"""Summarize these metrics in 1-2 sentences. Focus on:
- Error rates
- Unusual patterns
- Threshold violations

Metrics:
{json.dumps(data, indent=2)[:1000]}

Provide a concise summary."""

        else:
            return None

        # Run summarization
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent, prompt)
        summary_text = str(result.content) if hasattr(result, 'content') else str(result)

        return {
            'type': data_type,
            'source': data_source,
            'summary': summary_text.strip()
        }

    def _extract_facts_from_summaries(self, summaries: List[Dict[str, Any]], raw_data: List[Dict[str, Any]]) -> List[Fact]:
        """Extract structured facts from summaries."""
        facts = []

        for summary in summaries:
            fact = Fact(
                source=summary['type'],
                content=summary['summary'],
                confidence=0.9,  # High confidence - from actual data
                metadata={
                    'data_type': summary['type'],
                    'raw_data_available': True
                }
            )
            facts.append(fact)

        return facts

    def _generate_hypotheses(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses from facts."""
        from ..agents.hypothesis_agent import HypothesisAgent
        from strands import Agent
        from ..utils.config import create_hypothesis_agent_model

        model = create_hypothesis_agent_model()
        strands_agent = Agent(model=model)
        agent = HypothesisAgent(strands_agent=strands_agent)

        return agent.generate_hypotheses(facts)

    def _analyze_root_cause(self, hypotheses: List[Hypothesis], facts: List[Fact]) -> RootCauseAnalysis:
        """Analyze root cause."""
        from ..agents.root_cause_agent import RootCauseAgent
        from strands import Agent
        from ..utils.config import create_root_cause_agent_model

        model = create_root_cause_agent_model()
        strands_agent = Agent(model=model)
        agent = RootCauseAgent(strands_agent=strands_agent)

        return agent.analyze_root_cause(hypotheses, facts)

    def _generate_report(self, facts, hypotheses, advice, root_cause, raw_data, start_time, region) -> InvestigationReport:
        """Generate investigation report."""
        now = datetime.now(timezone.utc)

        # Build affected resources from raw data
        affected_resources = []
        for data in raw_data:
            if 'resource_name' in data:
                affected_resources.append(AffectedResource(
                    resource_type=data.get('resource_type', 'unknown'),
                    resource_id=data.get('resource_name'),
                    resource_name=data.get('resource_name'),
                    health_status='unknown',
                    detected_issues=[],
                    metadata={'region': region}
                ))

        # Deduplicate
        unique_resources = {r.resource_id: r for r in affected_resources}
        affected_resources = list(unique_resources.values())

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
                component="improved_orchestrator",
                description="Deep investigation started",
                metadata={"orchestration_type": "improved_deterministic"}
            ),
            EventTimeline(
                timestamp=now,
                event_type="investigation_complete",
                component="improved_orchestrator",
                description="Investigation completed",
                metadata={"orchestration_type": "improved_deterministic"}
            )
        ]

        summary = {
            "investigation_type": "improved_direct",
            "orchestration": "deterministic_deep_analysis",
            "data_sources_collected": len(raw_data),
            "facts": len(facts),
            "hypotheses": len(hypotheses),
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
