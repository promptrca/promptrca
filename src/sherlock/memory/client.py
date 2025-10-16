#!/usr/bin/env python3
"""
Sherlock Core - Memory Client
Copyright (C) 2025 Christian Gennaro Faraone

Client for graph-based RAG memory system using OpenSearch.
"""

import httpx
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from .models import (
    GraphNode, GraphEdge, ConfigSnapshot, ObservabilityPointer, 
    Pattern, Incident, ChangeEvent, SubGraphResult, MemoryResult
)
from ..utils import get_logger

logger = get_logger(__name__)


class MemoryClient:
    """Client for graph-based RAG memory system using OpenSearch.
    
    This client provides both ingestion and retrieval capabilities for a knowledge graph
    of AWS resources, their relationships, configurations, and past incidents.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize memory client.
        
        Args:
            config: Memory configuration dict with keys:
                - enabled: bool - whether memory is enabled
                - endpoint: str - OpenSearch endpoint URL
                - auth_type: str - authentication type ("api_key" or "aws_sigv4")
                - api_key: str - API key (if auth_type is "api_key")
                - max_results: int - maximum results to return
                - min_quality: float - minimum quality threshold
                - timeout_ms: int - timeout in milliseconds
        """
        self.enabled = config.get("enabled", False)
        self.endpoint = config.get("endpoint", "").rstrip('/') if config.get("endpoint") else ''
        self.auth_type = config.get("auth_type", "api_key")
        self.api_key = config.get("api_key", "")
        self.max_results = config.get("max_results", 5)
        self.min_quality = config.get("min_quality", 0.7)
        self.timeout_ms = config.get("timeout_ms", 2000)
        
        if not self.enabled or not self.endpoint:
            logger.info("Memory system not configured - memory retrieval disabled")
            self.enabled = False
    
    # ============================================================================
    # INDEX MANAGEMENT
    # ============================================================================
    
    async def create_all_indices(self) -> bool:
        """Create all 7 OpenSearch indices with proper mappings.
            
        Returns:
            True if all indices created successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        indices = [
            ("rca-nodes", self._get_nodes_mapping()),
            ("rca-edges", self._get_edges_mapping()),
            ("rca-configs", self._get_configs_mapping()),
            ("rca-pointers", self._get_pointers_mapping()),
            ("rca-incidents", self._get_incidents_mapping()),
            ("rca-changes", self._get_changes_mapping()),
            ("rca-patterns", self._get_patterns_mapping())
        ]
        
        success_count = 0
        for index_name, mapping in indices:
            try:
                if await self._create_index(index_name, mapping):
                    success_count += 1
                    logger.info(f"Created index: {index_name}")
                else:
                    logger.warning(f"Failed to create index: {index_name}")
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {e}")
        
        return success_count == len(indices)
    
    async def test_connectivity(self) -> bool:
        """Test OpenSearch connectivity.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.endpoint}/_cluster/health",
                    headers=self._auth_headers(),
                    timeout=self.timeout_ms / 1000.0
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"OpenSearch connectivity test failed: {e}")
            return False
    
    # ============================================================================
    # INGESTION METHODS
    # ============================================================================
    
    async def upsert_node(self, node: GraphNode) -> bool:
        """Upsert a graph node to rca-nodes index.
        
        Args:
            node: GraphNode to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Create a safe document ID by encoding the ARN
            doc_id = self._create_safe_doc_id(node.arn)
            doc_body = node.to_dict()
            
            await self._upsert_document("rca-nodes", doc_id, doc_body)
            logger.debug(f"Upserted node: {node.arn}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert node {node.arn}: {e}")
            return False
    
    async def upsert_edge(self, edge: GraphEdge) -> bool:
        """Upsert a graph edge to rca-edges index.
        
        Args:
            edge: GraphEdge to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            doc_id = edge.edge_id
            doc_body = edge.to_dict()
            
            await self._upsert_document("rca-edges", doc_id, doc_body)
            logger.debug(f"Upserted edge: {edge.from_arn} -> {edge.to_arn}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert edge {edge.edge_id}: {e}")
            return False
    
    async def upsert_config(self, config: ConfigSnapshot) -> bool:
        """Upsert a config snapshot to rca-configs index.
        
        Args:
            config: ConfigSnapshot to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            doc_id = config.config_id
            doc_body = config.to_dict()
            
            # Upsert the config
            await self._upsert_document("rca-configs", doc_id, doc_body)
            
            # If this is the current config, mark others as not current
            if config.current:
                await self._update_previous_configs_current_flag(config.arn, config.hash)
            
            logger.debug(f"Upserted config: {config.arn}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert config {config.config_id}: {e}")
            return False
    
    async def upsert_pointer(self, pointer: ObservabilityPointer) -> bool:
        """Upsert an observability pointer to rca-pointers index.
        
        Args:
            pointer: ObservabilityPointer to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Create a safe document ID by encoding the ARN
            doc_id = self._create_safe_doc_id(pointer.arn)
            doc_body = pointer.to_dict()
            
            await self._upsert_document("rca-pointers", doc_id, doc_body)
            logger.debug(f"Upserted pointer: {pointer.arn}")
            return True
        except Exception as e:
            logger.error(f"Failed to upsert pointer {pointer.arn}: {e}")
            return False
    
    async def save_incident(self, incident: Incident) -> bool:
        """Save an incident to rca-incidents index.
        
        Args:
            incident: Incident to save
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            doc_id = incident.incident_id
            doc_body = incident.to_dict()
            
            await self._index_document("rca-incidents", doc_id, doc_body)
            logger.info(f"Saved incident: {incident.incident_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save incident {incident.incident_id}: {e}")
            return False
    
    async def save_change_event(self, change: ChangeEvent) -> bool:
        """Save a change event to rca-changes index.
        
        Args:
            change: ChangeEvent to save
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            doc_id = change.event_id
            doc_body = change.to_dict()
            
            await self._index_document("rca-changes", doc_id, doc_body)
            logger.debug(f"Saved change event: {change.event_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save change event {change.event_id}: {e}")
            return False
    
    async def save_pattern(self, pattern: Pattern) -> bool:
        """Save a pattern to rca-patterns-vec index.
        
        Args:
            pattern: Pattern to save
        
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            doc_id = pattern.pattern_id
            doc_body = pattern.to_dict()
            
            await self._index_document("rca-patterns-vec", doc_id, doc_body)
            logger.info(f"Saved pattern: {pattern.pattern_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save pattern {pattern.pattern_id}: {e}")
            return False
    
    # ============================================================================
    # RAG RETRIEVAL PIPELINE
    # ============================================================================
    
    async def retrieve_context(self, seed: str, k_hop: int = 2) -> Optional[SubGraphResult]:
        """Main RAG retrieval method - gets complete context for investigation.
        
        Args:
            seed: ARN, trace_id, alarm, or other identifier to start from
            k_hop: Number of hops for subgraph traversal (default: 2)
            
        Returns:
            SubGraphResult with complete context, or None if failed
        """
        if not self.enabled:
            return None
        
        try:
            logger.info(f"Retrieving context for seed: {seed}")
            
            # 1. Resolve seed to focus node ARN
            focus_arn = await self._resolve_seed(seed)
            if not focus_arn:
                logger.warning(f"Could not resolve seed: {seed}")
                return None
            
            # 2. Query k-hop subgraph
            subgraph = await self._query_subgraph(focus_arn, k_hop)
            
            # 3. Fetch observability pointers for all nodes
            node_arns = [node['arn'] for node in subgraph['nodes']]
            observability = await self._fetch_pointers(node_arns)
            
            # 4. Fetch config diffs for focus node
            config_diff = await self._fetch_config_diff(focus_arn)
            
            # 5. Query patterns (k-NN search)
            patterns = await self._query_patterns(subgraph, limit=5)
            
            # 6. Query related incidents
            related_incidents = await self._query_incidents(focus_arn, days=30)
            
            result = SubGraphResult(
                focus_node=focus_arn,
                subgraph=subgraph,
                observability=observability,
                config_diff=config_diff,
                patterns=patterns,
                related_incidents=related_incidents
            )
            
            logger.info(f"Retrieved context with {len(subgraph['nodes'])} nodes, {len(subgraph['edges'])} edges")
            return result
            
        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return None
    
    # Legacy method for backward compatibility
    async def find_similar(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int = None
    ) -> List[MemoryResult]:
        """Legacy method - redirects to retrieve_context for backward compatibility.
        
        Args:
            query: Error message or investigation description
            filters: Filter criteria (ignored in new implementation)
            limit: Maximum results to return (ignored in new implementation)
            
        Returns:
            List of similar investigations (empty for now)
        """
        logger.warning("find_similar() is deprecated - use retrieve_context() instead")
        return []
    
    # ============================================================================
    # HELPER METHODS - INDEX MAPPINGS
    # ============================================================================
    
    def _get_nodes_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-nodes index."""
        return {
            "settings": {"index": {"number_of_shards": 1, "refresh_interval": "5s"}},
            "mappings": {
                "properties": {
                    "arn": {"type": "keyword"},
                    "type": {"type": "keyword"},
                    "name": {"type": "keyword"},
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "tags": {"type": "object", "enabled": True},
                    "observability": {
                        "properties": {
                            "log_group": {"type": "keyword"},
                            "xray_name": {"type": "keyword"},
                            "metric_namespace": {"type": "keyword"}
                        }
                    },
                    "config_fingerprint": {
                        "properties": {
                            "hash": {"type": "keyword"},
                            "updated_at": {"type": "date"}
                        }
                    },
                    "versions": {"type": "object", "enabled": True},
                    "staleness": {
                        "properties": {
                            "last_seen": {"type": "date"},
                            "flag": {"type": "boolean"}
                        }
                    }
                }
            }
        }
    
    def _get_edges_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-edges index."""
        return {
            "settings": {"index": {"number_of_shards": 1, "refresh_interval": "5s"}},
            "mappings": {
                "properties": {
                    "from_arn": {"type": "keyword"},
                    "to_arn": {"type": "keyword"},
                    "rel": {"type": "keyword"},
                    "evidence_sources": {"type": "keyword"},
                    "confidence": {"type": "float"},
                    "first_seen": {"type": "date"},
                    "last_seen": {"type": "date"},
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"}
                }
            }
        }
    
    def _get_configs_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-configs index."""
        return {
            "mappings": {
                "properties": {
                    "arn": {"type": "keyword"},
                    "hash": {"type": "keyword"},
                    "current": {"type": "boolean"},
                    "type": {"type": "keyword"},
                    "attrs": {"type": "object", "enabled": True},
                    "blob_s3": {"type": "keyword"},
                    "collected_at": {"type": "date"},
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"}
                }
            }
        }
    
    def _get_pointers_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-pointers index."""
        return {
            "mappings": {
                "properties": {
                    "arn": {"type": "keyword"},
                    "logs": {"type": "keyword"},
                    "traces": {
                        "properties": {
                            "xray_name": {"type": "keyword"},
                            "last_trace_ids": {"type": "keyword"}
                        }
                    },
                    "metrics": {
                        "properties": {
                            "namespace": {"type": "keyword"},
                            "names": {"type": "keyword"}
                        }
                    },
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"},
                    "updated_at": {"type": "date"}
                }
            }
        }
    
    def _get_incidents_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-incidents index."""
        return {
            "mappings": {
                "properties": {
                    "incident_id": {"type": "keyword"},
                    "nodes": {"type": "keyword"},
                    "root_cause": {"type": "text"},
                    "signals": {"type": "keyword"},
                    "fix": {"type": "text"},
                    "useful_queries": {"type": "text"},
                    "pattern_ids": {"type": "keyword"},
                    "created_at": {"type": "date"},
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"}
                }
            }
        }
    
    def _get_changes_mapping(self) -> Dict[str, Any]:
        """Get mapping for rca-changes index."""
        return {
            "mappings": {
                "properties": {
                    "event_id": {"type": "keyword"},
                    "changed_arn": {"type": "keyword"},
                    "change_type": {"type": "keyword"},
                    "diff_hash": {"type": "keyword"},
                    "timestamp": {"type": "date"},
                    "actor": {"type": "keyword"},
                    "links": {"type": "object", "enabled": True},
                    "account_id": {"type": "keyword"},
                    "region": {"type": "keyword"}
                }
            }
        }
    
    def _get_patterns_mapping(self) -> Dict[str, Any]:
        """Get patterns index mapping (no vectors)."""
        return {
            "mappings": {
                "properties": {
                    "pattern_id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "signatures": {
                        "properties": {
                            "topology_signature": {"type": "keyword"},
                            "resource_types": {"type": "keyword"},
                            "relationship_types": {"type": "keyword"},
                            "depth": {"type": "integer"},
                            "stack_signature": {"type": "keyword"},
                            "topology_motif": {"type": "keyword"}
                        }
                    },
                    "playbook_steps": {"type": "text"},
                    "popularity": {"type": "float"},
                    "last_used_at": {"type": "date"},
                    "match_count": {"type": "integer"}
                }
            }
        }
    
    # ============================================================================
    # HELPER METHODS - RAG RETRIEVAL
    # ============================================================================
    
    async def _resolve_seed(self, seed: str) -> Optional[str]:
        """Resolve seed (ARN/trace_id/alarm) to focus node ARN."""
        # If it's already an ARN, return it
        if seed.startswith("arn:aws:"):
            return seed
        
        # Try to resolve trace_id to ARN via pointers
        try:
            query = {
                "size": 1,
                "query": {
                    "term": {"traces.last_trace_ids": seed}
                }
            }
            
            response = await self._query_opensearch("rca-pointers", query)
            hits = response.get('hits', {}).get('hits', [])
            
            if hits:
                return hits[0]['_source']['arn']
        except Exception as e:
            logger.debug(f"Failed to resolve trace_id {seed}: {e}")
        
        # TODO: Add alarm/metric resolution logic
        logger.warning(f"Could not resolve seed: {seed}")
        return None
    
    async def _query_subgraph(self, focus_arn: str, k_hop: int) -> Dict[str, Any]:
        """Query k-hop subgraph starting from focus_arn."""
        nodes = set([focus_arn])
        edges = []
        current_arns = [focus_arn]
        
        for hop in range(k_hop):
            next_arns = set()
            
            # Query out edges
            out_edges = await self._query_edges(current_arns, direction="out")
            edges.extend(out_edges)
            
            # Query in edges
            in_edges = await self._query_edges(current_arns, direction="in")
            edges.extend(in_edges)
            
            # Collect new ARNs for next hop
            for edge in out_edges + in_edges:
                if edge['from_arn'] not in nodes:
                    next_arns.add(edge['from_arn'])
                if edge['to_arn'] not in nodes:
                    next_arns.add(edge['to_arn'])
            
            nodes.update(next_arns)
            current_arns = list(next_arns)
        
        # Fetch node details
        node_details = await self._fetch_nodes(list(nodes))
        
        return {
            "nodes": node_details,
            "edges": edges
        }
    
    async def _query_edges(self, arns: List[str], direction: str) -> List[Dict[str, Any]]:
        """Query edges for given ARNs in specified direction."""
        if not arns:
            return []
        
        try:
            field = "from_arn" if direction == "out" else "to_arn"
            
            query = {
                "size": 200,
                "query": {
                    "bool": {
                        "filter": [
                            {"terms": {field: arns}},
                            {"range": {"last_seen": {"gte": "now-48h"}}},
                            {"range": {"confidence": {"gte": 0.6}}}
                        ]
                    }
                }
            }
            
            response = await self._query_opensearch("rca-edges", query)
            hits = response.get('hits', {}).get('hits', [])
            
            return [hit['_source'] for hit in hits]
        except Exception as e:
            logger.warning(f"Failed to query edges: {e}")
            return []
    
    async def _fetch_nodes(self, arns: List[str]) -> List[Dict[str, Any]]:
        """Fetch node details for given ARNs."""
        if not arns:
            return []
        
        try:
            # Use mget for bulk fetch
            body = {"ids": arns}
            response = await self._query_opensearch("rca-nodes", body, method="mget")
            
            docs = response.get('docs', [])
            return [doc['_source'] for doc in docs if doc.get('found', False)]
        except Exception as e:
            logger.warning(f"Failed to fetch nodes: {e}")
            return []
    
    async def _fetch_pointers(self, arns: List[str]) -> Dict[str, Any]:
        """Fetch observability pointers for given ARNs."""
        if not arns:
            return {}
        
        try:
            # Use mget for bulk fetch
            body = {"ids": arns}
            response = await self._query_opensearch("rca-pointers", body, method="mget")
            
            docs = response.get('docs', [])
            result = {}
            for doc in docs:
                if doc.get('found', False):
                    source = doc['_source']
                    result[source['arn']] = source
            
            return result
        except Exception as e:
            logger.warning(f"Failed to fetch pointers: {e}")
            return {}
    
    async def _fetch_config_diff(self, arn: str) -> List[Dict[str, Any]]:
        """Fetch current and previous config for ARN."""
        try:
            query = {
                "size": 2,
                "sort": [{"collected_at": "desc"}],
                "query": {"term": {"arn": arn}}
            }
            
            response = await self._query_opensearch("rca-configs", query)
            hits = response.get('hits', {}).get('hits', [])
            
            return [hit['_source'] for hit in hits]
        except Exception as e:
            logger.warning(f"Failed to fetch config diff for {arn}: {e}")
            return []
    
    async def _query_patterns(self, subgraph: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Query patterns using structural signature matching."""
        try:
            # Build structural signature from subgraph
            topology_sig = self._build_topology_signature(subgraph)
            resource_types = self._extract_resource_types(subgraph)
            relationship_types = self._extract_relationship_types(subgraph)
            tags = self._extract_tags_from_subgraph(subgraph)
            
            # Multi-level query strategy
            queries = [
                # 1. Exact topology match (highest priority)
                {
                    "size": limit,
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"signatures.topology_signature": topology_sig}}
                            ]
                        }
                    }
                },
                # 2. Resource type + relationship match
                {
                    "size": limit * 2,
                    "query": {
                        "bool": {
                            "filter": [
                                {"terms": {"signatures.resource_types": resource_types}},
                                {"terms": {"signatures.relationship_types": relationship_types}}
                            ]
                        }
                    }
                },
                # 3. Tag-based match (fallback)
                {
                    "size": limit * 3,
                    "query": {
                        "bool": {
                            "filter": [{"terms": {"tags": tags}}] if tags else [{"match_all": {}}]
                        }
                    }
                }
            ]
            
            # Try queries in order, stop when enough results found
            all_patterns = []
            for query in queries:
                response = await self._query_opensearch("rca-patterns", query)
                hits = response.get('hits', {}).get('hits', [])
                all_patterns.extend([hit['_source'] for hit in hits])
                
                if len(all_patterns) >= limit:
                    break
            
            # Deduplicate and rerank
            unique_patterns = self._deduplicate_patterns(all_patterns)
            reranked = self._rerank_patterns_structural(unique_patterns, subgraph, topology_sig, resource_types, relationship_types, tags)
            
            return reranked[:limit]
        except Exception as e:
            logger.warning(f"Failed to query patterns: {e}")
            return []
    
    async def _query_incidents(self, focus_arn: str, days: int = 30) -> List[Dict[str, Any]]:
        """Query related incidents for focus ARN."""
        try:
            query = {
                "size": 20,
                "sort": [{"created_at": "desc"}],
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"nodes": focus_arn}},
                            {"range": {"created_at": {"gte": f"now-{days}d"}}}
                        ]
                    }
                }
            }
            
            response = await self._query_opensearch("rca-incidents", query)
            hits = response.get('hits', {}).get('hits', [])
            
            return [hit['_source'] for hit in hits]
        except Exception as e:
            logger.warning(f"Failed to query incidents: {e}")
            return []
    
    # ============================================================================
    # HELPER METHODS - UTILITIES
    # ============================================================================
    
    async def _create_index(self, index_name: str, mapping: Dict[str, Any]) -> bool:
        """Create a single OpenSearch index."""
        try:
            async with httpx.AsyncClient() as client:
                # Check if index exists
                response = await client.head(
                    f"{self.endpoint}/{index_name}",
                    headers=self._auth_headers(),
                    timeout=self.timeout_ms / 1000.0
                )
                
                if response.status_code == 200:
                    logger.debug(f"Index {index_name} already exists")
                    return True
                
                # Create index
                response = await client.put(
                    f"{self.endpoint}/{index_name}",
                    json=mapping,
                    headers=self._auth_headers(),
                    timeout=self.timeout_ms / 1000.0
                )
                response.raise_for_status()
                return True
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.debug(f"Index {index_name} already exists")
                return True
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to create index {index_name}: {e}")
            return False
    
    def _create_safe_doc_id(self, arn: str) -> str:
        """Create a safe document ID from an ARN by encoding special characters."""
        import base64
        import urllib.parse
        
        # URL encode the ARN to make it safe for use as a document ID
        return urllib.parse.quote(arn, safe='')
    
    async def _upsert_document(self, index: str, doc_id: str, doc_body: Dict[str, Any]) -> None:
        """Upsert document using update API with doc_as_upsert."""
        body = {
            "doc": doc_body,
            "doc_as_upsert": True
        }
        
        await self._query_opensearch(f"{index}/_update/{doc_id}", body, method="post")
    
    async def _index_document(self, index: str, doc_id: str, doc_body: Dict[str, Any]) -> None:
        """Index document using index API."""
        await self._query_opensearch(f"{index}/_doc/{doc_id}", doc_body, method="put")
    
    async def _update_previous_configs_current_flag(self, arn: str, current_hash: str) -> None:
        """Update previous configs to set current=false."""
        query = {
            "script": {
                "source": "if (ctx._source.hash != params.h) { ctx._source.current = false }",
                "lang": "painless",
                "params": {"h": current_hash}
            },
            "query": {"term": {"arn": arn}}
        }
        
        await self._query_opensearch("rca-configs/_update_by_query", query, method="post")
    
    async def _query_opensearch(self, endpoint: str, body: Dict[str, Any], method: str = "post") -> Dict[str, Any]:
        """Execute OpenSearch query."""
        async with httpx.AsyncClient() as client:
            url = f"{self.endpoint}/{endpoint}"
            
            if method == "post":
                response = await client.post(url, json=body, headers=self._auth_headers(), timeout=self.timeout_ms / 1000.0)
            elif method == "put":
                response = await client.put(url, json=body, headers=self._auth_headers(), timeout=self.timeout_ms / 1000.0)
            elif method == "mget":
                response = await client.post(f"{url}/_mget", json=body, headers=self._auth_headers(), timeout=self.timeout_ms / 1000.0)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
    
    def _auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers."""
        if self.auth_type == "api_key" and self.api_key:
            return {"Authorization": f"ApiKey {self.api_key}"}
        elif self.auth_type == "aws_sigv4":
            # TODO: Implement AWS SigV4 signing if needed
            logger.warning("AWS SigV4 auth not yet implemented")
        
        return {}
    
    def _build_topology_signature(self, subgraph: Dict[str, Any]) -> str:
        """Generate deterministic topology signature from subgraph."""
        nodes = subgraph.get('nodes', [])
        edges = subgraph.get('edges', [])
        
        # Create normalized representation
        node_types = sorted([n.get('type', '') for n in nodes])
        edge_rels = sorted([f"{e.get('rel', '')}" for e in edges])
        
        # Hash for deterministic signature
        import hashlib
        content = f"nodes:{','.join(node_types)}|edges:{','.join(edge_rels)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _extract_resource_types(self, subgraph: Dict[str, Any]) -> List[str]:
        """Extract sorted unique resource types."""
        nodes = subgraph.get('nodes', [])
        return sorted(list(set([n.get('type', '') for n in nodes])))

    def _extract_relationship_types(self, subgraph: Dict[str, Any]) -> List[str]:
        """Extract sorted unique relationship types."""
        edges = subgraph.get('edges', [])
        return sorted(list(set([e.get('rel', '') for e in edges])))

    def _deduplicate_patterns(self, patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate patterns by pattern_id."""
        seen = set()
        unique = []
        for pattern in patterns:
            pid = pattern.get('pattern_id')
            if pid and pid not in seen:
                seen.add(pid)
                unique.append(pattern)
        return unique

    def _rerank_patterns_structural(self, patterns: List[Dict[str, Any]], subgraph: Dict[str, Any], 
                                     topology_sig: str, resource_types: List[str], 
                                     relationship_types: List[str], tags: List[str]) -> List[Dict[str, Any]]:
        """Rerank patterns using structural similarity scoring."""
        for pattern in patterns:
            score = 0.0
            sigs = pattern.get('signatures', {})
            
            # Topology signature match (40% weight)
            if sigs.get('topology_signature') == topology_sig:
                score += 0.4
            
            # Resource type overlap (30% weight)
            pattern_resource_types = sigs.get('resource_types', [])
            resource_overlap = len(set(resource_types) & set(pattern_resource_types)) / max(len(resource_types), 1)
            score += 0.3 * resource_overlap
            
            # Relationship type overlap (20% weight)
            pattern_rel_types = sigs.get('relationship_types', [])
            rel_overlap = len(set(relationship_types) & set(pattern_rel_types)) / max(len(relationship_types), 1)
            score += 0.2 * rel_overlap
            
            # Tag overlap (10% weight)
            pattern_tags = pattern.get('tags', [])
            tag_overlap = len(set(tags) & set(pattern_tags)) / max(len(tags), 1) if tags else 0
            score += 0.1 * tag_overlap
            
            pattern['_match_score'] = score
        
        # Sort by match score descending, then popularity
        return sorted(patterns, key=lambda p: (p.get('_match_score', 0), p.get('popularity', 0)), reverse=True)
    
    def _extract_tags_from_subgraph(self, subgraph: Dict[str, Any]) -> List[str]:
        """Extract relevant tags from subgraph for pattern filtering."""
        nodes = subgraph.get('nodes', [])
        tags = set()
        
        for node in nodes:
            node_type = node.get('type', '')
            if node_type:
                tags.add(node_type)
        
        return list(tags)
    
