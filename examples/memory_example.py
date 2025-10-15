#!/usr/bin/env python3
"""
Sherlock Core - RAG Memory System Example
Copyright (C) 2025 Christian Gennaro Faraone

Example demonstrating the graph-based RAG memory system.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sherlock.memory import (
    MemoryClient, GraphNode, GraphEdge, ObservabilityPointer, 
    ConfigSnapshot, Pattern, Incident, GraphBuilder
)
from sherlock.utils.config import get_memory_config


async def main():
    """Main example function demonstrating RAG system."""
    print("🧠 Sherlock RAG Memory System Example")
    print("=" * 50)
    
    # Get configurations
    memory_config = get_memory_config()
    
    print(f"Memory enabled: {memory_config['enabled']}")
    print(f"Memory endpoint: {memory_config['endpoint']}")
    
    if not memory_config['enabled']:
        print("❌ Memory system is disabled. Set SHERLOCK_MEMORY_ENABLED=true to enable.")
        return
    
    # Initialize memory client with embedding support
    memory_client = MemoryClient(memory_config)
    
    # Test connectivity
    print("\n🔌 Testing OpenSearch connectivity...")
    if await memory_client.test_connectivity():
        print("✅ Connected to OpenSearch successfully")
    else:
        print("❌ Failed to connect to OpenSearch")
        return
    
    # Create all indices
    print("\n📝 Creating RAG indices...")
    if await memory_client.create_all_indices():
        print("✅ All indices created successfully")
    else:
        print("❌ Failed to create some indices")
        return
    
    # Example: Build a knowledge graph
    print("\n🏗️ Building knowledge graph...")
    
    # Create sample nodes
    lambda_node = GraphNode(
        arn="arn:aws:lambda:eu-west-1:123456789012:function:my-function",
        type="lambda",
        name="my-function",
        account_id="123456789012",
        region="eu-west-1",
        tags={"Environment": "prod", "Team": "backend"},
        observability={
            "log_group": "/aws/lambda/my-function",
            "xray_name": "my-function",
            "metric_namespace": "AWS/Lambda"
        },
        config_fingerprint={"hash": "abc123", "updated_at": datetime.now(timezone.utc).isoformat()},
        staleness={"last_seen": datetime.now(timezone.utc).isoformat(), "flag": False}
    )
    
    ddb_node = GraphNode(
        arn="arn:aws:dynamodb:eu-west-1:123456789012:table/my-table",
        type="dynamodb",
        name="my-table",
        account_id="123456789012",
        region="eu-west-1",
        tags={"Environment": "prod", "Team": "backend"},
        observability={
            "metric_namespace": "AWS/DynamoDB"
        },
        staleness={"last_seen": datetime.now(timezone.utc).isoformat(), "flag": False}
    )
    
    # Create sample edge
    lambda_ddb_edge = GraphEdge(
        from_arn="arn:aws:lambda:eu-west-1:123456789012:function:my-function",
        to_arn="arn:aws:dynamodb:eu-west-1:123456789012:table/my-table",
        rel="READS",
        evidence_sources=["X_RAY", "LOGS"],
        confidence=0.85,
        first_seen=datetime.now(timezone.utc).isoformat(),
        last_seen=datetime.now(timezone.utc).isoformat(),
        account_id="123456789012",
        region="eu-west-1"
    )
    
    # Create observability pointer
    lambda_pointer = ObservabilityPointer(
        arn="arn:aws:lambda:eu-west-1:123456789012:function:my-function",
        logs="/aws/lambda/my-function",
        traces={
            "xray_name": "my-function",
            "last_trace_ids": ["trace-123", "trace-456"]
        },
        metrics={
            "namespace": "AWS/Lambda",
            "names": ["Duration", "Errors", "Invocations"]
        },
        account_id="123456789012",
        region="eu-west-1",
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    
    # Store nodes and edges
    print("Storing nodes and edges...")
    await memory_client.upsert_node(lambda_node)
    await memory_client.upsert_node(ddb_node)
    await memory_client.upsert_edge(lambda_ddb_edge)
    await memory_client.upsert_pointer(lambda_pointer)
    
    # Create sample incident
    incident = Incident(
        incident_id="INC-001",
        nodes=["arn:aws:lambda:eu-west-1:123456789012:function:my-function"],
        root_cause="Lambda function timeout due to DynamoDB throttling",
        signals=["timeout", "throttling", "high latency"],
        fix="Increase DynamoDB capacity and optimize Lambda function",
        useful_queries="CloudWatch metrics, X-Ray traces, DynamoDB capacity",
        pattern_ids=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        account_id="123456789012",
        region="eu-west-1"
    )
    
    await memory_client.save_incident(incident)
    
    # Create sample pattern (no embeddings)
    pattern = Pattern(
        pattern_id="P-001",
        title="Lambda-DynamoDB Timeout Pattern",
        tags=["lambda", "dynamodb", "timeout", "throttling"],
        signatures={
            "topology_signature": "a3f5e8c2d1b4a7e9",  # Example hash
            "resource_types": ["dynamodb", "lambda"],
            "relationship_types": ["READS"],
            "depth": 1,
            "stack_signature": "lambda-dynamodb:READS",
            "topology_motif": ["lambda->dynamodb(READS)"]
        },
        playbook_steps="1. Check DynamoDB capacity\n2. Review Lambda timeout settings\n3. Optimize queries\n4. Enable auto-scaling",
        popularity=0.0,
        last_used_at=datetime.now(timezone.utc).isoformat(),
        match_count=0
    )
    
    await memory_client.save_pattern(pattern)
    print("✅ Pattern created and stored")
    
    # Example: RAG retrieval
    print("\n🔍 Testing RAG retrieval...")
    
    # Retrieve context for the Lambda function
    rag_result = await memory_client.retrieve_context("my-function", k_hop=2)
    
    if rag_result:
        print(f"✅ Retrieved context for focus node: {rag_result.focus_node}")
        print(f"   Subgraph nodes: {len(rag_result.subgraph['nodes'])}")
        print(f"   Subgraph edges: {len(rag_result.subgraph['edges'])}")
        print(f"   Patterns: {len(rag_result.patterns)}")
        print(f"   Related incidents: {len(rag_result.related_incidents)}")
        
        # Show some details
        if rag_result.subgraph['nodes']:
            print("\n   Discovered resources:")
            for node in rag_result.subgraph['nodes'][:3]:
                print(f"   - {node.get('type', 'unknown')}: {node.get('name', 'unknown')}")
        
        if rag_result.patterns:
            print("\n   Matched patterns:")
            for pattern in rag_result.patterns[:2]:
                print(f"   - {pattern.get('title', 'Unknown')}")
                print(f"     Tags: {', '.join(pattern.get('tags', []))}")
        
        if rag_result.related_incidents:
            print("\n   Related incidents:")
            for incident in rag_result.related_incidents[:2]:
                print(f"   - {incident.get('incident_id', 'Unknown')}")
                print(f"     Root cause: {incident.get('root_cause', '')[:100]}...")
    else:
        print("❌ No context retrieved")
    
    # Example: Graph builder
    print("\n🔧 Testing graph builder...")
    
    graph_builder = GraphBuilder(account_id="123456789012", region="eu-west-1")
    
    # Simulate X-Ray trace data
    sample_trace = {
        "Segments": [
            {
                "Document": {
                    "name": "my-function",
                    "origin": "AWS::Lambda::Function",
                    "resource_arn": "arn:aws:lambda:eu-west-1:123456789012:function:my-function",
                    "subsegments": [
                        {
                            "name": "DynamoDB",
                            "resource_arn": "arn:aws:dynamodb:eu-west-1:123456789012:table/my-table",
                            "start_time": datetime.now(timezone.utc).isoformat(),
                            "end_time": datetime.now(timezone.utc).isoformat()
                        }
                    ]
                }
            }
        ]
    }
    
    nodes, edges, pointers = graph_builder.extract_from_trace(sample_trace)
    print(f"✅ Extracted {len(nodes)} nodes, {len(edges)} edges, {len(pointers)} pointers from trace")
    
    print("\n✅ RAG Memory System example completed successfully!")
    print("\nThis example demonstrated:")
    print("- Creating OpenSearch indices for graph storage")
    print("- Storing nodes, edges, and observability pointers")
    print("- Saving incidents and patterns with embeddings")
    print("- RAG retrieval with k-hop subgraph traversal")
    print("- Graph building from X-Ray traces")


if __name__ == "__main__":
    asyncio.run(main())