#!/usr/bin/env python3
"""
Test script for the new Swarm orchestrator implementation.

This script demonstrates how to use the Swarm-based orchestrator
following Strands Agents best practices.
"""

import asyncio
import json
import os
from src.promptrca.core.investigator import PromptRCAInvestigator


async def test_swarm_orchestrator():
    """Test the Swarm orchestrator with a sample investigation."""
    
    print("🤖 Testing Swarm Orchestrator (Strands Best Practices)")
    print("=" * 60)
    
    # Sample investigation inputs
    sample_inputs = {
        "xray_trace_id": "1-67890123-abcdef1234567890abcdef12",
        "investigation_target": {
            "type": "lambda",
            "name": "sherlock-test-test-faulty-lambda",
            "region": "eu-west-1"
        }
    }
    
    try:
        # Create investigator with Swarm orchestrator
        investigator = PromptRCAInvestigator(
            region="eu-west-1",
            xray_trace_id=sample_inputs["xray_trace_id"],
            investigation_target=sample_inputs["investigation_target"],
            orchestrator_type="swarm"  # Use Swarm pattern
        )
        
        print(f"✅ Investigator initialized with orchestrator: {investigator.orchestrator_type}")
        print(f"📍 Region: {investigator.region}")
        print(f"🔍 Trace ID: {investigator.xray_trace_id}")
        print()
        
        # Run investigation
        print("🚀 Starting Swarm investigation...")
        report = await investigator.investigate()
        
        print("=" * 60)
        print("📊 INVESTIGATION RESULTS")
        print("=" * 60)
        
        print(f"Status: {report.status}")
        print(f"Duration: {report.duration_seconds:.2f}s")
        print(f"Facts collected: {len(report.facts)}")
        print(f"Hypotheses generated: {len(report.hypotheses)}")
        print(f"Root cause confidence: {report.root_cause_analysis.confidence_score:.2f}")
        print()
        
        # Show some facts
        if report.facts:
            print("🔍 Sample Facts:")
            for i, fact in enumerate(report.facts[:3]):  # Show first 3 facts
                print(f"  {i+1}. [{fact.source}] {fact.content[:100]}...")
            print()
        
        # Show hypotheses
        if report.hypotheses:
            print("💡 Hypotheses:")
            for i, hypothesis in enumerate(report.hypotheses):
                print(f"  {i+1}. [{hypothesis.type}] {hypothesis.description[:100]}...")
            print()
        
        # Show root cause
        if report.root_cause_analysis:
            print("🎯 Root Cause Analysis:")
            print(f"  Summary: {report.root_cause_analysis.analysis_summary[:200]}...")
            print(f"  Confidence: {report.root_cause_analysis.confidence_score:.2f}")
            print()
        
        print("✅ Swarm investigation completed successfully!")
        
    except Exception as e:
        print(f"❌ Investigation failed: {e}")
        import traceback
        traceback.print_exc()


async def compare_orchestrators():
    """Compare Swarm vs Direct orchestrators."""
    
    print("⚖️  Comparing Orchestrators")
    print("=" * 60)
    
    sample_inputs = {
        "xray_trace_id": "1-67890123-abcdef1234567890abcdef12",
        "investigation_target": {
            "type": "lambda", 
            "name": "test-function",
            "region": "us-east-1"
        }
    }
    
    results = {}
    
    for orchestrator_type in ["direct", "swarm"]:
        print(f"\n🔄 Testing {orchestrator_type.upper()} orchestrator...")
        
        try:
            investigator = PromptRCAInvestigator(
                region="us-east-1",
                xray_trace_id=sample_inputs["xray_trace_id"],
                investigation_target=sample_inputs["investigation_target"],
                orchestrator_type=orchestrator_type
            )
            
            import time
            start_time = time.time()
            report = await investigator.investigate()
            end_time = time.time()
            
            results[orchestrator_type] = {
                "status": report.status,
                "duration": end_time - start_time,
                "facts": len(report.facts),
                "hypotheses": len(report.hypotheses),
                "confidence": report.root_cause_analysis.confidence_score if report.root_cause_analysis else 0
            }
            
            print(f"  ✅ {orchestrator_type.upper()}: {report.status} in {results[orchestrator_type]['duration']:.2f}s")
            
        except Exception as e:
            print(f"  ❌ {orchestrator_type.upper()}: Failed - {e}")
            results[orchestrator_type] = {"status": "failed", "error": str(e)}
    
    # Compare results
    print("\n📊 COMPARISON RESULTS")
    print("=" * 60)
    
    for orchestrator_type, result in results.items():
        print(f"{orchestrator_type.upper()}:")
        if result["status"] == "failed":
            print(f"  Status: ❌ {result['status']} - {result.get('error', 'Unknown error')}")
        else:
            print(f"  Status: ✅ {result['status']}")
            print(f"  Duration: {result['duration']:.2f}s")
            print(f"  Facts: {result['facts']}")
            print(f"  Hypotheses: {result['hypotheses']}")
            print(f"  Confidence: {result['confidence']:.2f}")
        print()


if __name__ == "__main__":
    print("🧪 PromptRCA Swarm Orchestrator Test")
    print("=" * 60)
    
    # Set environment variable to test different orchestrators
    test_mode = os.getenv("TEST_MODE", "swarm")
    
    if test_mode == "compare":
        asyncio.run(compare_orchestrators())
    else:
        asyncio.run(test_swarm_orchestrator())