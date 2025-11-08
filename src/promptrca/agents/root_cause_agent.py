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

        hypotheses_list = []
        for i, h in enumerate(hypothesis_data):
            hypotheses_list.append(f"{i+1}. [{h['type']}] {h['description']} (confidence: {h['confidence']:.2f})")
        
        prompt = f"""You will be given a list of hypotheses about an incident, already sorted by confidence. Your objective is to methodically analyze these hypotheses and select the PRIMARY root cause that best explains the incident.

EXPERT ROLE: You are an expert incident analyst with advanced analytical and reasoning skills, experienced in identifying root causes in cloud system incidents. You understand causal relationships and can distinguish between symptoms and underlying causes.

HYPOTHESES (ranked by confidence):
{chr(10).join(hypotheses_list)}

ANALYSIS PROCESS (follow these steps):

STEP 1: EXAMINE EACH HYPOTHESIS
- Review the type, description, and confidence score
- Consider: Does this explain the DIRECT cause of the incident?
- Ask: Is this a symptom or the underlying root cause?

STEP 2: IDENTIFY CAUSAL RELATIONSHIPS
- Determine which hypotheses might CAUSE other hypotheses
- Example: permission_issue (root) → integration_failure (symptom)
- Example: code_bug (root) → timeout (symptom)
- Root causes are typically: permission_issue, configuration_error, code_bug, infrastructure_issue
- Symptoms are typically: timeout, error_rate, integration_failure, resource_constraint

STEP 3: SELECT PRIMARY ROOT CAUSE
- Choose the hypothesis that is:
  a) Highest confidence among TRUE root causes (not symptoms)
  b) Most likely to explain other hypotheses
  c) Actionable (can be fixed directly)
- If top hypothesis is a symptom, check if a lower-ranked hypothesis is the actual root cause

STEP 4: IDENTIFY CONTRIBUTING FACTORS
- Select 1-3 other high-confidence hypotheses
- These should be either:
  a) Secondary root causes
  b) Important context for understanding the primary root cause
  c) Related configuration issues

STEP 5: SELF-VALIDATION
Check your selection:
- ✓ Primary root cause has confidence ≥ 0.70?
- ✓ Primary explains the incident timeline?
- ✓ Contributing factors are distinct from primary?
- ✓ Analysis summary explains WHY this is the root cause?

CONFIDENCE VALIDATION:
- If primary_root_cause has confidence < 0.70 → explain uncertainty in summary
- If multiple hypotheses have similar confidence → explain why you chose this one
- If only symptoms are available → state "root cause unclear, symptoms identified"

CAUSAL RELATIONSHIP EXAMPLES:
- code_bug → timeout (bug causes slow execution)
- permission_issue → integration_failure (lack of permissions prevents integration)
- configuration_error → resource_constraint (wrong settings cause resource issues)
- infrastructure_issue → error_rate (unstable infrastructure causes errors)

RULES:
- Primary = hypothesis that best explains the DIRECT cause of the incident
- Prefer root causes over symptoms when confidence is similar
- Contributing factors = other high-confidence hypotheses or secondary causes
- Summary: 2-3 sentences explaining selection logic and causal relationships

CRITICAL REQUIREMENTS:
- Be thorough and evidence-based in your reasoning
- Eliminate personal biases
- Base your selection ENTIRELY on the hypothesis evidence and confidence scores
- Clearly explain WHY you selected this particular root cause over others

OUTPUT FORMAT:
Provide your analysis wrapped between <ANALYSIS_START> and <ANALYSIS_END> tags, followed by the JSON.

JSON: {{"primary_root_cause_index": 0, "contributing_factor_indices": [1,2], "analysis_summary": "..."}}"""

        try:
            # Use Strands agent
            response = self.strands_agent(prompt)


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
        """Fallback classification with symptom vs root cause detection."""
        logger.info("📊 Using fallback root cause classification")

        # Define symptom types (these are effects, not causes)
        SYMPTOM_TYPES = {"timeout", "error_rate", "throttling", "high_latency", "resource_constraint"}

        # Define root cause types (these are actual causes)
        ROOT_CAUSE_TYPES = {"permission_issue", "configuration_error", "code_bug",
                            "infrastructure_issue", "integration_failure", "network_issue"}

        # Separate hypotheses into root causes and symptoms
        root_causes = [h for h in hypotheses if h.type in ROOT_CAUSE_TYPES]
        symptoms = [h for h in hypotheses if h.type in SYMPTOM_TYPES]
        unknown = [h for h in hypotheses if h.type not in ROOT_CAUSE_TYPES and h.type not in SYMPTOM_TYPES]

        # Select primary root cause
        primary_root_cause = None
        contributing_factors = []

        if root_causes:
            # Pick highest confidence root cause
            primary_root_cause = max(root_causes, key=lambda h: h.confidence)

            # Contributing factors: other root causes + top symptoms
            other_root_causes = [h for h in root_causes if h != primary_root_cause]
            contributing_factors = other_root_causes[:2] + symptoms[:1]

            summary = (f"Identified {primary_root_cause.type} as primary root cause "
                      f"(confidence: {primary_root_cause.confidence:.2f})")
            if symptoms:
                symptom_types = ", ".join([s.type for s in symptoms[:3]])
                summary += f". Observed symptoms: {symptom_types}"

        elif symptoms:
            # Only symptoms available - pick highest confidence but reduce confidence
            primary_root_cause = max(symptoms, key=lambda h: h.confidence)
            original_confidence = primary_root_cause.confidence

            # Reduce confidence by 30% since we only have symptoms, not root causes
            # Create a new Hypothesis object with adjusted confidence
            from ..models import Hypothesis as HypothesisModel
            primary_root_cause = HypothesisModel(
                type=primary_root_cause.type,
                description=primary_root_cause.description + " (symptom - root cause unclear)",
                confidence=primary_root_cause.confidence * 0.7,
                evidence=primary_root_cause.evidence
            )

            contributing_factors = [s for s in symptoms if s != primary_root_cause][:2]
            summary = (f"Only symptoms identified, no clear root cause. "
                      f"Primary symptom: {primary_root_cause.type} "
                      f"(adjusted confidence: {primary_root_cause.confidence:.2f}, "
                      f"original: {original_confidence:.2f})")

        elif unknown:
            # Unknown hypothesis types
            primary_root_cause = max(unknown, key=lambda h: h.confidence)
            contributing_factors = [h for h in unknown if h != primary_root_cause][:2]
            summary = f"Identified {primary_root_cause.type} as potential root cause (type classification unclear)"

        else:
            # No hypotheses at all
            summary = "No hypotheses available for root cause analysis"

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
