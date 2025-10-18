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

from typing import List, Dict, Any
from datetime import datetime, timezone
import json

from ..models.base import Fact, Hypothesis, AffectedResource, SeverityAssessment
from ..clients.aws_client import AWSClient
from ..utils import get_logger

logger = get_logger(__name__)


class SeverityAgent:
    """Agent that assesses severity and impact of incidents."""
    
    def __init__(self, aws_client: AWSClient, strands_agent=None):
        """Initialize the severity assessment agent."""
        self.aws_client = aws_client
        self.strands_agent = strands_agent
    
    def assess_severity(
        self, 
        facts: List[Fact], 
        affected_resources: List[AffectedResource],
        hypotheses: List[Hypothesis]
    ) -> SeverityAssessment:
        """Assess incident severity using AI and heuristics."""
        
        
        # Heuristic-based severity scoring
        severity_score = self._calculate_heuristic_severity(facts, affected_resources)
        
        # Determine impact scope
        impact_scope = self._determine_impact_scope(affected_resources, facts)
        
        # Assess user impact
        user_impact = self._assess_user_impact(facts, affected_resources, impact_scope)
        
        # Use AI for final assessment and reasoning
        ai_assessment = self._get_ai_severity_assessment(facts, affected_resources, hypotheses, severity_score)
        
        return SeverityAssessment(
            severity=ai_assessment['severity'],
            impact_scope=impact_scope,
            affected_resource_count=len(affected_resources),
            user_impact=user_impact,
            confidence=ai_assessment['confidence'],
            reasoning=ai_assessment['reasoning']
        )
    
    def _calculate_heuristic_severity(self, facts: List[Fact], affected_resources: List[AffectedResource]) -> int:
        """Calculate severity score using heuristics."""
        severity_score = 0
        
        # Check for critical indicators in facts
        critical_keywords = ['error', 'failed', 'exception', 'timeout', 'denied', 'unauthorized']
        high_keywords = ['warning', 'degraded', 'slow', 'latency']
        
        for fact in facts:
            content_lower = fact.content.lower()
            
            # Critical indicators
            for keyword in critical_keywords:
                if keyword in content_lower:
                    severity_score += 3
                    break
            
            # High severity indicators
            for keyword in high_keywords:
                if keyword in content_lower:
                    severity_score += 1
                    break
        
        # Consider affected resource count and health status
        failed_resources = sum(1 for r in affected_resources if r.health_status == 'failed')
        degraded_resources = sum(1 for r in affected_resources if r.health_status == 'degraded')
        
        severity_score += failed_resources * 4  # Each failed resource adds significant severity
        severity_score += degraded_resources * 2  # Each degraded resource adds moderate severity
        
        # Consider total resource count
        if len(affected_resources) > 5:
            severity_score += 3  # System-wide impact
        elif len(affected_resources) > 2:
            severity_score += 2  # Service-level impact
        elif len(affected_resources) > 0:
            severity_score += 1  # Single resource impact
        
        return severity_score
    
    def _determine_impact_scope(self, affected_resources: List[AffectedResource], facts: List[Fact]) -> str:
        """Determine the scope of impact based on affected resources and facts."""
        
        if len(affected_resources) == 0:
            return "unknown"
        
        # Check for system-wide indicators in facts
        system_wide_keywords = ['system', 'platform', 'infrastructure', 'network', 'database']
        for fact in facts:
            content_lower = fact.content.lower()
            for keyword in system_wide_keywords:
                if keyword in content_lower and len(affected_resources) > 3:
                    return "system_wide"
        
        # Determine scope based on resource count and types
        if len(affected_resources) > 5:
            return "system_wide"
        elif len(affected_resources) > 2:
            return "service"
        else:
            return "single_resource"
    
    def _assess_user_impact(self, facts: List[Fact], affected_resources: List[AffectedResource], impact_scope: str) -> str:
        """Assess the impact on end users."""
        
        # Check for user-facing indicators
        user_impact_keywords = {
            'severe': ['down', 'unavailable', 'outage', 'complete failure', 'service unavailable'],
            'moderate': ['slow', 'degraded', 'intermittent', 'timeout', 'error'],
            'minimal': ['warning', 'minor', 'temporary', 'brief']
        }
        
        max_impact = 'none'
        for fact in facts:
            content_lower = fact.content.lower()
            for impact_level, keywords in user_impact_keywords.items():
                for keyword in keywords:
                    if keyword in content_lower:
                        if impact_level == 'severe':
                            return 'severe'
                        elif impact_level == 'moderate' and max_impact in ['none', 'minimal']:
                            max_impact = 'moderate'
                        elif impact_level == 'minimal' and max_impact == 'none':
                            max_impact = 'minimal'
        
        # Consider impact scope
        if impact_scope == "system_wide" and max_impact == 'none':
            max_impact = 'moderate'
        elif impact_scope == "service" and max_impact == 'none':
            max_impact = 'minimal'
        
        return max_impact
    
    def _get_ai_severity_assessment(
        self,
        facts: List[Fact],
        affected_resources: List[AffectedResource],
        hypotheses: List[Hypothesis],
        heuristic_score: int
    ) -> Dict[str, Any]:
        """Use AI to assess severity with detailed reasoning."""
        logger.info("Assessing severity using AI")

        # Try AI assessment first
        if self.strands_agent:
            try:
                return self._assess_severity_with_ai(facts, affected_resources, hypotheses, heuristic_score)
            except Exception as e:
                logger.error(f"AI severity assessment failed: {e}, using fallback")
                return self._assess_severity_fallback(heuristic_score)
        else:
            logger.warning("No Strands agent available, using fallback severity assessment")
            return self._assess_severity_fallback(heuristic_score)

    def _assess_severity_with_ai(
        self,
        facts: List[Fact],
        affected_resources: List[AffectedResource],
        hypotheses: List[Hypothesis],
        heuristic_score: int
    ) -> Dict[str, Any]:
        """Use Strands AI agent for severity assessment."""
        logger.info("🤖 Using AI for severity assessment")

        # Build context
        context = {
            "heuristic_score": heuristic_score,
            "affected_resources": len(affected_resources),
            "failed_resources": sum(1 for r in affected_resources if r.health_status == 'failed'),
            "degraded_resources": sum(1 for r in affected_resources if r.health_status == 'degraded'),
            "fact_count": len(facts),
            "hypothesis_count": len(hypotheses)
        }

        # Sample key data
        sample_facts = [f.content for f in facts[:5]]
        sample_hypotheses = [h.description for h in hypotheses[:3]]

        prompt = f"""You are an expert incident response analyst. Assess the severity of this AWS serverless incident.

CONTEXT:
- Heuristic severity score: {heuristic_score}/20
- Affected resources: {context['affected_resources']} (failed: {context['failed_resources']}, degraded: {context['degraded_resources']})
- Facts discovered: {context['fact_count']}
- Hypotheses generated: {context['hypothesis_count']}

KEY FACTS:
{chr(10).join(f"- {fact}" for fact in sample_facts)}

KEY HYPOTHESES:
{chr(10).join(f"- {hyp}" for hyp in sample_hypotheses)}

Determine:
1. Severity level: critical, high, medium, or low
2. Confidence in assessment: 0.0 to 1.0
3. Detailed reasoning for the assessment

Severity guidelines:
- critical: Service unavailable, data loss risk, customer-facing outage
- high: Significant degradation, errors affecting many users
- medium: Isolated issues, performance degradation
- low: Minor issues, warnings, or potential future problems

Respond with ONLY a JSON object:
{{
    "severity": "high",
    "confidence": 0.85,
    "reasoning": "Detailed explanation of why this severity level was chosen..."
}}"""

        try:
            # Use Strands agent
            response = self.strands_agent(prompt)

            # Cost tracking removed

            # Parse response
            ai_response = self._parse_severity_response(response)

            logger.info(f"✅ AI assessed severity as {ai_response['severity']} with confidence {ai_response['confidence']}")
            return ai_response

        except Exception as e:
            logger.error(f"Failed to get AI severity assessment: {e}")
            raise

    def _parse_severity_response(self, response: str) -> Dict[str, Any]:
        """Parse AI response for severity assessment."""
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

    def _assess_severity_fallback(self, heuristic_score: int) -> Dict[str, Any]:
        """Fallback severity assessment based on heuristic score."""
        logger.info("📊 Using fallback severity assessment")

        # Map heuristic score to severity
        if heuristic_score >= 15:
            severity = "critical"
            confidence = 0.8
            reasoning = "High heuristic score indicates critical severity"
        elif heuristic_score >= 10:
            severity = "high"
            confidence = 0.75
            reasoning = "Elevated heuristic score indicates high severity"
        elif heuristic_score >= 5:
            severity = "medium"
            confidence = 0.7
            reasoning = "Moderate heuristic score indicates medium severity"
        else:
            severity = "low"
            confidence = 0.65
            reasoning = "Low heuristic score indicates low severity"

        return {
            "severity": severity,
            "confidence": confidence,
            "reasoning": reasoning
        }
    
    def _build_severity_prompt(self, facts: List[Fact], affected_resources: List[AffectedResource], hypotheses: List[Hypothesis], severity_score: int) -> str:
        """Build a prompt for AI severity analysis."""
        
        facts_text = "\n".join([f"- {fact.content}" for fact in facts])
        resources_text = "\n".join([f"- {resource.resource_type}: {resource.resource_id}" for resource in affected_resources])
        hypotheses_text = "\n".join([f"- {hyp.type}: {hyp.description} (confidence: {hyp.confidence})" for hyp in hypotheses])
        
        prompt = f"""
Analyze the following incident and determine its severity level.

FACTS:
{facts_text}

AFFECTED RESOURCES:
{resources_text}

HYPOTHESES:
{hypotheses_text}

HEURISTIC SEVERITY SCORE: {severity_score}/20

Please provide a JSON response with:
{{
    "severity": "low|medium|high|critical",
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation of why this severity level was chosen..."
}}
"""
        return prompt
