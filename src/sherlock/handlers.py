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

Shared handler logic for Sherlock investigations.
Used by both the AgentCore server and AWS Lambda deployments.
"""

import os
import asyncio
from typing import Dict, Any, Optional
from strands import Agent

from .core import SherlockInvestigator
from .agents.lead_orchestrator import LeadOrchestratorAgent
from .utils.config import get_region, create_orchestrator_model
from .utils import get_logger

logger = get_logger(__name__)

# Configure orchestrator model - initialized once, reused across invocations
# In Lambda, this happens during cold start and is reused for warm invocations
orchestrator_model = create_orchestrator_model()

agent = Agent(model=orchestrator_model)


def handle_investigation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core investigation handler - shared between server and Lambda.

    Args:
        payload: Investigation request with one of:
            - free_text_input: Natural language description
            - investigation_inputs: Natural language description (new format)
            - function_name: Lambda function name (legacy)
            - investigation_target: Structured target specification
            - assume_role_arn: Optional IAM role ARN to assume for cross-account access

    Returns:
        Investigation report as dictionary
    """
    try:
        # Extract parameters from payload
        region = payload.get("region", get_region())
        assume_role_arn = payload.get("assume_role_arn")
        external_id = payload.get("external_id")
        
        # Debug logging for role assumption
        logger.info(f"🔍 [DEBUG] Extracted assume_role_arn: {assume_role_arn}")
        logger.info(f"🔍 [DEBUG] Extracted external_id: {external_id}")
        logger.info(f"🔍 [DEBUG] Full payload keys: {list(payload.keys())}")

        # Check for free text input (primary method)
        if "free_text_input" in payload:
            return _handle_free_text_investigation(
                payload["free_text_input"],
                region,
                agent,
                assume_role_arn,
                external_id
            )

        # Check for new investigation_inputs format
        if "investigation_inputs" in payload:
            return _handle_investigation_inputs(
                payload["investigation_inputs"],
                region,
                agent,
                assume_role_arn,
                external_id
            )

        # Fallback to legacy structured input
        function_name = payload.get("function_name")
        xray_trace_id = payload.get("xray_trace_id")
        investigation_target = payload.get("investigation_target", {})

        # Initialize investigator
        investigator = SherlockInvestigator(
            region=region,
            xray_trace_id=xray_trace_id,
            investigation_target=investigation_target,
            strands_agent=orchestrator_model
        )

        # Run investigation (async)
        report = asyncio.run(investigator.investigate(function_name=function_name))

        # Convert to structured response
        response = report.to_dict()


        # Add investigation metadata
        response["investigation"]["region"] = region
        response["investigation"]["investigation_target"] = investigation_target
        response["investigation"]["xray_trace_id"] = xray_trace_id

        return response

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _handle_free_text_investigation(
    free_text: str,
    region: str,
    strands_agent: Agent,
    assume_role_arn: Optional[str] = None,
    external_id: Optional[str] = None
) -> Dict[str, Any]:
    """Handle free text investigation using multi-agent orchestration."""
    try:
        from .agents.lead_orchestrator import LeadOrchestratorAgent

        # Initialize lead orchestrator agent
        orchestrator = LeadOrchestratorAgent(strands_agent.model)

        # Prepare input for investigation
        inputs = {
            "free_text_input": free_text
        }

        # Run multi-agent investigation (async)
        report = asyncio.run(orchestrator.investigate(inputs, region, assume_role_arn, external_id))

        # Convert to structured response
        response = report.to_dict()

        # Add investigation metadata
        response["investigation"]["region"] = region
        response["investigation"]["input_type"] = "free_text"
        response["investigation"]["original_input"] = free_text

        return response

    except Exception as e:
        return {
            "success": False,
            "error": f"Multi-agent investigation failed: {str(e)}"
        }


def _handle_investigation_inputs(
    investigation_inputs: str,
    region: str,
    strands_agent: Agent,
    assume_role_arn: Optional[str] = None,
    external_id: Optional[str] = None
) -> Dict[str, Any]:
    """Handle investigation_inputs using multi-agent orchestration."""
    try:
        from .agents.lead_orchestrator import LeadOrchestratorAgent

        # Initialize lead orchestrator agent
        orchestrator = LeadOrchestratorAgent(strands_agent.model)

        # Prepare input for investigation
        inputs = {
            "investigation_inputs": investigation_inputs
        }

        # Run multi-agent investigation (async)
        report = asyncio.run(orchestrator.investigate(inputs, region, assume_role_arn, external_id))

        # Convert to structured response
        response = report.to_dict()

        # Add investigation metadata
        response["investigation"]["region"] = region
        response["investigation"]["input_type"] = "investigation_inputs"
        response["investigation"]["original_input"] = investigation_inputs

        return response

    except Exception as e:
        return {
            "success": False,
            "error": f"Multi-agent investigation failed: {str(e)}"
        }
