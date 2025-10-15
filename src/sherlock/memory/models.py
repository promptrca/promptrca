#!/usr/bin/env python3
"""
Sherlock Core - Memory Data Models
Copyright (C) 2025 Christian Gennaro Faraone

Data models for memory system responses.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class MemoryResult:
    """Result from memory query representing a past investigation."""
    
    investigation_id: str
    similarity_score: float
    resource_type: str
    resource_name: str
    error_type: str
    root_cause_summary: str
    advice_summary: str
    outcome: str  # "resolved", "partial", "unresolved", "unknown"
    quality_score: float
    created_at: str
    
    @classmethod
    def from_hit(cls, hit: Dict[str, Any]) -> 'MemoryResult':
        """Parse OpenSearch hit into MemoryResult.
        
        Args:
            hit: OpenSearch hit document with _source and _score
            
        Returns:
            MemoryResult instance
        """
        source = hit.get('_source', {})
        return cls(
            investigation_id=source.get('investigation_id', ''),
            similarity_score=hit.get('_score', 0.0),
            resource_type=source.get('resource_type', ''),
            resource_name=source.get('resource_name', ''),
            error_type=source.get('error_type', ''),
            root_cause_summary=source.get('root_cause_summary', ''),
            advice_summary=source.get('advice_summary', ''),
            outcome=source.get('outcome', 'unknown'),
            quality_score=source.get('quality_score', 0.0),
            created_at=source.get('created_at', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'investigation_id': self.investigation_id,
            'similarity_score': self.similarity_score,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'error_type': self.error_type,
            'root_cause_summary': self.root_cause_summary,
            'advice_summary': self.advice_summary,
            'outcome': self.outcome,
            'quality_score': self.quality_score,
            'created_at': self.created_at
        }
