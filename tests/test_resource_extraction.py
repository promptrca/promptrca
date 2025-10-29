#!/usr/bin/env python3
"""
Test suite for resource extraction from X-Ray traces.
Tests the parsing logic that discovers AWS resources from trace data.
"""

import json
import pytest
from unittest.mock import patch
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from promptrca.tools.xray_tools import get_all_resources_from_trace


class TestResourceExtraction:
    """Test resource extraction logic with various trace patterns."""
    
    def test_api_gateway_stepfunctions_extraction(self):
        """Test extraction of API Gateway and Step Functions from real trace."""
        
        # Mock trace data with API Gateway -> Step Functions
        trace_data = {
            "Traces": [
                {
                    "Id": "1-test-trace",
                    "Duration": 0.054,
                    "IsPartial": False,
                    "Segments": [
                        {
                            "Id": "segment-1",
                            "Document": json.dumps({
                                "id": "segment-1",
                                "name": "sherlock-test-test-api/test",
                                "origin": "AWS::ApiGateway::Stage",
                                "resource_arn": "arn:aws:apigateway:eu-west-1::/restapis/142gh05m9a/stages/test",
                                "subsegments": [
                                    {
                                        "name": "STEPFUNCTIONS",
                                        "http": {
                                            "request": {
                                                "url": "https://sync-states.eu-west-1.amazonaws.com/?Action=StartSyncExecution"
                                            }
                                        }
                                    }
                                ]
                            })
                        },
                        {
                            "Id": "segment-2", 
                            "Document": json.dumps({
                                "id": "segment-2",
                                "name": "STEPFUNCTIONS",
                                "origin": "AWS::STEPFUNCTIONS",
                                "aws": {
                                    "execution_arn": "arn:aws:states:eu-west-1:840181656986:execution:test-statemachine:exec-123"
                                }
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-test-trace")
            parsed_result = json.loads(result)
            
            # Verify basic structure
            assert parsed_result["trace_id"] == "1-test-trace"
            assert parsed_result["duration"] == 0.054
            assert parsed_result["resource_count"] == 2
            
            resources = parsed_result["resources"]
            
            # Should detect API Gateway
            api_resources = [r for r in resources if r["type"] == "apigateway"]
            assert len(api_resources) == 1
            # Should extract API ID from ARN (more accurate than segment name)
            assert api_resources[0]["name"] == "142gh05m9a"  # From ARN: /restapis/142gh05m9a/stages/test
            assert api_resources[0]["stage"] == "test"
            
            # Should detect Step Functions
            sf_resources = [r for r in resources if r["type"] == "stepfunctions"]
            assert len(sf_resources) == 1
            assert "arn:aws:states:eu-west-1:840181656986:execution:test-statemachine:exec-123" in sf_resources[0]["execution_arn"]
    
    def test_lambda_function_extraction(self):
        """Test extraction of Lambda functions from traces."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-lambda-trace",
                    "Duration": 0.123,
                    "Segments": [
                        {
                            "Id": "lambda-segment",
                            "Document": json.dumps({
                                "id": "lambda-segment",
                                "name": "my-test-function",
                                "origin": "AWS::Lambda::Function",
                                "resource_arn": "arn:aws:lambda:us-east-1:123456789012:function:my-test-function"
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-lambda-trace")
            parsed_result = json.loads(result)
            
            resources = parsed_result["resources"]
            
            # Should detect Lambda function
            lambda_resources = [r for r in resources if r["type"] == "lambda"]
            assert len(lambda_resources) == 1
            assert lambda_resources[0]["name"] == "my-test-function"
            assert "arn:aws:lambda:us-east-1:123456789012:function:my-test-function" in lambda_resources[0]["arn"]
    
    def test_deduplication_logic(self):
        """Test that duplicate resources are not included."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-dup-trace",
                    "Duration": 0.1,
                    "Segments": [
                        {
                            "Id": "segment-1",
                            "Document": json.dumps({
                                "name": "my-api/prod",
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        },
                        {
                            "Id": "segment-2", 
                            "Document": json.dumps({
                                "name": "my-api/prod",  # Same API Gateway
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-dup-trace")
            parsed_result = json.loads(result)
            
            # Should only have one resource despite two segments
            assert parsed_result["resource_count"] == 1
            
            resources = parsed_result["resources"]
            api_resources = [r for r in resources if r["type"] == "apigateway"]
            assert len(api_resources) == 1
            assert api_resources[0]["name"] == "my-api"
            assert api_resources[0]["stage"] == "prod"
    
    def test_malformed_segment_handling(self):
        """Test handling of malformed or unparseable segments."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-malformed-trace",
                    "Duration": 0.05,
                    "Segments": [
                        {
                            "Id": "good-segment",
                            "Document": json.dumps({
                                "name": "valid-function",
                                "origin": "AWS::Lambda::Function"
                            })
                        },
                        {
                            "Id": "bad-segment",
                            "Document": "invalid-json-{{"  # Malformed JSON
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-malformed-trace")
            parsed_result = json.loads(result)
            
            # Should still extract the valid resource
            assert parsed_result["resource_count"] == 1
            resources = parsed_result["resources"]
            assert resources[0]["name"] == "valid-function"
            assert resources[0]["type"] == "lambda"
    
    def test_trace_not_found(self):
        """Test handling when trace is not found."""
        
        trace_data = {"Traces": []}  # Empty traces
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-missing-trace")
            parsed_result = json.loads(result)
            
            # Should return error
            assert "error" in parsed_result
            assert parsed_result["trace_id"] == "1-missing-trace"
            assert "Trace not found" in parsed_result["error"]
    
    def test_complex_api_gateway_parsing(self):
        """Test parsing of complex API Gateway names with multiple path segments."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-complex-api",
                    "Duration": 0.1,
                    "Segments": [
                        {
                            "Id": "api-segment",
                            "Document": json.dumps({
                                "name": "abc123def/prod/users/profile",  # Complex path
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-complex-api")
            parsed_result = json.loads(result)
            
            resources = parsed_result["resources"]
            api_resources = [r for r in resources if r["type"] == "apigateway"]
            
            # Should extract API ID and stage correctly
            assert len(api_resources) == 1
            assert api_resources[0]["name"] == "abc123def"
            assert api_resources[0]["stage"] == "prod"


    def test_trace_id_variations(self):
        """Test different trace ID formats (with/without Root= prefix)."""
        
        test_cases = [
            "1-68f622d0-2cfc080243ee63df62fc57a8",  # Standard format
            "Root=1-68f622d0-2cfc080243ee63df62fc57a8",  # With Root= prefix
            "1-12345678-abcdef1234567890abcdef12",  # Different hex values
        ]
        
        for trace_id in test_cases:
            trace_data = {
                "Traces": [
                    {
                        "Id": trace_id.replace("Root=", ""),  # AWS returns without Root=
                        "Duration": 0.1,
                        "Segments": [
                            {
                                "Id": "test-segment",
                                "Document": json.dumps({
                                    "name": "test-function",
                                    "origin": "AWS::Lambda::Function"
                                })
                            }
                        ]
                    }
                ]
            }
            
            with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
                mock_client = mock_get_client.return_value.get_client.return_value
                mock_client.batch_get_traces.return_value = trace_data
                
                result = get_all_resources_from_trace(trace_id)
                parsed_result = json.loads(result)
                
                # Should work regardless of trace ID format
                assert parsed_result["trace_id"] == trace_id
                assert parsed_result["resource_count"] == 1
                assert parsed_result["resources"][0]["type"] == "lambda"
    
    def test_arn_based_resource_detection(self):
        """Test resource detection from ARNs in segments."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-arn-test",
                    "Duration": 0.1,
                    "Segments": [
                        {
                            "Id": "lambda-arn-segment",
                            "Document": json.dumps({
                                "name": "some-generic-name",
                                "resource_arn": "arn:aws:lambda:us-east-1:123456789012:function:my-lambda-function",
                                "origin": "AWS::Lambda::Function"
                            })
                        },
                        {
                            "Id": "api-arn-segment", 
                            "Document": json.dumps({
                                "name": "generic-api-name",
                                "resource_arn": "arn:aws:apigateway:eu-west-1::/restapis/abc123def456/stages/production",
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        },
                        {
                            "Id": "stepfunctions-arn-segment",
                            "Document": json.dumps({
                                "name": "STEPFUNCTIONS",
                                "origin": "AWS::STEPFUNCTIONS",
                                "aws": {
                                    "execution_arn": "arn:aws:states:us-west-2:123456789012:execution:MyStateMachine:execution-name-123"
                                }
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-arn-test")
            parsed_result = json.loads(result)
            
            assert parsed_result["resource_count"] == 3
            resources = parsed_result["resources"]
            
            # Lambda from ARN
            lambda_resources = [r for r in resources if r["type"] == "lambda"]
            assert len(lambda_resources) == 1
            assert "my-lambda-function" in lambda_resources[0]["arn"]
            
            # API Gateway from ARN  
            api_resources = [r for r in resources if r["type"] == "apigateway"]
            assert len(api_resources) == 1
            # Should extract API ID from ARN if available
            
            # Step Functions from execution ARN
            sf_resources = [r for r in resources if r["type"] == "stepfunctions"]
            assert len(sf_resources) == 1
            assert "MyStateMachine" in sf_resources[0]["execution_arn"]
    
    def test_edge_case_service_names(self):
        """Test edge cases in service name parsing."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-edge-cases",
                    "Duration": 0.1,
                    "Segments": [
                        {
                            "Id": "empty-name-segment",
                            "Document": json.dumps({
                                "name": "",  # Empty name
                                "origin": "AWS::Lambda::Function"
                            })
                        },
                        {
                            "Id": "no-name-segment",
                            "Document": json.dumps({
                                # Missing name field
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        },
                        {
                            "Id": "special-chars-segment",
                            "Document": json.dumps({
                                "name": "my-api_with.special-chars/prod/v1",
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        },
                        {
                            "Id": "single-part-api",
                            "Document": json.dumps({
                                "name": "just-api-id",  # No stage part
                                "origin": "AWS::ApiGateway::Stage"
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-edge-cases")
            parsed_result = json.loads(result)
            
            # Should handle edge cases gracefully
            resources = parsed_result["resources"]
            
            # Should extract what it can
            api_resources = [r for r in resources if r["type"] == "apigateway"]
            
            # Should handle special characters and single parts
            special_char_api = [r for r in api_resources if "my-api_with.special-chars" in r["name"]]
            if special_char_api:
                assert special_char_api[0]["stage"] == "prod"
    
    def test_unknown_service_types(self):
        """Test handling of unknown or new service types."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-unknown-services",
                    "Duration": 0.1,
                    "Segments": [
                        {
                            "Id": "unknown-segment",
                            "Document": json.dumps({
                                "name": "some-new-service",
                                "origin": "AWS::NewService::Resource"  # Unknown service
                            })
                        },
                        {
                            "Id": "no-origin-segment",
                            "Document": json.dumps({
                                "name": "mystery-service"
                                # No origin field
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-unknown-services")
            parsed_result = json.loads(result)
            
            # Should not crash on unknown services
            # May have 0 resources if none are recognized, which is fine
            assert "error" not in parsed_result
            assert "resource_count" in parsed_result
    
    def test_multiple_executions_same_statemachine(self):
        """Test handling multiple executions of the same state machine."""
        
        trace_data = {
            "Traces": [
                {
                    "Id": "1-multiple-executions",
                    "Duration": 0.2,
                    "Segments": [
                        {
                            "Id": "exec1-segment",
                            "Document": json.dumps({
                                "name": "STEPFUNCTIONS",
                                "origin": "AWS::STEPFUNCTIONS",
                                "aws": {
                                    "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:MyStateMachine:execution-1"
                                }
                            })
                        },
                        {
                            "Id": "exec2-segment",
                            "Document": json.dumps({
                                "name": "STEPFUNCTIONS", 
                                "origin": "AWS::STEPFUNCTIONS",
                                "aws": {
                                    "execution_arn": "arn:aws:states:us-east-1:123456789012:execution:MyStateMachine:execution-2"
                                }
                            })
                        }
                    ]
                }
            ]
        }
        
        with patch('promptrca.tools.xray_tools.get_aws_client') as mock_get_client:
            mock_client = mock_get_client.return_value.get_client.return_value
            mock_client.batch_get_traces.return_value = trace_data
            
            result = get_all_resources_from_trace("1-multiple-executions")
            parsed_result = json.loads(result)
            
            # Should detect both executions as separate resources
            sf_resources = [r for r in parsed_result["resources"] if r["type"] == "stepfunctions"]
            assert len(sf_resources) == 2
            
            # Should have different execution ARNs
            execution_arns = [r["execution_arn"] for r in sf_resources]
            assert len(set(execution_arns)) == 2  # Should be unique


if __name__ == "__main__":
    pytest.main([__file__, "-v"])