#!/usr/bin/env python3
"""
Test for telemetry deduplication to prevent multiple traces.
"""

import pytest
from unittest.mock import patch, Mock
import os

from src.promptrca.utils.config import setup_strands_telemetry, reset_telemetry_initialization


class TestTelemetryDeduplication:
    """Test that telemetry initialization is deduplicated."""
    
    def setup_method(self):
        """Reset telemetry state before each test."""
        reset_telemetry_initialization()
    
    def teardown_method(self):
        """Clean up after each test."""
        reset_telemetry_initialization()
    
    @patch.dict('os.environ', {}, clear=True)
    def test_telemetry_setup_skips_when_no_endpoint(self):
        """Test that telemetry setup is skipped when no endpoint is configured."""
        # Should not raise an error when no endpoint is set
        setup_strands_telemetry()
        
        # Should skip on second call too
        setup_strands_telemetry()
    
    @patch.dict('os.environ', {
        'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317',
        'OTEL_SERVICE_NAME': 'test-service'
    })
    @patch('strands.telemetry.StrandsTelemetry')
    def test_telemetry_setup_prevents_duplicate_initialization(self, mock_strands_telemetry):
        """Test that telemetry setup prevents duplicate initialization."""
        mock_telemetry_instance = Mock()
        mock_strands_telemetry.return_value = mock_telemetry_instance
        
        # First call should initialize telemetry
        setup_strands_telemetry()
        
        # Check that StrandsTelemetry was instantiated once
        assert mock_strands_telemetry.call_count == 1
        assert mock_telemetry_instance.setup_otlp_exporter.call_count == 1
        
        # Second call should be skipped
        setup_strands_telemetry()
        
        # Should still be called only once
        assert mock_strands_telemetry.call_count == 1
        assert mock_telemetry_instance.setup_otlp_exporter.call_count == 1
    
    @patch.dict('os.environ', {
        'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317',
        'OTEL_SERVICE_NAME': 'test-service'
    })
    @patch('strands.telemetry.StrandsTelemetry')
    def test_multiple_calls_in_different_modules(self, mock_strands_telemetry):
        """Test that multiple calls from different modules are deduplicated."""
        mock_telemetry_instance = Mock()
        mock_strands_telemetry.return_value = mock_telemetry_instance
        
        # Simulate calls from different modules (like lambda_handler.py, server.py, __main__.py)
        setup_strands_telemetry()  # From lambda_handler.py
        setup_strands_telemetry()  # From server.py  
        setup_strands_telemetry()  # From __main__.py
        
        # Should only initialize once
        assert mock_strands_telemetry.call_count == 1
        assert mock_telemetry_instance.setup_otlp_exporter.call_count == 1
    
    @patch.dict('os.environ', {
        'OTEL_EXPORTER_OTLP_ENDPOINT': 'https://cloud.langfuse.com',
        'LANGFUSE_PUBLIC_KEY': 'pk_test_123',
        'LANGFUSE_SECRET_KEY': 'sk_test_456',
        'OTEL_SERVICE_NAME': 'test-service'
    })
    @patch('strands.telemetry.StrandsTelemetry')
    def test_langfuse_backend_deduplication(self, mock_strands_telemetry):
        """Test that Langfuse backend setup is also deduplicated."""
        mock_telemetry_instance = Mock()
        mock_strands_telemetry.return_value = mock_telemetry_instance
        
        # Multiple calls should only initialize once
        setup_strands_telemetry()
        setup_strands_telemetry()
        setup_strands_telemetry()
        
        # Should only initialize once
        assert mock_strands_telemetry.call_count == 1
        assert mock_telemetry_instance.setup_otlp_exporter.call_count == 1
        
        # Check that Langfuse headers were set correctly (only once)
        call_args = mock_telemetry_instance.setup_otlp_exporter.call_args
        assert 'headers' in call_args.kwargs
        assert 'Authorization' in call_args.kwargs['headers']
    
    def test_reset_telemetry_initialization_works(self):
        """Test that reset function allows re-initialization."""
        with patch.dict('os.environ', {
            'OTEL_EXPORTER_OTLP_ENDPOINT': 'http://localhost:4317',
            'OTEL_SERVICE_NAME': 'test-service'
        }):
            with patch('strands.telemetry.StrandsTelemetry') as mock_strands_telemetry:
                mock_telemetry_instance = Mock()
                mock_strands_telemetry.return_value = mock_telemetry_instance
                
                # First initialization
                setup_strands_telemetry()
                assert mock_strands_telemetry.call_count == 1
                
                # Second call should be skipped
                setup_strands_telemetry()
                assert mock_strands_telemetry.call_count == 1
                
                # Reset and try again
                reset_telemetry_initialization()
                setup_strands_telemetry()
                assert mock_strands_telemetry.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])