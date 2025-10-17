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

"""

from typing import List, Dict, Any
from strands import Agent
from ...models import Fact
from ...tools.aws_tools import (
    get_api_gateway_stage_config,
    get_iam_role_config,
    get_cloudwatch_logs
)
from ...prompts.loader import load_prompt, load_prompt_with_vars


def create_apigateway_agent(model) -> Agent:
    """Create an API Gateway specialist agent with tools."""
    
    system_prompt = load_prompt("specialized/apigateway_agent")

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_api_gateway_stage_config, get_iam_role_config, get_cloudwatch_logs],
        trace_attributes={
            "service.name": "sherlock-apigateway-agent",
            "service.version": "1.0.0",
            "agent.type": "apigateway_specialist",
            "aws.service": "apigateway"
        }
    )


def create_apigateway_agent_tool(apigateway_agent: Agent):
    """Create a tool that wraps the API Gateway agent for use by orchestrators."""
    from strands import tool
    
    @tool
    def investigate_api_gateway(api_id: str, stage_name: str = "test", investigation_context: str = "") -> str:
        """
        Investigate an API Gateway for issues and problems.
        
        Args:
            api_id: The API Gateway REST API ID
            stage_name: The stage name (e.g., 'test', 'prod')
            investigation_context: Additional context about the investigation (e.g., error messages, trace IDs)
        
        Returns:
            JSON string with investigation results and findings
        """
        import json
        
        try:
            # Create investigation prompt
            prompt = load_prompt_with_vars("specialized/apigateway_investigation", 
                                         api_id=api_id, 
                                         stage_name=stage_name,
                                         investigation_context=investigation_context)

            # Run the agent
            agent_result = apigateway_agent(prompt)
            
            # Extract the response content from AgentResult
            response = str(agent_result.content) if hasattr(agent_result, 'content') else str(agent_result)

            def _extract_json(s: str):
                try:
                    import json as _json
                    text = s.strip()
                    if "```" in text:
                        if "```json" in text:
                            text = text.split("```json", 1)[1].split("```", 1)[0]
                        else:
                            text = text.split("```", 1)[1].split("```", 1)[0]
                    return _json.loads(text)
                except Exception:
                    return None

            data = _extract_json(response) or {}
            # Basic validation and normalization
            if isinstance(data.get("facts"), dict) or isinstance(data.get("facts"), str):
                data["facts"] = [data.get("facts")]
            if isinstance(data.get("hypotheses"), dict):
                data["hypotheses"] = [data.get("hypotheses")]
            if isinstance(data.get("advice"), dict):
                data["advice"] = [data.get("advice")]
            summary = data.get("summary") or (response[:500] + "..." if len(str(response)) > 500 else str(response))

            return json.dumps({
                "target": {"type": "api_gateway", "api_id": api_id, "stage_name": stage_name},
                "context": investigation_context,
                "status": "completed",
                "facts": data.get("facts") or [],
                "hypotheses": data.get("hypotheses") or [],
                "advice": data.get("advice") or [],
                "artifacts": {"raw_analysis": str(response)},
                "summary": summary
            })
            
        except Exception as e:
            return json.dumps({
                "target": {
                    "type": "api_gateway",
                    "api_id": api_id,
                    "stage_name": stage_name
                },
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })
    
    return investigate_api_gateway

