#!/usr/bin/env python3
"""
Sherlock Core - Memory Client
Copyright (C) 2025 Christian Gennaro Faraone

Client for querying external memory system via OpenSearch-compatible API.
"""

import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
from .models import MemoryResult
from ..utils import get_logger

logger = get_logger(__name__)


class MemoryClient:
    """Client for querying external memory system via OpenSearch-compatible API.
    
    This client provides read-only access to historical investigations stored
    in an external system. It uses hybrid search (semantic + keyword) to find
    similar past investigations.
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
    
    async def find_similar(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int = None
    ) -> List[MemoryResult]:
        """Query memory system for similar investigations using hybrid search.
        
        Args:
            query: Error message or investigation description
            filters: Filter criteria:
                - resource_type: AWS resource type (e.g., "lambda")
                - resource_name: Specific resource name (optional)
                - min_quality_score: Minimum quality threshold (default: 0.7)
            limit: Maximum results to return (defaults to config max_results)
            
        Returns:
            List of similar investigations, ranked by relevance
        """
        if not self.enabled:
            return []
        
        if limit is None:
            limit = self.max_results
        
        try:
            logger.info(f"Querying memory for similar investigations (query: {query[:100]}...)")
            
            # Build hybrid search query
            query_body = self._build_hybrid_query(query, filters, limit)
            
            # Execute query
            response = await self._query_opensearch(query_body)
            
            # Parse results
            hits = response.get('hits', {}).get('hits', [])
            candidates = [MemoryResult.from_hit(hit) for hit in hits]
            
            logger.info(f"Found {len(candidates)} candidate investigations")
            
            # Rerank for better relevance
            reranked = self._rerank_results(query, candidates, filters)
            
            final_results = reranked[:limit]
            logger.info(f"Returning {len(final_results)} similar investigations")
            
            return final_results
            
        except httpx.TimeoutException:
            logger.warning("Memory query timeout - continuing without memory")
            return []
        except Exception as e:
            logger.warning(f"Memory query failed: {e} - continuing without memory")
            return []
    
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
    
    async def create_index(self) -> bool:
        """Create the investigations index with proper mapping.
        
        Returns:
            True if index created successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        index_mapping = {
            "mappings": {
                "properties": {
                    "investigation_id": {
                        "type": "keyword"
                    },
                    "resource_type": {
                        "type": "keyword"
                    },
                    "resource_name": {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword"
                            }
                        }
                    },
                    "error_type": {
                        "type": "keyword"
                    },
                    "error_message": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "root_cause_summary": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "advice_summary": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "outcome": {
                        "type": "keyword"
                    },
                    "quality_score": {
                        "type": "float"
                    },
                    "created_at": {
                        "type": "date",
                        "format": "strict_date_optional_time||epoch_millis"
                    },
                    "facts": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "hypotheses": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "advice": {
                        "type": "text",
                        "analyzer": "standard"
                    }
                }
            },
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "standard": {
                            "type": "standard",
                            "stopwords": "_english_"
                        }
                    }
                }
            }
        }
        
        try:
            async with httpx.AsyncClient() as client:
                # Check if index exists
                response = await client.head(
                    f"{self.endpoint}/investigations",
                    headers=self._auth_headers(),
                    timeout=self.timeout_ms / 1000.0
                )
                
                if response.status_code == 200:
                    logger.info("Investigations index already exists")
                    return True
                
                # Create index
                response = await client.put(
                    f"{self.endpoint}/investigations",
                    json=index_mapping,
                    headers=self._auth_headers(),
                    timeout=self.timeout_ms / 1000.0
                )
                response.raise_for_status()
                logger.info("Successfully created investigations index")
                return True
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                logger.info("Index already exists")
                return True
            logger.error(f"Failed to create index: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    def _build_hybrid_query(
        self,
        query: str,
        filters: Dict[str, Any],
        limit: int
    ) -> Dict[str, Any]:
        """Build OpenSearch hybrid query combining semantic and keyword search.
        
        Args:
            query: Search query text
            filters: Filter criteria
            limit: Max results
            
        Returns:
            OpenSearch query body
        """
        # Retrieve more candidates for reranking
        size = limit * 4
        
        # Build filter clauses
        filter_clauses = []
        
        if filters.get('resource_type'):
            filter_clauses.append({"term": {"resource_type": filters['resource_type']}})
        
        min_quality = filters.get('min_quality_score', self.min_quality)
        filter_clauses.append({"range": {"quality_score": {"gte": min_quality}}})
        
        # Build query body - using multi_match for local OpenSearch
        query_body = {
            "size": size,
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "error_message^3",  # Boost error message matches
                                    "root_cause_summary^2",
                                    "resource_name^2",
                                    "advice_summary",
                                    "investigation_id"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"  # Add fuzzy matching for typos
                            }
                        }
                    ],
                    "filter": filter_clauses
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"quality_score": {"order": "desc"}},
                {"created_at": {"order": "desc"}}
            ]
        }
        
        return query_body
    
    def _rerank_results(
        self,
        query: str,
        candidates: List[MemoryResult],
        filters: Dict[str, Any]
    ) -> List[MemoryResult]:
        """Rerank results using heuristic scoring for better relevance.
        
        Args:
            query: Original search query
            candidates: List of candidate results
            filters: Filter criteria
            
        Returns:
            Reranked list of results
        """
        for candidate in candidates:
            boost = 1.0
            
            # Boost exact resource name matches
            resource_name = filters.get("resource_name", "")
            if resource_name and resource_name.lower() in candidate.resource_name.lower():
                boost *= 1.5
            
            # Boost resolved cases
            if candidate.outcome == "resolved":
                boost *= 1.3
            elif candidate.outcome == "partial":
                boost *= 1.1
            
            # Boost by quality score
            boost *= (0.5 + candidate.quality_score * 0.5)
            
            # Boost recent investigations (recency bias)
            try:
                created_dt = datetime.fromisoformat(candidate.created_at.replace('Z', '+00:00'))
                days_old = (datetime.now(created_dt.tzinfo or None) - created_dt).days
                
                if days_old < 7:
                    boost *= 1.2
                elif days_old < 30:
                    boost *= 1.1
            except Exception:
                pass  # Skip recency boost if date parsing fails
            
            # Apply boost to similarity score
            candidate.similarity_score *= boost
        
        # Sort by boosted similarity score
        return sorted(candidates, key=lambda x: x.similarity_score, reverse=True)
    
    async def _query_opensearch(self, query_body: Dict[str, Any]) -> Dict[str, Any]:
        """Execute OpenSearch query against external endpoint.
        
        Args:
            query_body: OpenSearch query body
            
        Returns:
            OpenSearch response
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/investigations/_search",
                json=query_body,
                headers=self._auth_headers(),
                timeout=self.timeout_ms / 1000.0  # Convert ms to seconds
            )
            response.raise_for_status()
            return response.json()
    
    def _auth_headers(self) -> Dict[str, str]:
        """Generate authentication headers.
        
        Returns:
            HTTP headers for authentication
        """
        if self.auth_type == "api_key" and self.api_key:
            return {"Authorization": f"ApiKey {self.api_key}"}
        elif self.auth_type == "aws_sigv4":
            # TODO: Implement AWS SigV4 signing if needed
            logger.warning("AWS SigV4 auth not yet implemented")
        
        return {}
