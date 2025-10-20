#!/usr/bin/env python3
"""
Simple test to verify trace parsing logic works.
"""

import json
import sys
import os
from unittest.mock import patch

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from promptrca.core.direct_orchestrator import DirectInvocationOrchestrator

def test_trace_parsing():
    """Test trace parsing with the actual trace data."""
    
    # Load the failing trace data
    with open('tests/test_data/failing_trace_1-68f65f93-51ce24da73e55aa666c2c92f.json', 'r') as f:
        trace_data = json.load(f)
    
    print("=== TRACE DATA ANALYSIS ===")
    print(f"Trace ID: {trace_data['Traces'][0]['Id']}")
    print(f"Duration: {trace_data['Traces'][0]['Duration']}s")
    print(f"Number of segments: {len(trace_data['Traces'][0]['Segments'])}")
    
    # Analyze each segment
    for i, segment_doc in enumerate(trace_data['Traces'][0]['Segments']):
        segment = json.loads(segment_doc['Document'])
        print(f"\n--- Segment {i+1} ---")
        print(f"Name: {segment.get('name', 'unknown')}")
        print(f"Origin: {segment.get('origin', 'unknown')}")
        
        # Check for errors/faults
        if segment.get('fault'):
            print(f"⚠️  FAULT: {segment.get('fault')}")
        if segment.get('error'):
            print(f"❌ ERROR: {segment.get('error')}")
            
        # Check HTTP status
        http_status = segment.get('http', {}).get('response', {}).get('status')
        if http_status:
            print(f"HTTP Status: {http_status}")
            
        # Check for cause/exception
        if segment.get('cause'):
            cause = segment.get('cause', {})
            print(f"🔥 CAUSE: {cause.get('message', 'Unknown error')}")
            
        # Check subsegments
        subsegments = segment.get('subsegments', [])
        if subsegments:
            print(f"Subsegments: {len(subsegments)}")
            for j, subsegment in enumerate(subsegments):
                print(f"  - {subsegment.get('name', 'unknown')}")
                sub_http_status = subsegment.get('http', {}).get('response', {}).get('status')
                if sub_http_status:
                    print(f"    HTTP: {sub_http_status}")
                
                # Check if this is a Step Functions call
                if subsegment.get('name') == 'STEPFUNCTIONS':
                    http_req = subsegment.get('http', {}).get('request', {})
                    if 'StartSyncExecution' in http_req.get('url', ''):
                        print(f"    🔍 Step Functions StartSyncExecution call detected!")
                        print(f"    📍 This is where permission errors would occur")
                        
        # Check AWS metadata for more details
        aws_meta = segment.get('aws', {})
        if aws_meta:
            print(f"AWS Metadata: {aws_meta}")
            
        # Check annotations
        annotations = segment.get('annotations', {})
        if annotations:
            print(f"Annotations: {annotations}")
    
    # Now test our parsing logic
    print("\n=== TESTING OUR PARSING LOGIC ===")
    
    orchestrator = DirectInvocationOrchestrator()
    
    # Mock the get_xray_trace function to return the data directly
    with patch('promptrca.tools.get_xray_trace') as mock_get_trace:
        mock_get_trace.return_value = json.dumps(trace_data)
        
        # Test the deep analysis
        import asyncio
        facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-68f65f93-51ce24da73e55aa666c2c92f"))
        
        print(f"Generated {len(facts)} facts:")
        for i, fact in enumerate(facts):
            print(f"{i+1}. [{fact.source}] {fact.content} (confidence: {fact.confidence})")

if __name__ == "__main__":
    test_trace_parsing()