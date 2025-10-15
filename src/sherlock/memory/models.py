#!/usr/bin/env python3
"""
Sherlock Core - Memory Data Models
Copyright (C) 2025 Christian Gennaro Faraone

Data models for graph-based RAG memory system.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class GraphNode:
    """Represents an AWS resource in the knowledge graph."""
    
    arn: str
    type: str  # lambda, stepfunctions, apigateway, etc.
    name: str
    account_id: str
    region: str
    tags: Dict[str, str] = field(default_factory=dict)
    observability: Dict[str, Any] = field(default_factory=dict)  # log_group, xray_name, metric_namespace
    config_fingerprint: Dict[str, Any] = field(default_factory=dict)  # hash, updated_at
    versions: Dict[str, Any] = field(default_factory=dict)
    staleness: Dict[str, Any] = field(default_factory=dict)  # last_seen, flag
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'arn': self.arn,
            'type': self.type,
            'name': self.name,
            'account_id': self.account_id,
            'region': self.region,
            'tags': self.tags,
            'observability': self.observability,
            'config_fingerprint': self.config_fingerprint,
            'versions': self.versions,
            'staleness': self.staleness
        }


@dataclass
class GraphEdge:
    """Represents a relationship between AWS resources."""
    
    from_arn: str
    to_arn: str
    rel: str  # CALLS, READS, WRITES, PUBLISHES, SUBSCRIBES, TRIGGERS, DEPLOYED_BY
    evidence_sources: List[str]  # X_RAY, CONFIG, LOGS, HEURISTIC
    confidence: float
    first_seen: str
    last_seen: str
    account_id: str
    region: str
    
    @property
    def edge_id(self) -> str:
        """Generate deterministic edge ID using SHA1 hash."""
        import hashlib
        content = f"{self.from_arn}|{self.rel}|{self.to_arn}"
        return hashlib.sha1(content.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'from_arn': self.from_arn,
            'to_arn': self.to_arn,
            'rel': self.rel,
            'evidence_sources': self.evidence_sources,
            'confidence': self.confidence,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'account_id': self.account_id,
            'region': self.region
        }


@dataclass
class ConfigSnapshot:
    """Resource configuration snapshot with versioning."""
    
    arn: str
    hash: str  # SHA256 of config content
    current: bool
    type: str
    attrs: Dict[str, Any]
    blob_s3: Optional[str] = None
    collected_at: str = ""
    account_id: str = ""
    region: str = ""
    
    @property
    def config_id(self) -> str:
        """Generate deterministic config ID."""
        return f"{self.arn}|{self.hash}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'arn': self.arn,
            'hash': self.hash,
            'current': self.current,
            'type': self.type,
            'attrs': self.attrs,
            'blob_s3': self.blob_s3,
            'collected_at': self.collected_at,
            'account_id': self.account_id,
            'region': self.region
        }


@dataclass
class ObservabilityPointer:
    """Maps ARN to observability data sources."""
    
    arn: str
    logs: Optional[str] = None  # log group
    traces: Dict[str, Any] = field(default_factory=dict)  # xray_name, last_trace_ids
    metrics: Dict[str, Any] = field(default_factory=dict)  # namespace, names
    account_id: str = ""
    region: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'arn': self.arn,
            'logs': self.logs,
            'traces': self.traces,
            'metrics': self.metrics,
            'account_id': self.account_id,
            'region': self.region,
            'updated_at': self.updated_at
        }


@dataclass
class Pattern:
    """Playbook/pattern with structural signatures for matching."""
    
    pattern_id: str
    title: str
    tags: List[str]
    signatures: Dict[str, Any]  # topology_signature, resource_types, relationship_types, depth, stack_signature, topology_motif
    playbook_steps: str
    popularity: float = 0.0
    last_used_at: str = ""
    match_count: int = 0  # Track usage for learning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'pattern_id': self.pattern_id,
            'title': self.title,
            'tags': self.tags,
            'signatures': self.signatures,
            'playbook_steps': self.playbook_steps,
            'popularity': self.popularity,
            'last_used_at': self.last_used_at,
            'match_count': self.match_count
        }


@dataclass
class Incident:
    """Past RCA investigation result."""
    
    incident_id: str
    nodes: List[str]  # ARNs involved
    root_cause: str
    signals: List[str]
    fix: str
    useful_queries: str
    pattern_ids: List[str]
    created_at: str
    account_id: str = ""
    region: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'incident_id': self.incident_id,
            'nodes': self.nodes,
            'root_cause': self.root_cause,
            'signals': self.signals,
            'fix': self.fix,
            'useful_queries': self.useful_queries,
            'pattern_ids': self.pattern_ids,
            'created_at': self.created_at,
            'account_id': self.account_id,
            'region': self.region
        }


@dataclass
class ChangeEvent:
    """Configuration or topology change event."""
    
    event_id: str
    changed_arn: str
    change_type: str
    diff_hash: str
    timestamp: str
    actor: str
    links: Dict[str, Any] = field(default_factory=dict)
    account_id: str = ""
    region: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenSearch indexing."""
        return {
            'event_id': self.event_id,
            'changed_arn': self.changed_arn,
            'change_type': self.change_type,
            'diff_hash': self.diff_hash,
            'timestamp': self.timestamp,
            'actor': self.actor,
            'links': self.links,
            'account_id': self.account_id,
            'region': self.region
        }


@dataclass
class SubGraphResult:
    """Output structure for RAG retrieval containing complete context."""
    
    focus_node: str
    subgraph: Dict[str, Any]  # nodes and edges
    observability: Dict[str, Any]  # ARN -> observability data
    config_diff: List[Dict[str, Any]]  # current vs previous configs
    patterns: List[Dict[str, Any]]  # matched patterns with scores
    related_incidents: List[Dict[str, Any]]  # similar past incidents
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'focus_node': self.focus_node,
            'subgraph': self.subgraph,
            'observability': self.observability,
            'config_diff': self.config_diff,
            'patterns': self.patterns,
            'related_incidents': self.related_incidents
        }


# Legacy model for backward compatibility during transition
@dataclass
class MemoryResult:
    """Legacy result from memory query representing a past investigation."""
    
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
