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

"""

import json
import re
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
        """Generate hypotheses from facts using AI."""
        if not facts:
            logger.warning("No facts provided for hypothesis generation")
            return []

        logger.info(f"Generating hypotheses from {len(facts)} facts")

        # AI-powered hypothesis generation (required)
        if not self.strands_agent:
            error_msg = "No Strands agent available - hypothesis generation requires AI agent"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            base_hypotheses = self._generate_hypotheses_with_ai(facts)
            return base_hypotheses
        except Exception as e:
            logger.error(f"AI hypothesis generation failed: {e}")
            raise

    def _generate_hypotheses_with_ai(self, facts: List[Fact]) -> List[Hypothesis]:
        """Generate hypotheses using Strands AI agent."""
        logger.info("🤖 Using AI for hypothesis generation")

        evidence_facts = [f for f in facts if self._has_explicit_evidence(f)]
        if not evidence_facts:
            logger.warning("No explicit errors/failure indicators in facts; returning empty hypotheses per prompt guard")
            return []

        # Build the prompt for AI
        facts_text = "\n".join([f"- [{f.source}] {f.content} (confidence: {f.confidence:.2f})" for f in facts])

        # Load prompt template and format with facts
        from ..utils.prompt_loader import load_prompt
        prompt = load_prompt("hypothesis_generator", variables={"facts_text": facts_text}, category="graph")

        try:
            # Use Strands agent to generate hypotheses with retry
            from ..utils.agent_retry import invoke_agent_with_retry
            response = invoke_agent_with_retry(self.strands_agent, prompt)


            # Parse response
            hypotheses_data = self._parse_ai_response(response)

            # Convert to Hypothesis objects with evidence validation
            hypotheses = []
            MIN_CONFIDENCE = 0.70
            for h_data in hypotheses_data:
                evidence = h_data.get('evidence', [])
                if not evidence or len(evidence) == 0:
                    logger.warning(f"Dropping hypothesis without evidence: {h_data.get('description')}")
                    continue
                if all(self._evidence_is_absence(item) for item in evidence):
                    logger.warning(f"Dropping hypothesis based solely on missing/absent data: {h_data.get('description')}")
                    continue

                confidence = float(h_data.get('confidence', 0.5))
                if confidence < MIN_CONFIDENCE:
                    logger.info(f"Dropping low-confidence hypothesis ({confidence:.2f} < {MIN_CONFIDENCE:.2f}): {h_data.get('description')}")
                    continue
                
                hypothesis = Hypothesis(
                    type=h_data.get('type', 'unknown'),
                    description=h_data.get('description', ''),
                    confidence=confidence,
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

    def _has_explicit_evidence(self, fact: Fact) -> bool:
        """Detect explicit errors, failures, or configuration mismatches."""
        content = fact.content.lower()
        keywords = [
            "error", "exception", "fail", "failure", "denied", "forbidden", "unauthorized",
            "timeout", "timed out", "throttle", "throttl", "limit exceeded", "exceeded",
            "invalid", "mismatch", "misconfig", "not configured", "not found", "missing permission",
            "accessdenied", "access denied", "unavailable", "service unavailable"
        ]
        status_code_match = re.search(r"\b[45]\d{2}\b", content)
        return bool(status_code_match or any(k in content for k in keywords))

    def _evidence_is_absence(self, evidence_text: str) -> bool:
        """Check if evidence references only missing/absent data."""
        text = evidence_text.lower()
        absence_markers = [
            "missing", "absent", "no data", "not captured", "no payload", "no payloads",
            "empty trace", "not present", "not recorded", "did not capture", "no logs",
            "no evidence", "no errors observed"
        ]
        return any(marker in text for marker in absence_markers)
