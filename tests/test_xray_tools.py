#!/usr/bin/env python3
"""
Test suite for X-Ray tools with mocked data.
This allows testing the parsing logic without making actual AWS calls.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import the tools we want to test
from src.promptrca.tools.xray_tools import get_xray_trace
from src.promptrca.core.direct_orchestrator import DirectInvocationOrchestrator


class TestXRayTools:
    """Test X-Ray tool parsing logic with mocked data."""
    
    @pytest.fixture
    def sample_trace_data(self):
        """Load sample trace data from test files."""
        test_data_path = Path(__file__).parent / "test_data" / "xray_trace_1-68f622d0-2cfc080243ee63df62fc57a8.json"
        with open(test_data_path, 'r') as f:
            return json.load(f)
    
    @pytest.fixture
    def mock_aws_client(self):
        """Mock AWS client to return test data."""
        mock_client = MagicMock()
        return mock_client
    
    def test_get_xray_trace_parsing(self, sample_trace_data, mock_aws_client):
        """Test that get_xray_trace correctly parses trace data."""
        # Mock the boto3 client to return our test data
        mock_aws_client.batch_get_traces.return_value = sample_trace_data
        
        with patch('src.promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_get_client.return_value.xray = mock_aws_client
            
            # Call the function
            result = get_xray_trace("1-68f622d0-2cfc080243ee63df62fc57a8")
            
            # Parse the result
            parsed_result = json.loads(result)
            
            # Verify the structure
            assert "Traces" in parsed_result
            assert len(parsed_result["Traces"]) == 1
            
            trace = parsed_result["Traces"][0]
            assert trace["Id"] == "1-68f622d0-2cfc080243ee63df62fc57a8"
            assert trace["Duration"] == 0.054
            assert len(trace["Segments"]) == 2
    
    def test_deep_trace_analysis_successful_case(self, sample_trace_data):
        """Test deep trace analysis with successful trace (no errors)."""
        orchestrator = DirectInvocationOrchestrator()
        
        # Mock the get_xray_trace function to return our test data
        with patch('src.promptrca.tools.xray_tools.get_xray_trace') as mock_get_trace:
            mock_get_trace.return_value = json.dumps(sample_trace_data)
            
            # Test the deep analysis
            import asyncio
            facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-68f622d0-2cfc080243ee63df62fc57a8"))
            
            # Should get facts about the trace
            assert len(facts) > 0
            
            # Should have duration fact
            duration_facts = [f for f in facts if "duration" in f.content.lower()]
            assert len(duration_facts) == 1
            assert "0.054s" in duration_facts[0].content
            
            # Should not have error facts (this is a successful trace)
            error_facts = [f for f in facts if "error" in f.content.lower()]
            assert len(error_facts) == 0


class TestXRayToolsWithErrorTrace:
    """Test X-Ray tools with error scenarios."""
    
    @pytest.fixture
    def error_trace_data(self):
        """Create a mock trace with permission error."""
        return {
            "Traces": [
                {
                    "Id": "1-68f622d0-2cfc080243ee63df62fc57a8",
                    "Duration": 0.123,
                    "LimitExceeded": False,
                    "Segments": [
                        {
                            "Id": "7d3bfe9640ace210",
                            "Document": json.dumps({
                                "id": "7d3bfe9640ace210",
                                "name": "promptrca-test-test-api",
                                "start_time": 1.760961232443E9,
                                "trace_id": "1-68f622d0-2cfc080243ee63df62fc57a8",
                                "end_time": 1.760961232497E9,
                                "fault": True,
                                "error": True,
                                "http": {
                                    "response": {
                                        "status": 502
                                    }
                                },
                                "cause": {
                                    "id": "permission-error-123",
                                    "message": "User: arn:aws:sts::840181656986:assumed-role/promptrca-test-test-api-role/promptrca-test-test-api is not authorized to perform: states:StartSyncExecution on resource: arn:aws:states:eu-west-1:840181656986:stateMachine:promptrca-test-test-statemachine with an explicit deny in an identity-based policy"
                                },
                                "subsegments": []
                            })
                        }
                    ]
                }
            ],
            "UnprocessedTraceIds": []
        }
    
    def test_deep_trace_analysis_error_case(self, error_trace_data):
        """Test deep trace analysis with error trace."""
        orchestrator = DirectInvocationOrchestrator()
        
        # Mock the get_xray_trace function to return error data
        with patch('src.promptrca.tools.xray_tools.get_xray_trace') as mock_get_trace:
            mock_get_trace.return_value = json.dumps(error_trace_data)
            
            # Test the deep analysis
            import asyncio
            facts = asyncio.run(orchestrator._analyze_xray_trace_deep("1-68f622d0-2cfc080243ee63df62fc57a8"))
            
            # Should get multiple facts
            assert len(facts) >= 3
            
            # Should have duration fact
            duration_facts = [f for f in facts if "duration" in f.content.lower()]
            assert len(duration_facts) == 1
            assert "0.123s" in duration_facts[0].content
            
            # Should have HTTP 502 fact
            http_facts = [f for f in facts if "HTTP 502" in f.content]
            assert len(http_facts) == 1
            
            # Should have the permission error fact
            permission_facts = [f for f in facts if "states:StartSyncExecution" in f.content]
            assert len(permission_facts) == 1
            assert "not authorized to perform" in permission_facts[0].content
            
            # Should have fault/error summary facts
            fault_facts = [f for f in facts if "promptrca-test-test-api" in f.content and ("fault" in f.content.lower() or "error" in f.content.lower())]
            assert len(fault_facts) >= 1


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])