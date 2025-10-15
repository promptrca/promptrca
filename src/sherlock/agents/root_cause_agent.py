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

from typing import List, Dict, Any, Optional
import json

from ..models.base import Fact, Hypothesis, RootCauseAnalysis
from ..clients.aws_client import AWSClient
from ..utils import get_logger

logger = get_logger(__name__)


class RootCauseAgent:
    """Agent that identifies primary root cause from hypotheses."""
    
    def __init__(self, aws_client: AWSClient, strands_agent=None):
        """Initialize the root cause analysis agent."""
        self.aws_client = aws_client
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

        # Try AI classification first
        if self.strands_agent:
            try:
                analysis = self._classify_hypotheses_with_ai(sorted_hyps, facts)
            except Exception as e:
                logger.error(f"AI root cause analysis failed: {e}, using fallback")
                analysis = self._classify_hypotheses_fallback(sorted_hyps)
        else:
            logger.warning("No Strands agent available, using fallback classification")
            analysis = self._classify_hypotheses_fallback(sorted_hyps)

        return RootCauseAnalysis(
            primary_root_cause=analysis['primary_root_cause'],
            contributing_factors=analysis['contributing_factors'],
            confidence_score=analysis['primary_root_cause'].confidence if analysis['primary_root_cause'] else 0.0,
            analysis_summary=analysis['analysis_summary']
        )
    
    def _classify_hypotheses_with_ai(self, hypotheses: List[Hypothesis], facts: List[Fact]) -> Dict[str, Any]:
        """Use AI to classify hypotheses into primary root cause vs contributing factors."""
        logger.info("🤖 Using AI for root cause classification")

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

        prompt = f"""Select PRIMARY root cause from hypotheses (already sorted by confidence).

HYPOTHESES:
{chr(10).join(f"{i+1}. [{h['type']}] {h['description']} (confidence: {h['confidence']:.2f})" for i, h in enumerate(hypothesis_data))}

RULES:
- Primary = highest confidence hypothesis that explains the incident
- Contributing factors = other high-confidence hypotheses
- Summary: 1-2 sentences explaining selection

OUTPUT: JSON {"primary_root_cause_index": 0, "contributing_factor_indices": [1,2], "analysis_summary": "..."}"""

        try:
            # Use Strands agent
            response = self.strands_agent(prompt)

            # Cost tracking removed

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

    def _classify_hypotheses_fallback(self, hypotheses: List[Hypothesis]) -> Dict[str, Any]:
        """Fallback classification based on confidence scores."""
        logger.info("📊 Using fallback root cause classification")

        # Simple heuristic: highest confidence is primary, rest are contributing
        primary_root_cause = hypotheses[0] if hypotheses else None
        contributing_factors = hypotheses[1:3] if len(hypotheses) > 1 else []

        summary = f"Based on confidence scores, identified {primary_root_cause.type if primary_root_cause else 'unknown'} as primary root cause"
        if contributing_factors:
            summary += f" with {len(contributing_factors)} contributing factors"

        return {
            "primary_root_cause": primary_root_cause,
            "contributing_factors": contributing_factors,
            "confidence_score": primary_root_cause.confidence if primary_root_cause else 0.0,
            "analysis_summary": summary
        }
    
    def _build_root_cause_prompt(self, facts: List[Fact], hypotheses: List[Hypothesis]) -> str:
        """Build a prompt for AI root cause analysis."""
        
        facts_text = "\n".join([f"- {fact.content}" for fact in facts])
        hypotheses_text = "\n".join([f"{i+1}. {hyp.type}: {hyp.description} (confidence: {hyp.confidence})" for i, hyp in enumerate(hypotheses)])
        
        prompt = f"""
Analyze the following facts and hypotheses to identify the primary root cause and contributing factors.

FACTS:
{facts_text}

HYPOTHESES (numbered for reference):
{hypotheses_text}

Please provide a JSON response with:
{{
    "primary_root_cause_index": 0,
    "contributing_factor_indices": [1, 2],
    "analysis_summary": "Clear explanation of why this is the root cause and how contributing factors relate..."
}}

Use the hypothesis numbers (0-based indexing) for the indices.
"""
        return prompt
    
    def _analyze_causal_relationships(self, hypotheses: List[Hypothesis]) -> Dict[str, List[int]]:
        """Analyze potential causal relationships between hypotheses."""
        
        # Define common causal patterns
        causal_patterns = {
            "iam_permission": ["lambda_invocation", "stepfunctions_execution", "apigateway_integration"],
            "lambda_invocation": ["lambda_code", "lambda_config", "lambda_timeout"],
            "stepfunctions_execution": ["lambda_invocation", "iam_permission", "stepfunctions_config"],
            "apigateway_integration": ["iam_permission", "stepfunctions_execution", "lambda_invocation"],
            "lambda_code": ["lambda_invocation", "lambda_timeout"],
            "lambda_config": ["lambda_invocation", "lambda_timeout", "lambda_memory"],
            "network": ["lambda_invocation", "stepfunctions_execution", "apigateway_integration"]
        }
        
        relationships = {"causes": [], "effects": []}
        
        for i, hyp1 in enumerate(hypotheses):
            for j, hyp2 in enumerate(hypotheses):
                if i != j:
                    # Check if hyp1 could cause hyp2
                    if hyp1.type in causal_patterns and hyp2.type in causal_patterns[hyp1.type]:
                        relationships["causes"].append((i, j))
                    # Check if hyp2 could cause hyp1
                    elif hyp2.type in causal_patterns and hyp1.type in causal_patterns[hyp2.type]:
                        relationships["effects"].append((i, j))
        
        return relationships
