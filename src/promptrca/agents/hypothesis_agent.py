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

"""

import json
from typing import List, Optional
from ..models import Fact, Hypothesis
from ..utils import get_logger

logger = get_logger(__name__)


class HypothesisAgent:
    """Agent responsible for generating hypotheses from facts."""

    def __init__(self, strands_agent=None, model=None):
        """Initialize the hypothesis agent."""
        if strands_agent:
            self.strands_agent = strands_agent
        elif model:
            from strands import Agent
            self.strands_agent = Agent(model=model)
        else:
            self.strands_agent = None
    
    def generate_hypotheses(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses from facts using AI or fallback to heuristics."""
        if not facts:
            logger.warning("No facts provided for hypothesis generation")
            return []

        logger.info(f"Generating hypotheses from {len(facts)} facts")

        # Try AI-powered hypothesis generation first
        if self.strands_agent:
            try:
                base_hypotheses = self._generate_hypotheses_with_ai(facts)
                return base_hypotheses
            except Exception as e:
                logger.error(f"AI hypothesis generation failed: {e}, falling back to heuristics")
                return self._generate_hypotheses_heuristic(facts)
        else:
            logger.warning("No Strands agent available, using heuristic approach")
            return self._generate_hypotheses_heuristic(facts)

    def _generate_hypotheses_with_ai(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses using Strands AI agent."""
        logger.info("🤖 Using AI for hypothesis generation")

        # Build the prompt for AI
        facts_text = "\n".join([f"- [{f.source}] {f.content} (confidence: {f.confidence:.2f})" for f in facts])

        prompt = f"""You will be given a set of facts collected during an incident investigation. Your objective is to methodically analyze these facts and generate evidence-based hypotheses about the root cause.

EXPERT ROLE: You are an expert incident analyst with strong pattern recognition skills and deep understanding of cloud system failure modes. You excel at connecting evidence to potential root causes.

FACTS (from investigation tools):
{facts_text}

REASONING PROCESS (follow these steps sequentially):

STEP 1: IDENTIFY EXPLICIT ERRORS
- Look for exact error messages, exceptions, or failure indicators in facts
- Note error types: runtime exceptions, permission denials, timeouts, etc.
- Example: "AccessDenied" → permission_issue with 0.90+ confidence

STEP 2: IDENTIFY CONFIGURATION ISSUES
- Look for configuration values that contradict requirements or best practices
- Check for mismatches between settings and observed behavior
- Example: timeout=3s + "timed out after 3s" → timeout with 0.85+ confidence

STEP 3: CORRELATE RELATED FACTS
- Group facts that point to the same underlying issue
- Stronger hypotheses need 2+ supporting facts
- Example: "high memory usage" + "near memory limit" → resource_constraint with 0.80+ confidence

STEP 4: ASSIGN CONFIDENCE SCORES
- 0.95-1.0: Explicit error message with stack trace/error code
- 0.85-0.94: Configuration mismatch directly observed
- 0.70-0.84: Strong correlation between 2+ facts
- 0.50-0.69: Weak correlation or single indirect fact
- <0.50: DO NOT create hypothesis - insufficient evidence

STEP 5: VALIDATE EVIDENCE
- Every hypothesis MUST cite specific fact content as evidence
- Do NOT reference facts that don't exist
- Do NOT create hypotheses without evidence

CONFIDENCE CALIBRATION EXAMPLES:
- "ZeroDivisionError at line 42" → code_bug, confidence=0.95 (explicit error)
- "timeout=3s" + "timed out after 3.00s" → timeout, confidence=0.88 (config + observation)
- "high error rate" → error_rate, confidence=0.70 (single metric without root cause)
- "AccessDenied when calling PutObject" → permission_issue, confidence=0.92 (explicit permission error)

HYPOTHESIS TYPES:
permission_issue, configuration_error, code_bug, timeout, resource_constraint, integration_failure, infrastructure_issue

RULES:
- Each hypothesis must cite specific facts as evidence
- Do NOT invent scenarios not in facts
- Rank by confidence (highest first)
- THINK through steps 1-5 before responding

CRITICAL REQUIREMENTS:
- Be thorough and evidence-based - every hypothesis needs concrete facts
- Eliminate speculation - if there's insufficient evidence, don't create a hypothesis
- Base ALL hypotheses on the provided facts, never on assumptions
- Assign confidence scores honestly based on evidence strength
- Cross-reference facts to ensure hypotheses are supported

OUTPUT FORMAT:
First, provide your reasoning process wrapped between <REASONING_START> and <REASONING_END> tags.
Then, provide the JSON output.

JSON: [{{"type": "...", "description": "...", "confidence": 0.0-1.0, "evidence": ["fact1", "fact2"]}}]"""

        try:
            # Use Strands agent to generate hypotheses (call agent directly)
            response = self.strands_agent(prompt)


            # Parse response
            hypotheses_data = self._parse_ai_response(response)

            # Convert to Hypothesis objects with evidence validation
            hypotheses = []
            for h_data in hypotheses_data:
                evidence = h_data.get('evidence', [])
                if not evidence or len(evidence) == 0:
                    logger.warning(f"Dropping hypothesis without evidence: {h_data.get('description')}")
                    continue
                
                hypothesis = Hypothesis(
                    type=h_data.get('type', 'unknown'),
                    description=h_data.get('description', ''),
                    confidence=float(h_data.get('confidence', 0.5)),
                    evidence=evidence
                )
                hypotheses.append(hypothesis)

            logger.info(f"✅ Generated {len(hypotheses)} AI-powered hypotheses")
            return hypotheses

        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise

    def _parse_ai_response(self, response: str) -> List[dict]:
        """Parse AI response, handling various formats."""
        # Try to extract JSON from response
        response_str = str(response)

        # Remove markdown code blocks if present
        if "```json" in response_str:
            response_str = response_str.split("```json")[1].split("```")[0].strip()
        elif "```" in response_str:
            response_str = response_str.split("```")[1].split("```")[0].strip()

        # Find JSON array
        start_idx = response_str.find('[')
        end_idx = response_str.rfind(']') + 1

        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON array found in AI response")

        json_str = response_str[start_idx:end_idx]
        return json.loads(json_str)

    def _generate_hypotheses_heuristic(self, facts: List[Fact]) -> List[Hypothesis]:
        """Fallback heuristic-based hypothesis generation."""
        logger.info("📊 Using heuristic approach for hypothesis generation")

        # Cost tracking removed

        hypotheses = []
        identified_issues = set()

        for fact in facts:
            content_lower = fact.content.lower()

            # Timeout issues
            if "timeout" in content_lower and "timeout" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="timeout",
                    description="Function execution timeout due to cold start or resource constraints",
                    confidence=0.8,
                    evidence=[fact.content]
                ))
                identified_issues.add("timeout")

            # Error rate issues
            if ("error rate" in content_lower or "errors" in content_lower) and "error_rate" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="error_rate",
                    description="Increased error rate indicates potential infrastructure or code issues",
                    confidence=0.7,
                    evidence=[fact.content]
                ))
                identified_issues.add("error_rate")

            # Resource constraint issues
            if "low memory" in content_lower and "resource_constraint" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="resource_constraint",
                    description="Low memory allocation might be causing performance issues or timeouts",
                    confidence=0.85,
                    evidence=[fact.content]
                ))
                identified_issues.add("resource_constraint")

            # Code bugs
            if "division by zero" in content_lower and "division_by_zero" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="code_bug",
                    description="Division by zero error in code - likely caused by dividing by length of empty list",
                    confidence=0.95,
                    evidence=[fact.content]
                ))
                identified_issues.add("division_by_zero")

            if "empty list" in content_lower and "not properly handle" in content_lower and "empty_list_handling" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="code_bug",
                    description="Function may not properly handle empty input lists, causing runtime errors",
                    confidence=0.85,
                    evidence=[fact.content]
                ))
                identified_issues.add("empty_list_handling")

            if "missing error handling" in content_lower and "error_handling" not in identified_issues:
                hypotheses.append(Hypothesis(
                    type="code_bug",
                    description="Missing error handling around critical operations may cause unhandled exceptions",
                    confidence=0.8,
                    evidence=[fact.content]
                ))
                identified_issues.add("error_handling")

        logger.info(f"✅ Generated {len(hypotheses)} heuristic hypotheses")
        return hypotheses
    
