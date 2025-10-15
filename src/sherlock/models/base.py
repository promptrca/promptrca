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

Data models and classes for Sherlock AI Root-Cause Investigator
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import json


@dataclass
class Fact:
    """Represents a fact discovered during investigation."""
    source: str
    content: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source": self.source,
            "content": self.content,
            "confidence": self.confidence,
            "metadata": self.metadata
        }


@dataclass
class Hypothesis:
    """Represents a hypothesis about the root cause."""
    type: str
    description: str
    confidence: float = 0.5
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence
        }


@dataclass
class Advice:
    """Represents actionable advice for remediation."""
    title: str
    description: str
    priority: str = "medium"
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "category": self.category
        }


@dataclass
class InvestigationReport:
    """Complete investigation report with all findings."""
    run_id: str
    status: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    
    # New: Affected Resources
    affected_resources: List['AffectedResource']
    
    # New: Severity & Impact
    severity_assessment: 'SeverityAssessment'
    
    # Existing (enhanced)
    facts: List[Fact]
    
    # New: Enhanced Root Cause
    root_cause_analysis: 'RootCauseAnalysis'
    
    # Existing
    hypotheses: List[Hypothesis]
    advice: List[Advice]
    
    # New: Timeline
    timeline: List['EventTimeline']
    
    summary: str

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
            "severity": self.severity_assessment.to_dict(),
            "affected_resources": {
                "count": len(self.affected_resources),
                "resources": [r.to_dict() for r in self.affected_resources]
            },
            "root_cause": self.root_cause_analysis.to_dict(),
            "timeline": [e.to_dict() for e in self.timeline],
            "facts": {
                "count": len(self.facts),
                "items": [f.to_dict() for f in self.facts]
            },
            "hypotheses": {
                "count": len(self.hypotheses),
                "items": [h.to_dict() for h in self.hypotheses]
            },
            "remediation": {
                "count": len(self.advice),
                "recommendations": [a.to_dict() for a in self.advice]
            },
            "summary": json.loads(self.summary) if isinstance(self.summary, str) and self.summary.startswith('{') else self.summary
        }




@dataclass
class AffectedResource:
    """Represents an AWS resource involved in the incident."""
    resource_type: str  # lambda, stepfunctions, apigateway, etc.
    resource_id: str  # ARN or ID
    resource_name: str
    health_status: str  # healthy, degraded, failed, unknown
    detected_issues: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "health_status": self.health_status,
            "detected_issues": self.detected_issues,
            "metadata": self.metadata
        }


@dataclass
class SeverityAssessment:
    """Severity and impact assessment."""
    severity: str  # critical, high, medium, low
    impact_scope: str  # single_resource, service, system_wide
    affected_resource_count: int
    user_impact: str  # none, minimal, moderate, severe
    confidence: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "severity": self.severity,
            "impact_scope": self.impact_scope,
            "affected_resource_count": self.affected_resource_count,
            "user_impact": self.user_impact,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


@dataclass
class RootCauseAnalysis:
    """Enhanced root cause analysis."""
    primary_root_cause: Optional[Hypothesis]
    contributing_factors: List[Hypothesis]
    confidence_score: float
    analysis_summary: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "primary_root_cause": self.primary_root_cause.to_dict() if self.primary_root_cause else None,
            "contributing_factors": [h.to_dict() for h in self.contributing_factors],
            "confidence_score": self.confidence_score,
            "analysis_summary": self.analysis_summary
        }


@dataclass
class EventTimeline:
    """Timeline of events during incident."""
    timestamp: datetime
    event_type: str  # detection, analysis, finding
    component: str
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "component": self.component,
            "description": self.description,
            "metadata": self.metadata
        }


@dataclass
class InvestigationTarget:
    """Represents the target of investigation."""
    type: str
    name: str
    region: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "name": self.name,
            "region": self.region,
            "metadata": self.metadata
        }
