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

import json
from typing import List, Optional
from ..models import Fact, Hypothesis
from ..utils import get_logger

logger = get_logger(__name__)


class HypothesisAgent:
    """Agent responsible for generating hypotheses from facts."""

    def __init__(self, strands_agent=None):
        """Initialize the hypothesis agent."""
        self.strands_agent = strands_agent
    
    def generate_hypotheses(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses from facts using AI or fallback to heuristics."""
        if not facts:
            logger.warning("No facts provided for hypothesis generation")
            return []

        logger.info(f"Generating hypotheses from {len(facts)} facts")

        # Try AI-powered hypothesis generation first
        if self.strands_agent:
            try:
                return self._generate_hypotheses_with_ai(facts)
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

        prompt = f"""You are an expert AWS serverless incident analyst. Analyze these facts and generate 3-5 root cause hypotheses.

FACTS:
{facts_text}

CRITICAL RULE:
- ONLY base hypotheses on facts provided above
- DO NOT assume or invent services, resources, or configurations that are not mentioned in the facts
- If facts mention "API Gateway integrates with Step Functions", DO NOT say "Lambda" anywhere
- Be specific about what you actually observe in the facts

HYPOTHESIS PRIORITIZATION PRINCIPLES:
When analyzing incidents, distinguish between CAUSES and SYMPTOMS:

1. **Direct Causes** (High Confidence 0.85-0.99):
   - Application errors: exceptions, runtime errors, code crashes, unhandled errors
   - Logic bugs: division by zero, null/undefined references, type mismatches
   - Resource exhaustion: out of memory, disk full, connection pool exhausted
   - Configuration problems: invalid settings that prevent execution
   - Permission denials: IAM policies blocking required actions

2. **Contributing Factors** (Medium Confidence 0.50-0.84):
   - Performance issues: slow queries, inefficient algorithms, cold starts
   - Resource constraints: low memory allocation, tight timeouts
   - Integration problems: downstream service failures, network issues
   - Rate limiting or throttling

3. **Observable Symptoms** (Low Confidence 0.10-0.49):
   - Missing logs or monitoring gaps (these hide the problem, they don't cause it)
   - Lack of observability features
   - Incomplete telemetry

CONFIDENCE SCORING GUIDANCE:
- If you find an exception or error in logs → this is a DIRECT CAUSE → confidence 0.85+
- If you find performance degradation → this is a CONTRIBUTING FACTOR → confidence 0.50-0.84
- If you find missing logs → this is a SYMPTOM of poor observability → confidence 0.10-0.49

Generate hypotheses that:
1. Explain the root cause of the incident (focus on DIRECT CAUSES first)
2. Are specific and actionable
3. Are ranked by likelihood/confidence (highest confidence = most likely root cause)
4. Include supporting evidence from the facts

Respond with ONLY a JSON array in this exact format:
[
  {{
    "type": "category_name",
    "description": "Clear explanation of the hypothesis",
    "confidence": 0.95,
    "evidence": ["fact 1", "fact 2"]
  }}
]

Valid hypothesis types: code_bug, configuration_error, permission_issue, resource_constraint, timeout, infrastructure_issue, integration_failure"""

        try:
            # Use Strands agent to generate hypotheses (call agent directly)
            response = self.strands_agent(prompt)

            # Cost tracking removed

            # Parse response
            hypotheses_data = self._parse_ai_response(response)

            # Convert to Hypothesis objects
            hypotheses = []
            for h_data in hypotheses_data:
                hypothesis = Hypothesis(
                    type=h_data.get('type', 'unknown'),
                    description=h_data.get('description', ''),
                    confidence=float(h_data.get('confidence', 0.5)),
                    evidence=h_data.get('evidence', [])
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
