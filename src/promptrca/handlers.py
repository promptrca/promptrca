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

Shared handler logic for PromptRCA investigations.
Used by both the HTTP server and AWS Lambda deployments.
"""

import os
import asyncio
import re
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


async def handle_investigation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Core investigation handler - shared between server and Lambda.

    Args:
        payload: Investigation request in structured format:
            {
                "investigation": {
                    "input": "Free text description",
                    "xray_trace_id": "1-...",  # optional, defaults to empty string
                    "region": "eu-west-1"  # optional, uses service_config.region if not provided
                },
                "service_config": {
                    "role_arn": "arn:aws:iam::...",  # optional
                    "external_id": "...",  # optional
                    "region": "eu-west-1"  # tenant default region
                }
            }

    Returns:
        Investigation report as dictionary
    """
    try:
        # Validate structured format
        if "investigation" not in payload:
            return {
                "success": False,
                "error": "Missing required 'investigation' key in payload"
            }
        
        investigation = payload.get("investigation", {})
        service_config = payload.get("service_config", {})
        
        # Extract investigation data
        free_text_input = investigation.get("input", "")
        xray_trace_id = investigation.get("xray_trace_id", "")
        investigation_region = investigation.get("region")
        
        # Extract service configuration
        assume_role_arn = service_config.get("role_arn")
        external_id = service_config.get("external_id")
        service_region = service_config.get("region")
        
        # Determine region: investigation.region takes precedence over service_config.region
        region = investigation_region or service_region or get_region()
        
        # Extract trace IDs from free text input (for better logging)
        trace_id_pattern = r'(?:Root=)?(1-[a-f0-9]{8}-[a-f0-9]{24})'
        extracted_trace_ids = re.findall(trace_id_pattern, free_text_input)
        
        # Debug logging
        logger.info(f"🔍 [DEBUG] Investigation input: {free_text_input[:100]}...")
        logger.info(f"🔍 [DEBUG] Region: {region}")
        logger.info(f"🔍 [DEBUG] X-Ray trace ID (explicit): {xray_trace_id or '(none)'}")
        logger.info(f"🔍 [DEBUG] X-Ray trace ID (extracted from text): {', '.join(extracted_trace_ids) if extracted_trace_ids else '(none)'}")
        logger.info(f"🔍 [DEBUG] Assume role ARN: {assume_role_arn or '(none)'}")
        logger.info(f"🔍 [DEBUG] External ID: {external_id or '(none)'}")
        
        # Validate required fields
        if not free_text_input:
            return {
                "success": False,
                "error": "Missing required 'investigation.input' field"
            }
        
        # Handle free text investigation
        return await _handle_free_text_investigation(
            free_text_input,
            region,
            agent,
            assume_role_arn,
            external_id,
            xray_trace_id
        )

    except Exception as e:
        logger.error(f"Error in handle_investigation: {str(e)}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def _handle_free_text_investigation(
    free_text: str,
    region: str,
    strands_agent: Agent,
    assume_role_arn: Optional[str] = None,
    external_id: Optional[str] = None,
    xray_trace_id: Optional[str] = None
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
            "free_text_input": free_text,
            "xray_trace_id": xray_trace_id or ""
        }

        # Run Swarm investigation (async) - await since we're in an async context
        report = await orchestrator.investigate(inputs, region, assume_role_arn, external_id)
        
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
        facts_count = len(report.facts) if hasattr(report, 'facts') else 0
        hypotheses_count = len(report.hypotheses) if hasattr(report, 'hypotheses') else 0
        result_summary = f"Investigation completed successfully. Found {facts_count} facts and {hypotheses_count} hypotheses."
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


async def _handle_investigation_inputs(
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

        # Run Swarm investigation (async) - await since we're in an async context
        report = await orchestrator.investigate(inputs, region, assume_role_arn, external_id)
        
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
