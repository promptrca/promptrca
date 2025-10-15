#!/usr/bin/env python3
"""
Tests for Memory Data Models
"""

import pytest
from datetime import datetime, timezone
from src.sherlock.memory.models import (
    GraphNode, GraphEdge, ConfigSnapshot, ObservabilityPointer,
    Pattern, Incident, ChangeEvent, SubGraphResult, MemoryResult
)


class TestGraphNode:
    """Test GraphNode model functionality."""
    
    def test_graph_node_creation(self):
        """Test creating a GraphNode with all fields."""
        node = GraphNode(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            type="lambda",
            name="test-function",
            account_id="123456789012",
            region="eu-west-1",
            tags={"Environment": "prod", "Team": "backend"},
            observability={"log_group": "/aws/lambda/test-function"},
            config_fingerprint={"hash": "abc123"},
            versions={"current": "1.0.0"},
            staleness={"last_seen": "2025-01-15T10:30:00Z", "flag": False}
        )
        
        assert node.arn == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert node.type == "lambda"
        assert node.name == "test-function"
        assert node.tags["Environment"] == "prod"
        assert node.observability["log_group"] == "/aws/lambda/test-function"
    
    def test_graph_node_to_dict(self):
        """Test converting GraphNode to dictionary."""
        node = GraphNode(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            type="lambda",
            name="test-function",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        node_dict = node.to_dict()
        
        assert node_dict["arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert node_dict["type"] == "lambda"
        assert node_dict["name"] == "test-function"
        assert node_dict["account_id"] == "123456789012"
        assert node_dict["region"] == "eu-west-1"
        assert isinstance(node_dict["tags"], dict)
        assert isinstance(node_dict["observability"], dict)


class TestGraphEdge:
    """Test GraphEdge model functionality."""
    
    def test_graph_edge_creation(self):
        """Test creating a GraphEdge with all fields."""
        edge = GraphEdge(
            from_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            to_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
            rel="READS",
            evidence_sources=["X_RAY", "LOGS"],
            confidence=0.85,
            first_seen="2025-01-15T10:30:00Z",
            last_seen="2025-01-15T10:35:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        assert edge.from_arn == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert edge.to_arn == "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table"
        assert edge.rel == "READS"
        assert "X_RAY" in edge.evidence_sources
        assert edge.confidence == 0.85
    
    def test_graph_edge_id_generation(self):
        """Test deterministic edge ID generation."""
        edge1 = GraphEdge(
            from_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            to_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
            rel="READS",
            evidence_sources=["X_RAY"],
            confidence=0.85,
            first_seen="2025-01-15T10:30:00Z",
            last_seen="2025-01-15T10:35:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        edge2 = GraphEdge(
            from_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            to_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
            rel="READS",
            evidence_sources=["LOGS"],  # Different evidence sources
            confidence=0.90,  # Different confidence
            first_seen="2025-01-15T11:00:00Z",  # Different timestamps
            last_seen="2025-01-15T11:05:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        # Edge ID should be the same for same from_arn, rel, to_arn
        assert edge1.edge_id == edge2.edge_id
        assert len(edge1.edge_id) == 40  # SHA1 hex length
    
    def test_graph_edge_to_dict(self):
        """Test converting GraphEdge to dictionary."""
        edge = GraphEdge(
            from_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            to_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
            rel="READS",
            evidence_sources=["X_RAY"],
            confidence=0.85,
            first_seen="2025-01-15T10:30:00Z",
            last_seen="2025-01-15T10:35:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        edge_dict = edge.to_dict()
        
        assert edge_dict["from_arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert edge_dict["rel"] == "READS"
        assert edge_dict["confidence"] == 0.85
        assert "X_RAY" in edge_dict["evidence_sources"]


class TestConfigSnapshot:
    """Test ConfigSnapshot model functionality."""
    
    def test_config_snapshot_creation(self):
        """Test creating a ConfigSnapshot."""
        snapshot = ConfigSnapshot(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            hash="abc123def456",
            current=True,
            type="lambda",
            attrs={"timeout": 30, "memory": 512},
            blob_s3="s3://config-bucket/lambda-configs/test-function.json",
            collected_at="2025-01-15T10:30:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        assert snapshot.arn == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert snapshot.hash == "abc123def456"
        assert snapshot.current is True
        assert snapshot.type == "lambda"
        assert snapshot.attrs["timeout"] == 30
    
    def test_config_snapshot_id_generation(self):
        """Test config ID generation."""
        snapshot = ConfigSnapshot(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            hash="abc123def456",
            current=True,
            type="lambda",
            attrs={}
        )
        
        expected_id = "arn:aws:lambda:eu-west-1:123456789012:function:test-function|abc123def456"
        assert snapshot.config_id == expected_id
    
    def test_config_snapshot_to_dict(self):
        """Test converting ConfigSnapshot to dictionary."""
        snapshot = ConfigSnapshot(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            hash="abc123def456",
            current=True,
            type="lambda",
            attrs={"timeout": 30}
        )
        
        snapshot_dict = snapshot.to_dict()
        
        assert snapshot_dict["arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert snapshot_dict["hash"] == "abc123def456"
        assert snapshot_dict["current"] is True
        assert snapshot_dict["type"] == "lambda"


class TestObservabilityPointer:
    """Test ObservabilityPointer model functionality."""
    
    def test_observability_pointer_creation(self):
        """Test creating an ObservabilityPointer."""
        pointer = ObservabilityPointer(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            logs="/aws/lambda/test-function",
            traces={"xray_name": "test-function", "last_trace_ids": ["trace-123"]},
            metrics={"namespace": "AWS/Lambda", "names": ["Duration", "Errors"]},
            account_id="123456789012",
            region="eu-west-1",
            updated_at="2025-01-15T10:30:00Z"
        )
        
        assert pointer.arn == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert pointer.logs == "/aws/lambda/test-function"
        assert pointer.traces["xray_name"] == "test-function"
        assert "trace-123" in pointer.traces["last_trace_ids"]
        assert pointer.metrics["namespace"] == "AWS/Lambda"
    
    def test_observability_pointer_to_dict(self):
        """Test converting ObservabilityPointer to dictionary."""
        pointer = ObservabilityPointer(
            arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            logs="/aws/lambda/test-function",
            traces={"xray_name": "test-function"},
            metrics={"namespace": "AWS/Lambda"}
        )
        
        pointer_dict = pointer.to_dict()
        
        assert pointer_dict["arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert pointer_dict["logs"] == "/aws/lambda/test-function"
        assert pointer_dict["traces"]["xray_name"] == "test-function"
        assert pointer_dict["metrics"]["namespace"] == "AWS/Lambda"


class TestPattern:
    """Test Pattern model functionality."""
    
    def test_pattern_creation(self):
        """Test creating a Pattern."""
        pattern = Pattern(
            pattern_id="P-001",
            title="Lambda Timeout Pattern",
            tags=["lambda", "timeout", "dynamodb"],
            signatures={
                "topology_signature": "a3f5e8c2d1b4a7e9",
                "resource_types": ["lambda", "dynamodb"],
                "relationship_types": ["READS"],
                "depth": 1,
                "stack_signature": "lambda-dynamodb:READS",
                "topology_motif": ["lambda->dynamodb(READS)"]
            },
            playbook_steps="1. Check DynamoDB capacity\n2. Increase Lambda timeout",
            popularity=0.85,
            last_used_at="2025-01-15T10:30:00Z",
            match_count=5
        )
        
        assert pattern.pattern_id == "P-001"
        assert pattern.title == "Lambda Timeout Pattern"
        assert "lambda" in pattern.tags
        assert pattern.signatures["topology_signature"] == "a3f5e8c2d1b4a7e9"
        assert pattern.signatures["resource_types"] == ["lambda", "dynamodb"]
        assert pattern.popularity == 0.85
        assert pattern.match_count == 5
    
    def test_pattern_to_dict(self):
        """Test converting Pattern to dictionary."""
        pattern = Pattern(
            pattern_id="P-001",
            title="Lambda Timeout Pattern",
            tags=["lambda", "timeout"],
            signatures={
                "topology_signature": "a3f5e8c2d1b4a7e9",
                "resource_types": ["lambda", "dynamodb"],
                "relationship_types": ["READS"],
                "depth": 1,
                "stack_signature": "lambda-dynamodb:READS"
            },
            playbook_steps="Check capacity",
            match_count=2
        )
        
        pattern_dict = pattern.to_dict()
        
        assert pattern_dict["pattern_id"] == "P-001"
        assert pattern_dict["title"] == "Lambda Timeout Pattern"
        assert "lambda" in pattern_dict["tags"]
        assert pattern_dict["match_count"] == 2


class TestIncident:
    """Test Incident model functionality."""
    
    def test_incident_creation(self):
        """Test creating an Incident."""
        incident = Incident(
            incident_id="INC-001",
            nodes=["arn:aws:lambda:eu-west-1:123456789012:function:test-function"],
            root_cause="Lambda timeout due to DynamoDB throttling",
            signals=["timeout", "throttling", "high latency"],
            fix="Increase DynamoDB capacity and optimize Lambda function",
            useful_queries="CloudWatch metrics, X-Ray traces",
            pattern_ids=["P-001", "P-002"],
            created_at="2025-01-15T10:30:00Z",
            account_id="123456789012",
            region="eu-west-1"
        )
        
        assert incident.incident_id == "INC-001"
        assert "arn:aws:lambda:eu-west-1:123456789012:function:test-function" in incident.nodes
        assert incident.root_cause == "Lambda timeout due to DynamoDB throttling"
        assert "timeout" in incident.signals
        assert "P-001" in incident.pattern_ids
    
    def test_incident_to_dict(self):
        """Test converting Incident to dictionary."""
        incident = Incident(
            incident_id="INC-001",
            nodes=["arn:aws:lambda:eu-west-1:123456789012:function:test-function"],
            root_cause="Lambda timeout",
            signals=["timeout"],
            fix="Increase capacity",
            useful_queries="Check metrics",
            pattern_ids=["P-001"],
            created_at="2025-01-15T10:30:00Z"
        )
        
        incident_dict = incident.to_dict()
        
        assert incident_dict["incident_id"] == "INC-001"
        assert "arn:aws:lambda:eu-west-1:123456789012:function:test-function" in incident_dict["nodes"]
        assert incident_dict["root_cause"] == "Lambda timeout"
        assert "timeout" in incident_dict["signals"]


class TestChangeEvent:
    """Test ChangeEvent model functionality."""
    
    def test_change_event_creation(self):
        """Test creating a ChangeEvent."""
        event = ChangeEvent(
            event_id="EVT-001",
            changed_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            change_type="CONFIG_UPDATE",
            diff_hash="def456ghi789",
            timestamp="2025-01-15T10:30:00Z",
            actor="user@example.com",
            links={"cloudformation": "stack-123"},
            account_id="123456789012",
            region="eu-west-1"
        )
        
        assert event.event_id == "EVT-001"
        assert event.changed_arn == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert event.change_type == "CONFIG_UPDATE"
        assert event.diff_hash == "def456ghi789"
        assert event.actor == "user@example.com"
        assert event.links["cloudformation"] == "stack-123"
    
    def test_change_event_to_dict(self):
        """Test converting ChangeEvent to dictionary."""
        event = ChangeEvent(
            event_id="EVT-001",
            changed_arn="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            change_type="CONFIG_UPDATE",
            diff_hash="def456ghi789",
            timestamp="2025-01-15T10:30:00Z",
            actor="user@example.com"
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_id"] == "EVT-001"
        assert event_dict["changed_arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert event_dict["change_type"] == "CONFIG_UPDATE"
        assert event_dict["actor"] == "user@example.com"


class TestSubGraphResult:
    """Test SubGraphResult model functionality."""
    
    def test_subgraph_result_creation(self):
        """Test creating a SubGraphResult."""
        result = SubGraphResult(
            focus_node="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            subgraph={
                "nodes": [{"arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function"}],
                "edges": [{"from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function", "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table"}]
            },
            observability={"arn:aws:lambda:eu-west-1:123456789012:function:test-function": {"log_group": "/aws/lambda/test-function"}},
            config_diff=[{"arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function", "changes": ["timeout"]}],
            patterns=[{"pattern_id": "P-001", "title": "Lambda Timeout Pattern"}],
            related_incidents=[{"incident_id": "INC-001", "root_cause": "Lambda timeout"}]
        )
        
        assert result.focus_node == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert len(result.subgraph["nodes"]) == 1
        assert len(result.subgraph["edges"]) == 1
        assert len(result.observability) == 1
        assert len(result.config_diff) == 1
        assert len(result.patterns) == 1
        assert len(result.related_incidents) == 1
    
    def test_subgraph_result_to_dict(self):
        """Test converting SubGraphResult to dictionary."""
        result = SubGraphResult(
            focus_node="arn:aws:lambda:eu-west-1:123456789012:function:test-function",
            subgraph={"nodes": [], "edges": []},
            observability={},
            config_diff=[],
            patterns=[],
            related_incidents=[]
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["focus_node"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        assert "subgraph" in result_dict
        assert "observability" in result_dict
        assert "config_diff" in result_dict
        assert "patterns" in result_dict
        assert "related_incidents" in result_dict


class TestMemoryResult:
    """Test MemoryResult legacy model functionality."""
    
    def test_memory_result_from_hit(self):
        """Test parsing OpenSearch hit into MemoryResult."""
        hit = {
            "_score": 0.95,
            "_source": {
                "investigation_id": "inv-123",
                "resource_type": "lambda",
                "resource_name": "payment-processor",
                "error_type": "timeout",
                "root_cause_summary": "Lambda timeout due to cold start",
                "advice_summary": "Increase memory allocation",
                "outcome": "resolved",
                "quality_score": 0.85,
                "created_at": "2025-01-15T10:30:00Z"
            }
        }
        
        result = MemoryResult.from_hit(hit)
        
        assert result.investigation_id == "inv-123"
        assert result.similarity_score == 0.95
        assert result.resource_type == "lambda"
        assert result.resource_name == "payment-processor"
        assert result.error_type == "timeout"
        assert result.outcome == "resolved"
        assert result.quality_score == 0.85
    
    def test_memory_result_from_hit_missing_fields(self):
        """Test parsing OpenSearch hit with missing fields."""
        hit = {
            "_score": 0.8,
            "_source": {
                "investigation_id": "inv-456"
                # Missing other fields
            }
        }
        
        result = MemoryResult.from_hit(hit)
        
        assert result.investigation_id == "inv-456"
        assert result.similarity_score == 0.8
        assert result.resource_type == ""  # Default empty string
        assert result.resource_name == ""
        assert result.error_type == ""
        assert result.outcome == "unknown"  # Default value
        assert result.quality_score == 0.0  # Default value
    
    def test_memory_result_to_dict(self):
        """Test converting MemoryResult to dictionary."""
        result = MemoryResult(
            investigation_id="inv-789",
            similarity_score=0.88,
            resource_type="dynamodb",
            resource_name="orders-table",
            error_type="throttling",
            root_cause_summary="Insufficient read capacity",
            advice_summary="Enable auto-scaling",
            outcome="resolved",
            quality_score=0.92,
            created_at="2025-01-16T14:20:00Z"
        )
        
        result_dict = result.to_dict()
        
        assert result_dict["investigation_id"] == "inv-789"
        assert result_dict["similarity_score"] == 0.88
        assert result_dict["resource_type"] == "dynamodb"
        assert result_dict["resource_name"] == "orders-table"
        assert result_dict["error_type"] == "throttling"
        assert result_dict["outcome"] == "resolved"
        assert result_dict["quality_score"] == 0.92
