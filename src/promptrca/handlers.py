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

Shared handler logic for PromptRCA investigations.
Used by both the AgentCore server and AWS Lambda deployments.
"""

import os
import asyncio
from typing import Dict, Any, Optional
from strands import Agent

from .core import PromptRCAInvestigator
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
            print(f"🔍 Debug: Taking free_text_input path")
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
        print(f"🔍 Debug: Taking legacy path")
        function_name = payload.get("function_name")
        xray_trace_id = payload.get("xray_trace_id")
        investigation_target = payload.get("investigation_target", {})

        # Initialize investigator
        orchestrator_env = os.getenv('PROMPTRCA_ORCHESTRATOR', 'direct')
        print(f"🔧 DEBUG: Environment PROMPTRCA_ORCHESTRATOR: {orchestrator_env}")
        
        investigator = PromptRCAInvestigator(
            region=region,
            xray_trace_id=xray_trace_id,
            investigation_target=investigation_target,
            strands_agent=orchestrator_model
        )
        
        print(f"🎯 DEBUG: Investigator created with orchestrator: {investigator.orchestrator_type}")

        # Run investigation (async)
        report = asyncio.run(investigator.investigate(function_name=function_name))
        
        # Debug: Check what type of object we received
        print(f"🔍 Debug: Legacy handler received report type: {type(report)}")
        print(f"🔍 Debug: Legacy handler report has to_dict: {hasattr(report, 'to_dict')}")
        print(f"🔍 Debug: Legacy handler report is dict: {isinstance(report, dict)}")

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
    """Handle free text investigation using Swarm orchestration."""
    print(f"🔍 Debug: _handle_free_text_investigation called with free_text: {free_text}")
    
    # Use Strands built-in tracing for the entire investigation
    from strands.telemetry.tracer import get_tracer
    strands_tracer = get_tracer()
    
    # Create task description for tracing
    task_description = f"AWS Infrastructure Investigation: {free_text}"
    
    # Start Strands multiagent span for the entire investigation
    investigation_span = strands_tracer.start_multiagent_span(
        task=task_description,
        instance="promptrca_investigation"
    )
    
    try:
        print(f"🔍 Debug: Starting SwarmOrchestrator import")
        from .core.swarm_orchestrator import SwarmOrchestrator

        # Initialize Swarm orchestrator
        orchestrator = SwarmOrchestrator(region=region)

        # Prepare input for investigation
        inputs = {
            "free_text_input": free_text
        }

        # Run Swarm investigation (async) - this will run within the trace context
        report = asyncio.run(orchestrator.investigate(inputs, region, assume_role_arn, external_id))
        
        # Debug: Check what type of object we received
        print(f"🔍 Debug: Handler received report type: {type(report)}")
        print(f"🔍 Debug: Handler report has to_dict: {hasattr(report, 'to_dict')}")
        print(f"🔍 Debug: Handler report is dict: {isinstance(report, dict)}")

        # Convert to structured response
        response = report.to_dict()

        # Add investigation metadata
        response["investigation"]["region"] = region
        response["investigation"]["input_type"] = "free_text"
        response["investigation"]["original_input"] = free_text

        # End the span with successful result
        result_summary = f"Investigation completed successfully. Found {len(report.facts)} facts and {len(report.hypotheses)} hypotheses."
        strands_tracer.end_swarm_span(investigation_span, result=result_summary)

        return response

    except Exception as e:
        print(f"🔍 Debug: Exception in _handle_free_text_investigation: {str(e)}")
        import traceback
        print(f"🔍 Debug: Traceback: {traceback.format_exc()}")
        
        # End the span with error
        strands_tracer.end_span_with_error(investigation_span, f"Investigation failed: {str(e)}", e)
        
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
    """Handle investigation_inputs using Swarm orchestration."""
    # Use Strands built-in tracing for the entire investigation
    from strands.telemetry.tracer import get_tracer
    strands_tracer = get_tracer()
    
    # Create task description for tracing
    task_description = f"AWS Infrastructure Investigation: {investigation_inputs}"
    
    # Start Strands multiagent span for the entire investigation
    investigation_span = strands_tracer.start_multiagent_span(
        task=task_description,
        instance="promptrca_investigation"
    )
    
    try:
        from .core.swarm_orchestrator import SwarmOrchestrator

        # Initialize Swarm orchestrator
        orchestrator = SwarmOrchestrator(region=region)

        # Prepare input for investigation
        inputs = {
            "investigation_inputs": investigation_inputs
        }

        # Run Swarm investigation (async) - this will run within the trace context
        report = asyncio.run(orchestrator.investigate(inputs, region, assume_role_arn, external_id))
        
        # Debug: Check what type of object we received
        print(f"🔍 Debug: Handler received report type: {type(report)}")
        print(f"🔍 Debug: Handler report has to_dict: {hasattr(report, 'to_dict')}")
        print(f"🔍 Debug: Handler report is dict: {isinstance(report, dict)}")

        # Convert to structured response
        response = report.to_dict()

        # Add investigation metadata
        response["investigation"]["region"] = region
        response["investigation"]["input_type"] = "investigation_inputs"
        response["investigation"]["original_input"] = investigation_inputs

        # End the span with successful result
        result_summary = f"Investigation completed successfully. Found {len(report.facts)} facts and {len(report.hypotheses)} hypotheses."
        strands_tracer.end_swarm_span(investigation_span, result=result_summary)

        return response

    except Exception as e:
        # End the span with error
        strands_tracer.end_span_with_error(investigation_span, f"Investigation failed: {str(e)}", e)
        
        return {
            "success": False,
            "error": f"Multi-agent investigation failed: {str(e)}"
        }
