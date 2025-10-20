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

Contact: christiangenn99+promptrca@gmail.com

Main PromptRCA Investigator class
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import json

from ..models import InvestigationReport, InvestigationTarget, Fact, Hypothesis, Advice, SeverityAssessment, RootCauseAnalysis
from ..clients import AWSClient
from ..core.direct_orchestrator import DirectInvocationOrchestrator
from ..core.swarm_orchestrator import SwarmOrchestrator
from ..utils.config import get_region
from ..utils import get_logger
import os

logger = get_logger(__name__)


class PromptRCAInvestigator:
    """
    Main PromptRCA AI investigator class.

    Supports multiple orchestration patterns:
    - Direct Invocation (code-based, default)
    - Swarm (Strands best practices)
    """

    def __init__(self, region: str = None,
                 xray_trace_id: str = None, investigation_target: Dict[str, Any] = None, strands_agent=None,
                 assume_role_arn: str = None, external_id: str = None, orchestrator_type: str = None):
        """Initialize the investigator."""
        self.region = region or get_region()
        self.run_id = str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.xray_trace_id = xray_trace_id
        self.investigation_target = InvestigationTarget(**investigation_target) if investigation_target else None
        self.assume_role_arn = assume_role_arn
        self.external_id = external_id

        # Initialize AWS client with optional role assumption
        self.aws_client = AWSClient(
            region=self.region,
            role_arn=assume_role_arn,
            external_id=external_id
        )

        # Select orchestrator type
        self.orchestrator_type = orchestrator_type or os.getenv('PROMPTRCA_ORCHESTRATOR', 'direct')
        
        if self.orchestrator_type == 'swarm':
            logger.info(f"🤖 Initializing with SWARM ORCHESTRATION (Strands best practices)")
            self.orchestrator = SwarmOrchestrator(region=self.region)
        else:
            logger.info(f"🚀 Initializing with DIRECT ORCHESTRATION (code-based)")
            self.orchestrator = DirectInvocationOrchestrator(region=self.region)
            self.orchestrator_type = "direct_invocation"

        # Log initialization metadata
        logger.info(f"Investigation ID: {self.run_id}")
        logger.info(f"Orchestrator Type: {self.orchestrator_type}")
    
    async def investigate(self, function_name: Optional[str] = None) -> InvestigationReport:
        """Run a PromptRCA investigation using Direct Invocation orchestration only."""
        investigation_start = datetime.now(timezone.utc)

        try:
            logger.info("=" * 80)
            logger.info(f"INVESTIGATION STARTED: {self.run_id}")
            logger.info(f"Orchestrator: {self.orchestrator_type}")
            logger.info("=" * 80)

            # Build investigation inputs in the format expected by both orchestrators
            inputs = {}

            # Add trace ID if available
            if self.xray_trace_id:
                inputs['xray_trace_id'] = self.xray_trace_id

            # Add function name if available
            if function_name:
                inputs['function_name'] = function_name

            # Add investigation target if available
            if self.investigation_target:
                inputs['investigation_target'] = {
                    "type": self.investigation_target.type,
                    "name": self.investigation_target.name,
                    "region": self.region,
                    "metadata": self.investigation_target.to_dict()
                }

            # Run investigation through orchestrator with role assumption
            report = await self.orchestrator.investigate(
                inputs,
                region=self.region,
                assume_role_arn=self.assume_role_arn,
                external_id=self.external_id
            )

            # Add orchestrator type to report metadata
            investigation_end = datetime.now(timezone.utc)
            duration = (investigation_end - investigation_start).total_seconds()

            logger.info("=" * 80)
            logger.info(f"INVESTIGATION COMPLETED: {self.run_id}")
            logger.info(f"Orchestrator: {self.orchestrator_type}")
            logger.info(f"Duration: {duration:.2f}s")
            logger.info(f"Facts: {len(report.facts)}, Hypotheses: {len(report.hypotheses)}")
            logger.info(f"Root Cause Confidence: {report.root_cause_analysis.confidence_score if report.root_cause_analysis else 0:.2f}")
            logger.info("=" * 80)

            # Add orchestrator metadata to summary
            self._add_orchestrator_metadata(report)

            return report

        except Exception as e:
            logger.error(f"❌ Investigation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.generate_error_report(str(e))

    def _add_orchestrator_metadata(self, report: InvestigationReport):
        """Add orchestrator type to report for A/B comparison metrics."""
        try:
            # Parse existing summary
            if isinstance(report.summary, str):
                if report.summary.startswith('{'):
                    summary = json.loads(report.summary)
                else:
                    summary = {"summary_text": report.summary}
            else:
                summary = report.summary

            # Add orchestrator metadata
            summary["orchestrator_type"] = self.orchestrator_type
            summary["investigation_id"] = self.run_id

            # Update report
            report.summary = json.dumps(summary)

        except Exception as e:
            logger.warning(f"Failed to add orchestrator metadata: {e}")
    
    def gather_facts(self, function_name: Optional[str]) -> List[Fact]:
        """Gather facts from various sources."""
        facts = []
        
        # X-Ray investigation if trace ID provided
        if self.xray_trace_id:
            facts.extend(self.aws_client.get_xray_trace(self.xray_trace_id))
        
        # Gather facts based on investigation target type
        if self.investigation_target and self.investigation_target.type == 'lambda' and function_name:
            # Lambda-specific fact gathering
            facts.extend(self.aws_client.get_cloudwatch_logs(function_name))
            facts.extend(self.aws_client.get_lambda_function_info(function_name))
            facts.extend(self.aws_client.get_cloudwatch_metrics(function_name))
        elif self.investigation_target and self.investigation_target.type == 'stepfunctions':
            # Step Functions-specific fact gathering
            state_machine_name = self.investigation_target.name
            facts.extend(self.aws_client.get_step_function_info(state_machine_name))
            facts.extend(self.aws_client.get_cloudwatch_metrics(state_machine_name))
        elif function_name:
            # Fallback to Lambda if function_name is provided
            facts.extend(self.aws_client.get_cloudwatch_logs(function_name))
            facts.extend(self.aws_client.get_lambda_function_info(function_name))
            facts.extend(self.aws_client.get_cloudwatch_metrics(function_name))
        
        return facts
    
    def generate_report(self, facts: List[Fact], hypotheses: List[Hypothesis], advice: List[Advice]) -> InvestigationReport:
        """Generate a final report."""
        duration_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        
        summary = {
            "total_facts": len(facts),
            "total_hypotheses": len(hypotheses),
            "total_advice": len(advice),
            "investigation_success": True if facts else False
        }
        
        return InvestigationReport(
            run_id=self.run_id,
            status="completed",
            started_at=self.start_time,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration_seconds,
            facts=facts,
            hypotheses=hypotheses,
            advice=advice,
            summary=json.dumps(summary),
        )
    
    def generate_error_report(self, error_message: str) -> InvestigationReport:
        """Generate an error report."""
        duration_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return InvestigationReport(
            run_id=self.run_id,
            status="failed",
            started_at=self.start_time,
            completed_at=datetime.now(timezone.utc),
            duration_seconds=duration_seconds,
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
                analysis_summary="Investigation failed"
            ),
            hypotheses=[],
            advice=[],
            timeline=[],
            summary=json.dumps({"error": error_message, "investigation_success": False}),
        )
