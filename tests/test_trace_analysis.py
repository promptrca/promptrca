#!/usr/bin/env python3
"""
Test suite for X-Ray trace analysis logic.
Tests the parsing of trace data to extract service interactions and technical details.
"""

import json
import pytest
import asyncio
from unittest.mock import patch
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from promptrca.core.direct_orchestrator import DirectInvocationOrchestrator
from promptrca.models import Fact


class TestTraceAnalysis:
    """Test X-Ray trace analysis with real trace data."""
    
    @pytest.fixture
    def successful_trace_data(self):
        """Load successful trace data (API Gateway -> Step Functions, HTTP 200)."""
        test_data_path = Path(__file__).parent / "test_data" / "xray_trace_1-68f622d0-2cfc080243ee63df62fc57a8.json"
        with open(test_data_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        return DirectInvocationOrchestrator()
    
    def test_successful_trace_parsing(self, orchestrator, successful_trace_data):
        """Test parsing of successful API Gateway -> Step Functions trace."""
        
        with patch('promptrca.tools.get_xray_trace') as mock_get_trace:
            mock_get_trace.return_value = json.dumps(successful_trace_data)
            
            # Run trace analysis
            facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-68f622d0-2cfc080243ee63df62fc57a8"))
            
            # Should generate multiple facts
            assert len(facts) >= 3
            
            # Should have duration fact
            duration_facts = [f for f in facts if "duration" in f.content.lower()]
            assert len(duration_facts) == 1
            assert "0.054s" in duration_facts[0].content
            assert duration_facts[0].source == 'xray_trace'
            
            # Should detect API Gateway -> Step Functions interaction
            interaction_facts = [f for f in facts if "StartSyncExecution" in f.content]
            assert len(interaction_facts) == 1
            assert "API Gateway invoked Step Functions StartSyncExecution" in interaction_facts[0].content
            assert interaction_facts[0].confidence == 0.95
            
            # Should capture HTTP response status
            http_facts = [f for f in facts if "HTTP 200" in f.content]
            assert len(http_facts) == 1
            assert "Step Functions call returned HTTP 200" in http_facts[0].content
            
            # Should NOT make assumptions about permissions (that's for other specialists)
            permission_facts = [f for f in facts if "permission" in f.content.lower()]
            assert len(permission_facts) == 0
    
    def test_trace_with_explicit_errors(self, orchestrator):
        """Test parsing of trace with explicit faults/errors."""
        
        error_trace_data = {
            "Traces": [
                {
                    "Id": "1-error-trace-123",
                    "Duration": 0.123,
                    "Segments": [
                        {
                            "Id": "segment-1",
                            "Document": json.dumps({
                                "id": "segment-1",
                                "name": "test-api",
                                "fault": True,
                                "error": True,
                                "http": {"response": {"status": 500}},
                                "cause": {
                                    "id": "error-123",
                                    "message": "Internal server error occurred"
                                }
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.get_xray_trace') as mock_get_trace:
            mock_get_trace.return_value = json.dumps(error_trace_data)
            
            facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-error-trace-123"))
            
            # Should detect the explicit error
            error_facts = [f for f in facts if "Internal server error occurred" in f.content]
            assert len(error_facts) == 1
            
            # Should detect HTTP 500
            http_facts = [f for f in facts if "HTTP 500" in f.content]
            assert len(http_facts) == 1
            
            # Should detect faulted service
            fault_facts = [f for f in facts if "test-api" in f.content and "fault" in f.content.lower()]
            assert len(fault_facts) >= 1
    
    def test_trace_service_flow_extraction(self, orchestrator, successful_trace_data):
        """Test that we correctly extract the service flow from traces."""
        
        with patch('promptrca.tools.get_xray_trace') as mock_get_trace:
            mock_get_trace.return_value = json.dumps(successful_trace_data)
            
            facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-68f622d0-2cfc080243ee63df62fc57a8"))
            
            # Extract metadata to verify service flow detection
            stepfunctions_facts = [f for f in facts if f.metadata.get('service_call') == 'stepfunctions']
            assert len(stepfunctions_facts) == 1
            assert stepfunctions_facts[0].metadata.get('action') == 'StartSyncExecution'
            
            # Verify we capture the right HTTP status
            http_facts = [f for f in facts if f.metadata.get('http_status') == 200]
            assert len(http_facts) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])