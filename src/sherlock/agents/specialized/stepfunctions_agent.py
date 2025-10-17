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

from typing import Any
from strands import Agent
from ...tools.aws_tools import (
    get_stepfunctions_definition,
    get_iam_role_config,
    get_cloudwatch_logs
)


def create_stepfunctions_agent(model) -> Agent:
    """Create a Step Functions specialist agent with tools."""
    system_prompt = """You are a Step Functions specialist investigating AWS Step Functions workflow execution and state machine issues.

INVESTIGATION METHODOLOGY:
1. Start by examining the state machine definition (ASL JSON) to understand workflow structure and task resources
2. Analyze execution logs to identify failed states, errors, and execution patterns
3. If permission errors are suspected, review the IAM role permissions against required actions
4. Cross-reference task resource ARNs with actual AWS services being invoked
5. Identify state transitions and failure points in the workflow

ANALYSIS RULES:
- Base all findings strictly on tool outputs - no speculation beyond what you observe
- Extract concrete facts: state definitions, task ARNs, IAM permissions, execution errors, state transitions
- Every hypothesis MUST cite specific evidence from facts
- Return empty arrays [] if no evidence found
- Map observations to hypothesis types:
  * "AccessDeniedException" in logs → permission_issue
  * "States.TaskFailed" in logs → integration_failure
  * Missing or invalid resource ARNs → configuration_error
  * State machine definition errors → definition_error
  * Execution timeouts → timeout
  * Retry failures → retry_exhausted
  * Invalid state transitions → state_error
- Focus on workflow execution problems first (failures, permissions, configuration)

OUTPUT SCHEMA (strict):
{
  "facts": [{"source": "tool_name", "content": "observation", "confidence": 0.0-1.0, "metadata": {}}],
  "hypotheses": [{"type": "category", "description": "issue", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}],
  "advice": [{"title": "action", "description": "details", "priority": "high/medium/low", "category": "type"}],
  "summary": "1-2 sentences"
}

INVESTIGATION PRIORITIES:
1. Execution failures and state errors (highest priority)
2. Permission and access control issues
3. Configuration and definition problems
4. Integration failures with downstream services
5. Workflow optimization opportunities"""

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[get_stepfunctions_definition, get_iam_role_config, get_cloudwatch_logs]
    )


def create_stepfunctions_agent_tool(stepfunctions_agent: Agent):
    """Create a tool that wraps the Step Functions agent for use by orchestrators."""
    from strands import tool

    @tool
    def investigate_stepfunctions(state_machine_arn: str, investigation_context: str = "") -> str:
        import json
        try:
            prompt = f"""Investigate Step Functions state machine: {state_machine_arn}

Context: {investigation_context}

Please analyze this Step Functions state machine for any issues, errors, or problems. Start by getting the state machine definition, then check IAM permissions if execution issues are suspected, and examine logs for errors."""
            agent_result = stepfunctions_agent(prompt)
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
                "target": {"type": "step_functions", "state_machine_arn": state_machine_arn},
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
                "target": {"type": "step_functions", "state_machine_arn": state_machine_arn},
                "context": investigation_context,
                "status": "failed",
                "error": str(e)
            })

    return investigate_stepfunctions

