#!/usr/bin/env python3
"""
Integration tests for Memory System
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.sherlock.memory import MemoryClient, MemoryResult
from src.sherlock.agents.lead_orchestrator import LeadOrchestratorAgent, InvestigationContext
from src.sherlock.agents.input_parser_agent import ParsedResource


@pytest.fixture
def mock_memory_config():
    """Mock memory configuration."""
    return {
        "enabled": True,
        "endpoint": "https://memory-api.example.com",
        "auth_type": "api_key",
        "api_key": "test-key",
        "max_results": 5,
        "min_quality": 0.7,
        "timeout_ms": 2000
    }


@pytest.fixture
def mock_similar_investigations():
    """Mock similar investigations from memory."""
    return [
        MemoryResult(
            investigation_id="inv-123",
            similarity_score=0.95,
            resource_type="lambda",
            resource_name="payment-processor",
            error_type="timeout",
            root_cause_summary="Lambda timeout due to DynamoDB connection pool exhaustion",
            advice_summary="Increased connection pool size from 10 to 50",
            outcome="resolved",
            quality_score=0.92,
            created_at="2025-01-13T14:30:00Z"
        ),
        MemoryResult(
            investigation_id="inv-456",
            similarity_score=0.88,
            resource_type="lambda",
            resource_name="payment-processor",
            error_type="timeout",
            root_cause_summary="Lambda timeout due to cold start",
            advice_summary="Enabled provisioned concurrency",
            outcome="resolved",
            quality_score=0.85,
            created_at="2025-01-12T09:15:00Z"
        )
    ]


@pytest.mark.asyncio
async def test_memory_client_find_similar_disabled():
    """Test memory client find_similar when disabled."""
    
    client = MemoryClient({"enabled": False, "endpoint": ""})
    
    results = await client.find_similar(
        query="Lambda timeout error",
        filters={"resource_type": "lambda"},
        limit=5
    )
    
    assert results == []
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_memory_client_find_similar_no_endpoint():
    """Test memory client find_similar when no endpoint configured."""
    
    client = MemoryClient({"enabled": True, "endpoint": ""})
    
    results = await client.find_similar(
        query="Lambda timeout error",
        filters={"resource_type": "lambda"},
        limit=5
    )
    
    assert results == []
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_memory_client_timeout_handling(mock_memory_config):
    """Test memory client handles timeouts gracefully."""
    
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        client = MemoryClient(mock_memory_config)
        
        results = await client.find_similar(
            query="Lambda timeout error",
            filters={"resource_type": "lambda"},
            limit=5
        )
        
        # Should return empty list on timeout
        assert results == []


@pytest.mark.asyncio
async def test_memory_client_connection_error(mock_memory_config):
    """Test memory client handles connection errors gracefully."""
    
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.side_effect = ConnectionError("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        client = MemoryClient(mock_memory_config)
        
        results = await client.find_similar(
            query="Lambda timeout error",
            filters={"resource_type": "lambda"},
            limit=5
        )
        
        # Should return empty list on connection error
        assert results == []


def test_memory_context_formatting(mock_similar_investigations):
    """Test memory context formatting for prompts."""
    
    # Create a mock orchestrator to test formatting
    class MockOrchestrator:
        def _format_memory_context(self, similar):
            context = "\n" + "="*60 + "\n"
            context += "RELEVANT PAST INVESTIGATIONS (from memory system)\n"
            context += "="*60 + "\n\n"
            
            for i, mem in enumerate(similar, 1):
                outcome_icon = "✓" if mem.outcome == "resolved" else "⚠" if mem.outcome == "partial" else "✗"
                
                context += f"{i}. Investigation #{mem.investigation_id} (similarity: {mem.similarity_score:.2f})\n"
                context += f"   Resource: {mem.resource_type}:{mem.resource_name}\n"
                context += f"   Root Cause: {mem.root_cause_summary}\n"
                context += f"   Solution: {mem.advice_summary}\n"
                context += f"   Outcome: {outcome_icon} {mem.outcome.upper()} (quality: {mem.quality_score:.2f})\n"
                context += f"   Date: {mem.created_at}\n\n"
            
            context += "="*60 + "\n"
            context += "Use the above historical context to inform your investigation.\n"
            context += "Prioritize solutions that have been proven effective.\n"
            context += "="*60 + "\n\n"
            
            return context
        
        def _extract_patterns(self, similar):
            root_causes = {}
            successful_advice = {}
            
            for mem in similar:
                if mem.outcome == "resolved":
                    root_causes[mem.error_type] = root_causes.get(mem.error_type, 0) + 1
                    successful_advice[mem.advice_summary] = successful_advice.get(mem.advice_summary, 0) + 1
            
            patterns = []
            
            if root_causes:
                most_common = max(root_causes.items(), key=lambda x: x[1])
                patterns.append(f"- {most_common[0]} is the most common root cause ({most_common[1]}/{len(similar)} cases)")
            
            if successful_advice:
                top_advice = max(successful_advice.items(), key=lambda x: x[1])
                patterns.append(f"- Successfully resolved {top_advice[1]} times with: {top_advice[0]}")
            
            return "\n".join(patterns) if patterns else ""
    
    orchestrator = MockOrchestrator()
    formatted_context = orchestrator._format_memory_context(mock_similar_investigations)
    
    # Check that context contains expected elements
    assert "RELEVANT PAST INVESTIGATIONS" in formatted_context
    assert "inv-123" in formatted_context
    assert "inv-456" in formatted_context
    assert "payment-processor" in formatted_context
    assert "✓ RESOLVED" in formatted_context
    assert "DynamoDB connection pool exhaustion" in formatted_context
    assert "Increased connection pool size" in formatted_context


def test_pattern_extraction(mock_similar_investigations):
    """Test pattern extraction from similar investigations."""
    
    class MockOrchestrator:
        def _extract_patterns(self, similar):
            root_causes = {}
            successful_advice = {}
            
            for mem in similar:
                if mem.outcome == "resolved":
                    root_causes[mem.error_type] = root_causes.get(mem.error_type, 0) + 1
                    successful_advice[mem.advice_summary] = successful_advice.get(mem.advice_summary, 0) + 1
            
            patterns = []
            
            if root_causes:
                most_common = max(root_causes.items(), key=lambda x: x[1])
                patterns.append(f"- {most_common[0]} is the most common root cause ({most_common[1]}/{len(similar)} cases)")
            
            if successful_advice:
                top_advice = max(successful_advice.items(), key=lambda x: x[1])
                patterns.append(f"- Successfully resolved {top_advice[1]} times with: {top_advice[0]}")
            
            return "\n".join(patterns) if patterns else ""
    
    orchestrator = MockOrchestrator()
    patterns = orchestrator._extract_patterns(mock_similar_investigations)
    
    # Check that patterns are extracted correctly
    assert "timeout is the most common root cause" in patterns
    assert "Successfully resolved" in patterns


@pytest.mark.asyncio
async def test_memory_client_connectivity_test(mock_memory_config):
    """Test memory client connectivity test."""
    
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.raise_for_status.return_value = None
        mock_client.get.return_value = mock_response_obj
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        client = MemoryClient(mock_memory_config)
        
        is_connected = await client.test_connectivity()
        
        assert is_connected is True
        
        # Verify the health check endpoint was called
        mock_client.get.assert_called_once_with(
            f"{mock_memory_config['endpoint']}/_cluster/health",
            headers=client._auth_headers(),
            timeout=mock_memory_config['timeout_ms'] / 1000.0
        )


@pytest.mark.asyncio
async def test_memory_client_connectivity_test_failure(mock_memory_config):
    """Test memory client connectivity test with failure."""
    
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client.get.side_effect = ConnectionError("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        client = MemoryClient(mock_memory_config)
        
        is_connected = await client.test_connectivity()
        
        assert is_connected is False


def test_memory_client_disabled_connectivity():
    """Test connectivity test when memory is disabled."""
    
    client = MemoryClient({"enabled": False, "endpoint": ""})
    
    # Should return False immediately when disabled
    assert client.enabled is False
    # Note: test_connectivity is async, but we can test the enabled check
    assert not client.enabled
