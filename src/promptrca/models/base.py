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

Data models and classes for PromptRCA AI Root-Cause Investigator
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import json


class Fact(BaseModel):
    """Represents a fact discovered during investigation."""
    source: str = Field(description="The source agent or component that discovered this fact")
    content: str = Field(description="The actual fact content or finding")
    confidence: float = Field(default=1.0, description="Confidence level in this fact (0.0 to 1.0)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about this fact")


class Hypothesis(BaseModel):
    """Represents a hypothesis about the root cause."""
    type: str = Field(description="The type of hypothesis (e.g., 'root_cause_analysis', 'investigation_summary')")
    description: str = Field(description="Detailed description of the hypothesis")
    confidence: float = Field(default=0.5, description="Confidence level in this hypothesis (0.0 to 1.0)")
    evidence: List[str] = Field(default_factory=list, description="List of evidence supporting this hypothesis")


class Advice(BaseModel):
    """Represents actionable advice for remediation."""
    title: str = Field(description="Title of the advice or recommendation")
    description: str = Field(description="Detailed description of the advice")
    priority: str = Field(default="medium", description="Priority level: low, medium, high, critical")
    category: str = Field(default="general", description="Category of the advice (e.g., 'general', 'security', 'performance')")


class InvestigationReport(BaseModel):
    """Complete investigation report with all findings."""
    run_id: str = Field(description="Unique identifier for this investigation run")
    status: str = Field(description="Status of the investigation: completed, failed, in_progress")
    started_at: datetime = Field(description="When the investigation started")
    completed_at: datetime = Field(description="When the investigation completed")
    duration_seconds: float = Field(description="Total duration of the investigation in seconds")
    
    # New: Affected Resources
    affected_resources: List['AffectedResource'] = Field(description="List of AWS resources affected by the incident")
    
    # New: Severity & Impact
    severity_assessment: Optional['SeverityAssessment'] = Field(default=None, description="Assessment of severity and impact")
    
    # Existing (enhanced)
    facts: List[Fact] = Field(description="List of facts discovered during investigation")
    
    # New: Enhanced Root Cause
    root_cause_analysis: Optional['RootCauseAnalysis'] = Field(default=None, description="Root cause analysis findings")
    
    # Existing
    hypotheses: List[Hypothesis] = Field(description="List of hypotheses about the root cause")
    advice: List[Advice] = Field(description="List of remediation advice and recommendations")
    
    # New: Timeline
    timeline: List['EventTimeline'] = Field(description="Timeline of events during the investigation")
    
    summary: str = Field(description="Summary of the investigation findings")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured JSON following industry standards."""
        return {
            "investigation": {
                "id": self.run_id,
                "status": self.status,
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat(),
                "duration_seconds": self.duration_seconds
            },
            "severity": self.severity_assessment.model_dump(mode='json') if self.severity_assessment else {
                "severity": "unknown",
                "impact_scope": "unknown",
                "affected_resource_count": 0,
                "user_impact": "unknown",
                "confidence": 0.0,
                "reasoning": "Investigation failed"
            },
            "affected_resources": {
                "count": len(self.affected_resources),
                "resources": [r.model_dump(mode='json') for r in self.affected_resources]
            },
            "root_cause": self.root_cause_analysis.model_dump(mode='json') if self.root_cause_analysis else {
                "primary_root_cause": None,
                "contributing_factors": [],
                "confidence_score": 0.0,
                "analysis_summary": "Investigation failed"
            },
            "timeline": [e.model_dump(mode='json') for e in self.timeline],
            "facts": {
                "count": len(self.facts),
                "items": [f.model_dump(mode='json') for f in self.facts]
            },
            "hypotheses": {
                "count": len(self.hypotheses),
                "items": [h.model_dump(mode='json') for h in self.hypotheses]
            },
            "remediation": {
                "count": len(self.advice),
                "recommendations": [a.model_dump(mode='json') for a in self.advice]
            },
            "summary": json.loads(self.summary) if isinstance(self.summary, str) and self.summary.startswith('{') else self.summary
        }




class AffectedResource(BaseModel):
    """Represents an AWS resource involved in the incident."""
    resource_type: str = Field(description="Type of AWS resource (e.g., lambda, stepfunctions, apigateway)")
    resource_id: str = Field(description="ARN or ID of the resource")
    resource_name: str = Field(description="Name of the resource")
    health_status: str = Field(description="Health status: healthy, degraded, failed, unknown")
    detected_issues: List[str] = Field(description="List of issues detected in this resource")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the resource")


class SeverityAssessment(BaseModel):
    """Severity and impact assessment."""
    severity: str = Field(description="Severity level: critical, high, medium, low")
    impact_scope: str = Field(description="Scope of impact: single_resource, service, system_wide")
    affected_resource_count: int = Field(description="Number of resources affected")
    user_impact: str = Field(description="User impact level: none, minimal, moderate, severe")
    confidence: float = Field(description="Confidence in this assessment (0.0 to 1.0)")
    reasoning: str = Field(description="Reasoning behind this severity assessment")


class RootCauseAnalysis(BaseModel):
    """Enhanced root cause analysis."""
    primary_root_cause: Optional[Hypothesis] = Field(default=None, description="The primary root cause hypothesis")
    contributing_factors: List[Hypothesis] = Field(description="List of contributing factor hypotheses")
    confidence_score: float = Field(description="Overall confidence in this root cause analysis (0.0 to 1.0)")
    analysis_summary: str = Field(description="Summary of the root cause analysis")


class EventTimeline(BaseModel):
    """Timeline of events during incident."""
    timestamp: datetime = Field(description="When this event occurred")
    event_type: str = Field(description="Type of event: detection, analysis, finding")
    component: str = Field(description="Component that generated this event")
    description: str = Field(description="Description of what happened")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about this event")


class InvestigationTarget(BaseModel):
    """Represents the target of investigation."""
    type: str = Field(description="Type of investigation target")
    name: str = Field(description="Name of the target")
    region: str = Field(description="AWS region of the target")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the target")


# Update forward references for Pydantic
InvestigationReport.model_rebuild()
AffectedResource.model_rebuild()
SeverityAssessment.model_rebuild()
RootCauseAnalysis.model_rebuild()
EventTimeline.model_rebuild()
