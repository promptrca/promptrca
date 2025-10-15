#!/usr/bin/env python3
"""
Tests for Memory Client
"""

import pytest
from src.sherlock.memory import MemoryClient, MemoryResult


def test_memory_client_disabled():
    """Test that memory client gracefully handles being disabled."""
    client = MemoryClient({"enabled": False, "endpoint": ""})
    assert not client.enabled


def test_memory_client_enabled():
    """Test that memory client is enabled with valid endpoint."""
    client = MemoryClient({
        "enabled": True,
        "endpoint": "https://memory-api.example.com",
        "auth_type": "api_key",
        "api_key": "test-key"
    })
    assert client.enabled
    assert client.endpoint == "https://memory-api.example.com"


def test_memory_result_from_hit():
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


def test_memory_result_to_dict():
    """Test converting MemoryResult to dictionary."""
    result = MemoryResult(
        investigation_id="inv-456",
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
    
    assert result_dict["investigation_id"] == "inv-456"
    assert result_dict["similarity_score"] == 0.88
    assert result_dict["resource_type"] == "dynamodb"
    assert result_dict["outcome"] == "resolved"


@pytest.mark.asyncio
async def test_find_similar_when_disabled():
    """Test that find_similar returns empty list when disabled."""
    client = MemoryClient({"enabled": False, "endpoint": ""})
    
    results = await client.find_similar(
        query="Lambda timeout error",
        filters={"resource_type": "lambda"},
        limit=5
    )
    
    assert results == []
    assert isinstance(results, list)


def test_auth_headers_api_key():
    """Test API key authentication headers."""
    client = MemoryClient({
        "enabled": True,
        "endpoint": "https://memory-api.example.com",
        "auth_type": "api_key",
        "api_key": "test-api-key-123"
    })
    
    headers = client._auth_headers()
    
    assert "Authorization" in headers
    assert headers["Authorization"] == "ApiKey test-api-key-123"


def test_auth_headers_no_key():
    """Test authentication headers when no key provided."""
    client = MemoryClient({
        "enabled": True,
        "endpoint": "https://memory-api.example.com",
        "auth_type": "api_key",
        "api_key": ""
    })
    
    headers = client._auth_headers()
    
    assert headers == {}

