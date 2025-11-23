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

from typing import List, Dict, Any, Optional
import json

from ..models.base import Fact, Hypothesis, RootCauseAnalysis
from ..utils import get_logger

logger = get_logger(__name__)


class RootCauseAgent:
    """Agent that identifies primary root cause from hypotheses."""
    
    def __init__(self, strands_agent=None):
        """
        Initialize the root cause analysis agent.
        
        Note: Root cause analysis is purely analytical and doesn't require AWS API calls.
        """
        self.strands_agent = strands_agent
    
    def analyze_root_cause(self, hypotheses: List[Hypothesis], facts: List[Fact]) -> RootCauseAnalysis:
        """Identify primary root cause and contributing factors."""
        logger.info(f"Analyzing root cause from {len(hypotheses)} hypotheses")

        if not hypotheses:
            logger.warning("No hypotheses provided for root cause analysis")
            return RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary="No hypotheses generated - unable to determine root cause"
            )

        # Sort hypotheses by confidence
        sorted_hyps = sorted(hypotheses, key=lambda h: h.confidence, reverse=True)
        MIN_CONFIDENCE = 0.70
        high_confidence_hyps = [h for h in sorted_hyps if h.confidence >= MIN_CONFIDENCE]

        if not high_confidence_hyps:
            logger.warning("No hypotheses meet minimum confidence threshold; root cause unclear")
            return RootCauseAnalysis(
                primary_root_cause=None,
                contributing_factors=[],
                confidence_score=0.0,
                analysis_summary="root cause unclear - insufficient evidence (no hypotheses with confidence ≥ 0.70)"
            )

        if len(high_confidence_hyps) < len(sorted_hyps):
            logger.info(f"Filtered out {len(sorted_hyps) - len(high_confidence_hyps)} low-confidence hypotheses before analysis")

        # AI classification (required)
        if not self.strands_agent:
            error_msg = "No Strands agent available - root cause analysis requires AI agent"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        try:
            analysis = self._classify_hypotheses_with_ai(high_confidence_hyps, facts)
        except Exception as e:
            logger.error(f"AI root cause analysis failed: {e}")
            raise

        return RootCauseAnalysis(
            primary_root_cause=analysis['primary_root_cause'],
            contributing_factors=analysis['contributing_factors'],
            confidence_score=analysis['primary_root_cause'].confidence if analysis['primary_root_cause'] else 0.0,
            analysis_summary=analysis['analysis_summary']
        )
    
    def _classify_hypotheses_with_ai(self, hypotheses: List[Hypothesis], facts: List[Fact]) -> Dict[str, Any]:
        """Use AI to classify hypotheses into primary root cause vs contributing factors."""
        logger.info("🤖 Using AI for root cause classification")

        if not hypotheses:
            logger.warning("No hypotheses provided to AI classifier after filtering; marking root cause unclear")
            return {
                "primary_root_cause": None,
                "contributing_factors": [],
                "confidence_score": 0.0,
                "analysis_summary": "root cause unclear - insufficient evidence"
            }

        # Build context for AI analysis
        hypothesis_data = []
        for i, hyp in enumerate(hypotheses):
            hypothesis_data.append({
                "index": i,
                "type": hyp.type,
                "description": hyp.description,
                "confidence": hyp.confidence,
                "evidence_count": len(hyp.evidence)
            })

        # Sample key facts for context
        sample_facts = [f.content for f in facts[:5]]

        hypotheses_list = []
        for i, h in enumerate(hypothesis_data):
            hypotheses_list.append(
                f"{i+1}. [{h['type']}] {h['description']} (confidence: {h['confidence']:.2f}, evidence_count: {h['evidence_count']})"
            )
        
        # Load prompt template and format with hypotheses
        from ..utils.prompt_loader import load_prompt
        prompt = load_prompt("root_cause_analyzer", variables={"hypotheses_list": "\n".join(hypotheses_list)}, category="graph")

        try:
            # Use Strands agent with retry
            from ..utils.agent_retry import invoke_agent_with_retry
            response = invoke_agent_with_retry(self.strands_agent, prompt)


            # Parse response
            ai_response = self._parse_root_cause_response(response)

            primary_index = ai_response.get("primary_root_cause_index", 0)
            contributing_indices = ai_response.get("contributing_factor_indices", [])
            summary = ai_response.get("analysis_summary", "AI analysis completed")

            # Extract primary root cause
            primary_root_cause = None
            if 0 <= primary_index < len(hypotheses):
                primary_root_cause = hypotheses[primary_index]

            # Extract contributing factors
            contributing_factors = []
            for idx in contributing_indices:
                if 0 <= idx < len(hypotheses) and idx != primary_index:
                    contributing_factors.append(hypotheses[idx])

            logger.info(f"✅ Identified primary root cause: {primary_root_cause.type if primary_root_cause else 'None'}")
            logger.info(f"✅ Identified {len(contributing_factors)} contributing factors")

            return {
                "primary_root_cause": primary_root_cause,
                "contributing_factors": contributing_factors,
                "confidence_score": primary_root_cause.confidence if primary_root_cause else 0.0,
                "analysis_summary": summary
            }

        except Exception as e:
            logger.error(f"Failed to classify hypotheses with AI: {e}")
            raise

    def _parse_root_cause_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for root cause classification."""
        response_str = str(response)

        # Remove markdown code blocks if present
        if "```json" in response_str:
            response_str = response_str.split("```json")[1].split("```")[0].strip()
        elif "```" in response_str:
            response_str = response_str.split("```")[1].split("```")[0].strip()

        # Find JSON object
        start_idx = response_str.find('{')
        end_idx = response_str.rfind('}') + 1

        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON object found in AI response")

        json_str = response_str[start_idx:end_idx]
        return json.loads(json_str)
