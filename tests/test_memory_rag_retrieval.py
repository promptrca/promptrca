#!/usr/bin/env python3
"""
Tests for RAG Context Retrieval and Subgraph Traversal
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from src.sherlock.memory.client import MemoryClient
from src.sherlock.memory.models import SubGraphResult, GraphNode, GraphEdge, ObservabilityPointer, Pattern, Incident


class TestRAGRetrieval:
    """Test RAG context retrieval functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key",
            "max_results": 5,
            "min_quality": 0.7,
            "timeout_ms": 2000
        }
        
    
    @pytest.mark.asyncio
    async def test_retrieve_context_disabled(self):
        """Test retrieve_context when memory is disabled."""
        client = MemoryClient({"enabled": False, "endpoint": ""})
        
        result = await client.retrieve_context("arn:aws:lambda:eu-west-1:123456789012:function:test-function")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_retrieve_context_with_trace_id(self):
        """Test context retrieval using trace ID as seed."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            # Mock all the internal method calls
            mock_query.side_effect = [
                # _resolve_seed call for trace ID
                {"hits": {"hits": [{"_source": {"arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function"}}]}},
                # _query_subgraph calls (out edges, in edges, node details)
                {"hits": {"hits": []}},  # out edges
                {"hits": {"hits": []}},  # in edges
                {"docs": [{"found": True, "_source": {"arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function", "type": "lambda"}}]},  # node details
                # _fetch_pointers call
                {"docs": [{"found": True, "_source": {"arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function", "logs": "/aws/lambda/test-function"}}]},
                # _fetch_config_diff call
                {"hits": {"hits": []}},  # config diff
                # _query_patterns call
                {"hits": {"hits": []}},  # patterns
                # _query_incidents call
                {"hits": {"hits": []}}   # incidents
            ]
            
            client = MemoryClient(self.memory_config)
            
            result = await client.retrieve_context("trace-123")
            
            assert result is not None
            assert result.focus_node == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
    
    @pytest.mark.asyncio
    async def test_retrieve_context_unresolvable_seed(self):
        """Test context retrieval with unresolvable seed."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = {"hits": {"hits": []}}
            mock_client.post.return_value = mock_response_obj
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client.retrieve_context("unknown-seed")
            
            assert result is None
    


class TestSeedResolution:
    """Test seed resolution functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_resolve_seed_arn(self):
        """Test resolving ARN seed."""
        client = MemoryClient(self.memory_config)
        
        arn = "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
        result = await client._resolve_seed(arn)
        
        assert result == arn
    
    @pytest.mark.asyncio
    async def test_resolve_seed_trace_id(self):
        """Test resolving trace ID seed."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "traces": {
                                    "last_trace_ids": ["trace-123"]
                                }
                            }
                        }
                    ]
                }
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._resolve_seed("trace-123")
            
            assert result == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
    
    @pytest.mark.asyncio
    async def test_resolve_seed_trace_id_not_found(self):
        """Test resolving trace ID that doesn't exist."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {"hits": {"hits": []}}
            
            client = MemoryClient(self.memory_config)
            
            result = await client._resolve_seed("trace-nonexistent")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_resolve_seed_exception(self):
        """Test seed resolution with exception."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Query failed")
            
            client = MemoryClient(self.memory_config)
            
            result = await client._resolve_seed("trace-123")
            
            assert result is None


class TestSubgraphTraversal:
    """Test subgraph traversal functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_query_subgraph_single_hop(self):
        """Test single-hop subgraph traversal."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = [
                # Out edges query
                {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                    "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                    "rel": "READS",
                                    "confidence": 0.9
                                }
                            }
                        ]
                    }
                },
                # In edges query
                {"hits": {"hits": []}},
                # Node details query
                {
                    "docs": [
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "type": "lambda",
                                "name": "test-function"
                            }
                        },
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                "type": "dynamodb",
                                "name": "test-table"
                            }
                        }
                    ]
                }
            ]
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_subgraph("arn:aws:lambda:eu-west-1:123456789012:function:test-function", k_hop=1)
            
            assert "nodes" in result
            assert "edges" in result
            assert len(result["nodes"]) == 2
            assert len(result["edges"]) == 1
            assert result["edges"][0]["rel"] == "READS"
    
    @pytest.mark.asyncio
    async def test_query_subgraph_multiple_hops(self):
        """Test multi-hop subgraph traversal."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            # Mock responses for multiple hops
            mock_query.side_effect = [
                # Hop 1 - out edges
                {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                    "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                    "rel": "READS",
                                    "confidence": 0.9
                                }
                            }
                        ]
                    }
                },
                # Hop 1 - in edges
                {"hits": {"hits": []}},
                # Hop 2 - out edges (from DynamoDB)
                {
                    "hits": {
                        "hits": [
                            {
                                "_source": {
                                    "from_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                    "to_arn": "arn:aws:s3:eu-west-1:123456789012:bucket/backup-bucket",
                                    "rel": "WRITES",
                                    "confidence": 0.8
                                }
                            }
                        ]
                    }
                },
                # Hop 2 - in edges
                {"hits": {"hits": []}},
                # Node details query
                {
                    "docs": [
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "type": "lambda",
                                "name": "test-function"
                            }
                        },
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                "type": "dynamodb",
                                "name": "test-table"
                            }
                        },
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:s3:eu-west-1:123456789012:bucket/backup-bucket",
                                "type": "s3",
                                "name": "backup-bucket"
                            }
                        }
                    ]
                }
            ]
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_subgraph("arn:aws:lambda:eu-west-1:123456789012:function:test-function", k_hop=2)
            
            assert len(result["nodes"]) == 3
            assert len(result["edges"]) == 2
            assert any(edge["rel"] == "READS" for edge in result["edges"])
            assert any(edge["rel"] == "WRITES" for edge in result["edges"])
    
    @pytest.mark.asyncio
    async def test_query_subgraph_no_edges(self):
        """Test subgraph traversal with no edges."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = [
                {"hits": {"hits": []}},  # Out edges
                {"hits": {"hits": []}},  # In edges
                {  # Node details
                    "docs": [
                        {
                            "found": True,
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "type": "lambda",
                                "name": "test-function"
                            }
                        }
                    ]
                }
            ]
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_subgraph("arn:aws:lambda:eu-west-1:123456789012:function:test-function", k_hop=1)
            
            assert len(result["nodes"]) == 1
            assert len(result["edges"]) == 0


class TestEdgeQuerying:
    """Test edge querying functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_query_edges_out_direction(self):
        """Test querying outbound edges."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                                "rel": "READS",
                                "confidence": 0.9,
                                "last_seen": "2025-01-15T10:30:00Z"
                            }
                        }
                    ]
                }
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_edges(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"], "out")
            
            assert len(result) == 1
            assert result[0]["rel"] == "READS"
            assert result[0]["from_arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
    
    @pytest.mark.asyncio
    async def test_query_edges_in_direction(self):
        """Test querying inbound edges."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "from_arn": "arn:aws:apigateway:eu-west-1:123456789012:restapi/test-api",
                                "to_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "rel": "CALLS",
                                "confidence": 0.95,
                                "last_seen": "2025-01-15T10:30:00Z"
                            }
                        }
                    ]
                }
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_edges(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"], "in")
            
            assert len(result) == 1
            assert result[0]["rel"] == "CALLS"
            assert result[0]["to_arn"] == "arn:aws:lambda:eu-west-1:123456789012:function:test-function"
    
    @pytest.mark.asyncio
    async def test_query_edges_empty_arns(self):
        """Test querying edges with empty ARN list."""
        client = MemoryClient(self.memory_config)
        
        result = await client._query_edges([], "out")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_query_edges_exception(self):
        """Test edge querying with exception."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Query failed")
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_edges(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"], "out")
            
            assert result == []


class TestNodeFetching:
    """Test node fetching functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_fetch_nodes_success(self):
        """Test successful node fetching."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "docs": [
                    {
                        "found": True,
                        "_source": {
                            "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                            "type": "lambda",
                            "name": "test-function",
                            "account_id": "123456789012",
                            "region": "eu-west-1"
                        }
                    },
                    {
                        "found": True,
                        "_source": {
                            "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table",
                            "type": "dynamodb",
                            "name": "test-table",
                            "account_id": "123456789012",
                            "region": "eu-west-1"
                        }
                    }
                ]
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_nodes([
                "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                "arn:aws:dynamodb:eu-west-1:123456789012:table/test-table"
            ])
            
            assert len(result) == 2
            assert result[0]["type"] == "lambda"
            assert result[1]["type"] == "dynamodb"
    
    @pytest.mark.asyncio
    async def test_fetch_nodes_empty_arns(self):
        """Test fetching nodes with empty ARN list."""
        client = MemoryClient(self.memory_config)
        
        result = await client._fetch_nodes([])
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_fetch_nodes_not_found(self):
        """Test fetching nodes that don't exist."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json.return_value = {
                "docs": [
                    {
                        "found": False
                    },
                    {
                        "found": False
                    }
                ]
            }
            mock_client.post.return_value = mock_response_obj
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_nodes([
                "arn:aws:lambda:eu-west-1:123456789012:function:nonexistent",
                "arn:aws:dynamodb:eu-west-1:123456789012:table:nonexistent"
            ])
            
            assert result == []
    
    @pytest.mark.asyncio
    async def test_fetch_nodes_exception(self):
        """Test node fetching with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Query failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_nodes(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"])
            
            assert result == []


class TestPointerFetching:
    """Test observability pointer fetching functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_fetch_pointers_success(self):
        """Test successful pointer fetching."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "docs": [
                    {
                        "found": True,
                        "_source": {
                            "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                            "logs": "/aws/lambda/test-function",
                            "traces": {
                                "xray_name": "test-function",
                                "last_trace_ids": ["trace-123"]
                            },
                            "metrics": {
                                "namespace": "AWS/Lambda",
                                "names": ["Duration", "Errors"]
                            }
                        }
                    }
                ]
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_pointers(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"])
            
            assert len(result) == 1
            assert "arn:aws:lambda:eu-west-1:123456789012:function:test-function" in result
            assert result["arn:aws:lambda:eu-west-1:123456789012:function:test-function"]["logs"] == "/aws/lambda/test-function"
    
    @pytest.mark.asyncio
    async def test_fetch_pointers_empty_arns(self):
        """Test fetching pointers with empty ARN list."""
        client = MemoryClient(self.memory_config)
        
        result = await client._fetch_pointers([])
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_fetch_pointers_exception(self):
        """Test pointer fetching with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Query failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_pointers(["arn:aws:lambda:eu-west-1:123456789012:function:test-function"])
            
            assert result == {}


class TestConfigDiffFetching:
    """Test config diff fetching functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_fetch_config_diff_success(self):
        """Test successful config diff fetching."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "hash": "current-hash",
                                "current": True,
                                "type": "lambda",
                                "attrs": {"timeout": 30, "memory": 512},
                                "collected_at": "2025-01-15T10:30:00Z"
                            }
                        },
                        {
                            "_source": {
                                "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                                "hash": "previous-hash",
                                "current": False,
                                "type": "lambda",
                                "attrs": {"timeout": 15, "memory": 256},
                                "collected_at": "2025-01-14T10:30:00Z"
                            }
                        }
                    ]
                }
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_config_diff("arn:aws:lambda:eu-west-1:123456789012:function:test-function")
            
            assert len(result) == 2
            assert result[0]["current"] is True
            assert result[1]["current"] is False
    
    @pytest.mark.asyncio
    async def test_fetch_config_diff_exception(self):
        """Test config diff fetching with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Query failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client._fetch_config_diff("arn:aws:lambda:eu-west-1:123456789012:function:test-function")
            
            assert result == []


class TestPatternQuerying:
    """Test pattern querying functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
        
    
    @pytest.mark.asyncio
    async def test_query_patterns_structural_matching(self):
        """Test pattern querying with structural signature matching."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            
            # Mock OpenSearch query response - just return one result
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "pattern_id": "P-001",
                                "title": "Lambda Timeout Pattern",
                                "tags": ["lambda", "timeout"],
                                "signatures": {
                                    "topology_signature": "e34dae0e1ef15693",  # This should match the generated signature
                                    "resource_types": ["lambda", "dynamodb"],
                                    "relationship_types": ["READS"],
                                    "depth": 1
                                },
                                "playbook_steps": "Check DynamoDB capacity",
                                "popularity": 0.8,
                                "match_count": 5
                            }
                        }
                    ]
                }
            }
            
            # Create client after mocking
            client = MemoryClient(self.memory_config)
            
            subgraph = {
                "nodes": [
                    {"type": "lambda", "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function"},
                    {"type": "dynamodb", "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table:test-table"}
                ],
                "edges": [
                    {
                        "from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                        "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table:test-table",
                        "rel": "READS"
                    }
                ]
            }
            
            result = await client._query_patterns(subgraph, limit=5)
            
            assert len(result) == 1
            assert result[0]["pattern_id"] == "P-001"
            assert result[0]["_match_score"] > 0  # Should have a structural match score
            assert result[0]["title"] == "Lambda Timeout Pattern"
    
    @pytest.mark.asyncio
    async def test_query_patterns_empty_subgraph(self):
        """Test pattern querying with empty subgraph."""
        client = MemoryClient(self.memory_config)
        
        subgraph = {"nodes": [], "edges": []}
        result = await client._query_patterns(subgraph, limit=5)
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_query_patterns_exception(self):
        """Test pattern querying with exception."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("OpenSearch query failed")
            
            client = MemoryClient(self.memory_config)
            
            subgraph = {"nodes": [], "edges": []}
            result = await client._query_patterns(subgraph, limit=5)
            
            assert result == []


class TestIncidentQuerying:
    """Test incident querying functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    @pytest.mark.asyncio
    async def test_query_incidents_success(self):
        """Test successful incident querying."""
        with patch.object(MemoryClient, '_query_opensearch', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "incident_id": "INC-001",
                                "nodes": ["arn:aws:lambda:eu-west-1:123456789012:function:test-function"],
                                "root_cause": "Lambda timeout due to DynamoDB throttling",
                                "signals": ["timeout", "throttling"],
                                "fix": "Increase DynamoDB capacity",
                                "useful_queries": "Check CloudWatch metrics",
                                "pattern_ids": ["P-001"],
                                "created_at": "2025-01-15T10:30:00Z"
                            }
                        }
                    ]
                }
            }
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_incidents("arn:aws:lambda:eu-west-1:123456789012:function:test-function", days=30)
            
            assert len(result) == 1
            assert result[0]["incident_id"] == "INC-001"
            assert result[0]["root_cause"] == "Lambda timeout due to DynamoDB throttling"
    
    @pytest.mark.asyncio
    async def test_query_incidents_exception(self):
        """Test incident querying with exception."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = Exception("Query failed")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            client = MemoryClient(self.memory_config)
            
            result = await client._query_incidents("arn:aws:lambda:eu-west-1:123456789012:function:test-function", days=30)
            
            assert result == []


class TestHelperMethods:
    """Test helper methods for RAG retrieval."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory_config = {
            "enabled": True,
            "endpoint": "https://memory-api.example.com",
            "auth_type": "api_key",
            "api_key": "test-key"
        }
    
    def test_build_topology_signature(self):
        """Test building topology signature."""
        client = MemoryClient(self.memory_config)
        
        subgraph = {
            "nodes": [
                {"type": "lambda", "arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function"},
                {"type": "dynamodb", "arn": "arn:aws:dynamodb:eu-west-1:123456789012:table:test-table"}
            ],
            "edges": [
                {
                    "from_arn": "arn:aws:lambda:eu-west-1:123456789012:function:test-function",
                    "to_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table:test-table",
                    "rel": "READS"
                }
            ]
        }
        
        signature = client._build_topology_signature(subgraph)
        
        assert len(signature) == 16  # SHA256 hash truncated to 16 chars
        assert isinstance(signature, str)
    
    def test_extract_tags_from_subgraph(self):
        """Test extracting tags from subgraph."""
        client = MemoryClient(self.memory_config)
        
        subgraph = {
            "nodes": [
                {"type": "lambda"},
                {"type": "dynamodb"},
                {"type": "s3"}
            ],
            "edges": []
        }
        
        tags = client._extract_tags_from_subgraph(subgraph)
        
        assert "lambda" in tags
        assert "dynamodb" in tags
        assert "s3" in tags
        assert len(tags) == 3
    
    def test_extract_tags_from_subgraph_empty(self):
        """Test extracting tags from empty subgraph."""
        client = MemoryClient(self.memory_config)
        
        subgraph = {"nodes": [], "edges": []}
        tags = client._extract_tags_from_subgraph(subgraph)
        
        assert tags == []
    
    def test_rerank_patterns_structural(self):
        """Test structural pattern reranking."""
        client = MemoryClient(self.memory_config)
        
        patterns = [
            {
                "pattern_id": "P-001",
                "tags": ["lambda", "timeout"],
                "signatures": {
                    "topology_signature": "a3f5e8c2d1b4a7e9",
                    "resource_types": ["lambda", "dynamodb"],
                    "relationship_types": ["READS"]
                },
                "popularity": 0.8
            },
            {
                "pattern_id": "P-002",
                "tags": ["dynamodb", "throttling"],
                "signatures": {
                    "topology_signature": "b4f6e9c3d2b5a8e0",
                    "resource_types": ["dynamodb"],
                    "relationship_types": ["WRITES"]
                },
                "popularity": 0.6
            }
        ]
        
        subgraph = {
            "nodes": [{"type": "lambda"}, {"type": "dynamodb"}],
            "edges": [{"rel": "READS"}]
        }
        
        topology_sig = "a3f5e8c2d1b4a7e9"
        resource_types = ["lambda", "dynamodb"]
        relationship_types = ["READS"]
        tags = ["lambda"]
        
        reranked = client._rerank_patterns_structural(patterns, subgraph, topology_sig, resource_types, relationship_types, tags)
        
        assert len(reranked) == 2
        assert "_match_score" in reranked[0]
        assert "_match_score" in reranked[1]
        # First pattern should have higher score due to exact topology match
        assert reranked[0]["_match_score"] > reranked[1]["_match_score"]
        # Should be sorted by match score
        assert reranked[0]["_match_score"] >= reranked[1]["_match_score"]
    
