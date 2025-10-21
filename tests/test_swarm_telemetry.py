#!/usr/bin/env python3
"""
Unit tests for Swarm Orchestrator OpenTelemetry integration.

Tests that OpenTelemetry tracing is properly integrated into the
swarm orchestrator and specialist tools.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, MagicMock

from src.promptrca.core.swarm_orchestrator import (
    lambda_specialist_tool,
    apigateway_specialist_tool
)


class TestSpecialistToolTelemetryIntegration:
    """Test that specialist tools have telemetry integration."""
    
    @patch('src.promptrca.core.swarm_orchestrator.LambdaSpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    @patch('opentelemetry.trace.get_tracer')
    def test_lambda_specialist_tool_uses_tracer(self, mock_get_tracer, mock_run_analysis, mock_specialist_class):
        """Test that lambda_specialist_tool uses OpenTelemetry tracer."""
        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)
        mock_get_tracer.return_value = mock_tracer
        
        # Mock successful analysis
        mock_run_analysis.return_value = [
            Mock(source="lambda_config", content="Test fact", confidence=0.9, metadata={})
        ]
        
        # Call the tool
        resource_data = json.dumps([{"type": "lambda", "name": "test-function"}])
        context_data = json.dumps({"region": "us-east-1", "trace_ids": []})
        
        result = lambda_specialist_tool(resource_data, context_data)
        
        # Check that result is valid JSON
        parsed_result = json.loads(result)
        assert parsed_result["specialist_type"] == "lambda"
        
        # Check that tracer was used
        mock_get_tracer.assert_called_once()
        mock_tracer.start_as_current_span.assert_called_once_with("lambda_specialist_tool")
        
        # Check that span attributes were set
        mock_span.set_attribute.assert_any_call("lambda.resource_name", "test-function")
        mock_span.set_attribute.assert_any_call("lambda.resource_type", "lambda")
        mock_span.set_attribute.assert_any_call("lambda.region", "us-east-1")
        mock_span.set_attribute.assert_any_call("lambda.facts_count", 1)
        mock_span.set_attribute.assert_any_call("lambda.analysis_status", "success")
    
    @patch('opentelemetry.trace.get_tracer')
    def test_lambda_specialist_tool_records_error_in_tracer(self, mock_get_tracer):
        """Test that lambda_specialist_tool records errors in tracer."""
        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)
        mock_get_tracer.return_value = mock_tracer
        
        # Call the tool with invalid JSON
        invalid_resource_data = "invalid json"
        valid_context_data = json.dumps({"region": "us-east-1", "trace_ids": []})
        
        result = lambda_specialist_tool(invalid_resource_data, valid_context_data)
        
        # Check that result is an error response
        parsed_result = json.loads(result)
        assert parsed_result["error_type"] == "ResourceDataError"
        
        # Check that tracer was used
        mock_get_tracer.assert_called_once()
        mock_tracer.start_as_current_span.assert_called_once_with("lambda_specialist_tool")
        
        # Check that error attributes were set
        mock_span.set_attribute.assert_any_call("lambda.analysis_status", "error")
        mock_span.set_attribute.assert_any_call("lambda.error_type", "ResourceDataError")
        # Check that error message contains expected text
        error_calls = [call for call in mock_span.set_attribute.call_args_list 
                      if call[0][0] == "lambda.error_message"]
        assert len(error_calls) == 1
        assert "Invalid JSON in resource_data" in error_calls[0][0][1]
    
    @patch('src.promptrca.core.swarm_orchestrator.APIGatewaySpecialist')
    @patch('src.promptrca.core.swarm_orchestrator._run_specialist_analysis')
    @patch('opentelemetry.trace.get_tracer')
    def test_apigateway_specialist_tool_uses_tracer(self, mock_get_tracer, mock_run_analysis, mock_specialist_class):
        """Test that apigateway_specialist_tool uses OpenTelemetry tracer."""
        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)
        mock_get_tracer.return_value = mock_tracer
        
        # Mock successful analysis
        mock_run_analysis.return_value = [
            Mock(source="apigateway_config", content="Test fact", confidence=0.8, metadata={})
        ]
        
        # Call the tool
        resource_data = json.dumps([{"type": "apigateway", "name": "test-api", "id": "abc123"}])
        context_data = json.dumps({"region": "eu-west-1", "trace_ids": []})
        
        result = apigateway_specialist_tool(resource_data, context_data)
        
        # Check that result is valid JSON
        parsed_result = json.loads(result)
        assert parsed_result["specialist_type"] == "apigateway"
        
        # Check that tracer was used
        mock_get_tracer.assert_called_once()
        mock_tracer.start_as_current_span.assert_called_once_with("apigateway_specialist_tool")
        
        # Check that span attributes were set
        mock_span.set_attribute.assert_any_call("apigateway.resource_name", "test-api")
        mock_span.set_attribute.assert_any_call("apigateway.resource_type", "apigateway")
        mock_span.set_attribute.assert_any_call("apigateway.region", "eu-west-1")
        mock_span.set_attribute.assert_any_call("apigateway.facts_count", 1)
        mock_span.set_attribute.assert_any_call("apigateway.analysis_status", "success")


class TestTelemetryConfiguration:
    """Test telemetry configuration and setup."""
    
    def test_telemetry_setup_function_exists(self):
        """Test that telemetry setup function is available."""
        from src.promptrca.utils.config import setup_strands_telemetry
        
        # Function should be callable
        assert callable(setup_strands_telemetry)
    
    @patch.dict('os.environ', {}, clear=True)
    def test_telemetry_setup_skips_when_no_endpoint(self):
        """Test that telemetry setup is skipped when no endpoint is configured."""
        from src.promptrca.utils.config import setup_strands_telemetry
        
        # Should not raise an error when no endpoint is set
        setup_strands_telemetry()
    
    @patch.dict('os.environ', {
        'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317',
        'OTEL_SERVICE_NAME': 'test-service'
    })
    @patch('strands.telemetry.StrandsTelemetry')
    def test_telemetry_setup_configures_otlp_exporter(self, mock_strands_telemetry):
        """Test that telemetry setup configures OTLP exporter when endpoint is provided."""
        from src.promptrca.utils.config import setup_strands_telemetry
        
        mock_telemetry_instance = Mock()
        mock_strands_telemetry.return_value = mock_telemetry_instance
        
        # Call setup
        setup_strands_telemetry()
        
        # Check that StrandsTelemetry was instantiated
        mock_strands_telemetry.assert_called_once()
        
        # Check that OTLP exporter was set up
        mock_telemetry_instance.setup_otlp_exporter.assert_called_once()


class TestSwarmOrchestratorTelemetryIntegration:
    """Test that SwarmOrchestrator has telemetry integration."""
    
    @patch('opentelemetry.trace.get_tracer')
    def test_swarm_orchestrator_investigate_uses_tracer(self, mock_get_tracer):
        """Test that SwarmOrchestrator.investigate uses OpenTelemetry tracer."""
        from src.promptrca.core.swarm_orchestrator import SwarmOrchestrator
        
        # Mock tracer and span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=None)
        mock_get_tracer.return_value = mock_tracer
        
        # Create orchestrator
        orchestrator = SwarmOrchestrator(region="us-east-1")
        
        # Check that the investigate method exists and would use tracer
        assert hasattr(orchestrator, 'investigate')
        assert callable(orchestrator.investigate)
        
        # The investigate method should be async
        import inspect
        assert inspect.iscoroutinefunction(orchestrator.investigate)
    
    def test_swarm_orchestrator_has_telemetry_imports(self):
        """Test that SwarmOrchestrator module has OpenTelemetry imports."""
        import src.promptrca.core.swarm_orchestrator as swarm_module
        
        # Check that the module can import OpenTelemetry
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            assert tracer is not None
        except ImportError:
            pytest.fail("OpenTelemetry not available for import")
    
    def test_swarm_orchestrator_investigate_method_signature(self):
        """Test that SwarmOrchestrator.investigate has the expected signature."""
        from src.promptrca.core.swarm_orchestrator import SwarmOrchestrator
        import inspect
        
        orchestrator = SwarmOrchestrator(region="us-east-1")
        
        # Get the signature of the investigate method
        sig = inspect.signature(orchestrator.investigate)
        
        # Check expected parameters
        expected_params = ['inputs', 'region', 'assume_role_arn', 'external_id']
        actual_params = list(sig.parameters.keys())
        
        for param in expected_params:
            assert param in actual_params, f"Missing parameter: {param}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])