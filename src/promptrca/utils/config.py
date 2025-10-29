#!/usr/bin/env python3
"""
PromptRCA Core - Configuration utilities
Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: christiangenn99+promptrca@gmail.com

Centralized configuration utilities for PromptRCA.
Handles environment variable parsing and provides consistent defaults.
"""

import os
from typing import Dict, Any, Optional
from strands.models import BedrockModel

# Default region - can be overridden by environment variables
DEFAULT_REGION = "eu-west-1"


def get_region() -> str:
    """
    Get AWS region from environment variables with fallback chain.
    
    Checks in order:
    1. AWS_REGION
    2. AWS_DEFAULT_REGION  
    3. DEFAULT_REGION constant
    
    Returns:
        str: AWS region name
    """
    return (
        os.getenv("AWS_REGION") or 
        os.getenv("AWS_DEFAULT_REGION") or 
        DEFAULT_REGION
    )


def get_bedrock_model_config() -> Dict[str, Any]:
    """
    Get Bedrock model configuration from environment variables.
    
    Supported environment variables:
    - BEDROCK_MODEL_ID: Bedrock model identifier (default: "openai.gpt-oss-120b-1:0")
    - PROMPTRCA_TEMPERATURE: Model temperature 0.0-1.0 (default: 0.7)
    - PROMPTRCA_MAX_TOKENS: Maximum tokens (optional)
    
    Returns:
        Dict[str, Any]: Configuration dictionary for BedrockModel
    """
    config = {
        "model_id": os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"),
        "temperature": float(os.getenv("PROMPTRCA_TEMPERATURE", "0.7")),
        "streaming": False
    }
    
    # Add max_tokens if specified
    max_tokens = os.getenv("PROMPTRCA_MAX_TOKENS")
    if max_tokens:
        config["max_tokens"] = int(max_tokens)
    
    return config


def create_bedrock_model(temperature_override: Optional[float] = None) -> BedrockModel:
    """
    Create a BedrockModel instance with environment-based configuration.
    
    Args:
        temperature_override: Optional temperature to override the default
    
    Returns:
        BedrockModel: Configured Bedrock model instance
    """
    config = get_bedrock_model_config()
    if temperature_override is not None:
        config["temperature"] = temperature_override
    return BedrockModel(**config)


def get_max_tokens(default: int = 1500) -> int:
    """
    Get max tokens for reasoning phases from env with sensible default.
    """
    try:
        return int(os.getenv("PROMPTRCA_MAX_TOKENS", str(default)))
    except Exception:
        return default


def get_temperature(agent: str | None = None, default: float = 0.2) -> float:
    """
    Get temperature with precedence: agent-specific -> analysis -> global -> default.
    """
    if agent:
        env_key = f"PROMPTRCA_{agent.upper()}_TEMPERATURE"
        if os.getenv(env_key) is not None:
            return float(os.getenv(env_key))
    if os.getenv("PROMPTRCA_ANALYSIS_TEMPERATURE") is not None:
        return float(os.getenv("PROMPTRCA_ANALYSIS_TEMPERATURE"))
    if os.getenv("PROMPTRCA_TEMPERATURE") is not None:
        return float(os.getenv("PROMPTRCA_TEMPERATURE"))
    return default


def create_parser_model() -> BedrockModel:
    """
    Create a dedicated low-temp, low-token model for the fallback parser agent.
    Enforces temperature≈0.1 and max_tokens≈256 irrespective of global defaults.
    """
    # Base config from global, but override specifics for parser usage
    cfg = get_bedrock_model_config()
    cfg["temperature"] = float(os.getenv("PROMPTRCA_PARSER_TEMPERATURE", "0.1"))
    # Ensure a tight cap for tokens used by the parser
    cfg["max_tokens"] = int(os.getenv("PROMPTRCA_PARSER_MAX_TOKENS", "256"))
    return BedrockModel(**cfg)


def create_synthesis_model() -> BedrockModel:
    """
    Create a model for synthesis with lower temperature.
    
    Returns:
        BedrockModel: Configured Bedrock model with lower temperature for synthesis
    """
    synthesis_temp = float(os.getenv("PROMPTRCA_SYNTHESIS_TEMPERATURE", "0.2"))
    return create_bedrock_model(temperature_override=synthesis_temp)


def create_orchestrator_model() -> BedrockModel:
    """
    Create a model for the lead orchestrator agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for orchestrator
    """
    model_id = os.getenv("PROMPTRCA_ORCHESTRATOR_MODEL_ID") or os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0")
    temperature = float(os.getenv("PROMPTRCA_ORCHESTRATOR_TEMPERATURE") or os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_lambda_agent_model() -> BedrockModel:
    """
    Create a model for the Lambda specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for Lambda agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_LAMBDA_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_LAMBDA_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_apigateway_agent_model() -> BedrockModel:
    """
    Create a model for the API Gateway specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for API Gateway agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_APIGATEWAY_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_APIGATEWAY_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_stepfunctions_agent_model() -> BedrockModel:
    """
    Create a model for the Step Functions specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for Step Functions agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_STEPFUNCTIONS_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_STEPFUNCTIONS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_iam_agent_model() -> BedrockModel:
    """
    Create a model for the IAM specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for IAM agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_IAM_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_IAM_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_dynamodb_agent_model() -> BedrockModel:
    """
    Create a model for the DynamoDB specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for DynamoDB agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_DYNAMODB_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_DYNAMODB_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_s3_agent_model() -> BedrockModel:
    """
    Create a model for the S3 specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for S3 agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_S3_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_S3_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_sqs_agent_model() -> BedrockModel:
    """
    Create a model for the SQS specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for SQS agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_SQS_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_SQS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_sns_agent_model() -> BedrockModel:
    """
    Create a model for the SNS specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for SNS agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_SNS_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_SNS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_eventbridge_agent_model() -> BedrockModel:
    """
    Create a model for the EventBridge specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for EventBridge agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_EVENTBRIDGE_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_EVENTBRIDGE_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_vpc_agent_model() -> BedrockModel:
    """
    Create a model for the VPC specialist agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for VPC agent
    """
    # Hierarchical configuration: Agent-specific -> Specialist category -> Global default
    model_id = (os.getenv("PROMPTRCA_VPC_MODEL_ID") or 
                os.getenv("PROMPTRCA_SPECIALIST_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_VPC_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_SPECIALIST_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


def create_hypothesis_agent_model() -> BedrockModel:
    """
    Create a model for the hypothesis generation agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for hypothesis agent
    """
    # Hierarchical configuration: Agent-specific -> Analysis category -> Global default
    model_id = (os.getenv("PROMPTRCA_HYPOTHESIS_MODEL_ID") or 
                os.getenv("PROMPTRCA_ANALYSIS_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_HYPOTHESIS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_ANALYSIS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    # Apply max_tokens cap if provided
    model = BedrockModel(model_id=model_id, temperature=temperature, streaming=False)
    max_tokens = get_max_tokens()
    try:
        setattr(model, "max_tokens", max_tokens)
    except Exception:
        pass
    return model


def create_root_cause_agent_model() -> BedrockModel:
    """
    Create a model for the root cause analysis agent.
    
    Returns:
        BedrockModel: Configured Bedrock model for root cause agent
    """
    # Hierarchical configuration: Agent-specific -> Analysis category -> Global default
    model_id = (os.getenv("PROMPTRCA_ROOT_CAUSE_MODEL_ID") or 
                os.getenv("PROMPTRCA_ANALYSIS_MODEL_ID") or 
                os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"))
    
    temperature = float(os.getenv("PROMPTRCA_ROOT_CAUSE_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_ANALYSIS_TEMPERATURE") or 
                       os.getenv("PROMPTRCA_TEMPERATURE", "0.7"))
    
    model = BedrockModel(model_id=model_id, temperature=temperature, streaming=False)
    max_tokens = get_max_tokens()
    try:
        setattr(model, "max_tokens", max_tokens)
    except Exception:
        pass
    return model








def get_mcp_config() -> Dict[str, Any]:
    """
    Get AWS Knowledge MCP server configuration from environment variables.
    
    Environment Variables:
    - ENABLE_AWS_KNOWLEDGE_MCP: Enable/disable MCP integration (default: true)
    - AWS_KNOWLEDGE_MCP_URL: MCP server URL (default: https://knowledge-mcp.global.api.aws)
    - AWS_KNOWLEDGE_MCP_TIMEOUT: Request timeout in seconds (default: 5)
    - AWS_KNOWLEDGE_MCP_RETRIES: Max retry attempts (default: 2)
    
    Returns:
        Dict[str, Any]: MCP configuration dictionary
    """
    return {
        "enabled": os.getenv("ENABLE_AWS_KNOWLEDGE_MCP", "false").lower() == "true",
        "server_url": os.getenv("AWS_KNOWLEDGE_MCP_URL", "https://knowledge-mcp.global.api.aws"),
        "timeout": int(os.getenv("AWS_KNOWLEDGE_MCP_TIMEOUT", "5")),
        "max_retries": int(os.getenv("AWS_KNOWLEDGE_MCP_RETRIES", "2"))
    }


def get_environment_info() -> Dict[str, str]:
    """
    Get information about current environment configuration.
    
    Returns:
        Dict[str, str]: Environment configuration summary
    """
    return {
        "region": get_region(),
        "model_id": os.getenv("BEDROCK_MODEL_ID", "openai.gpt-oss-120b-1:0"),
        "temperature": os.getenv("PROMPTRCA_TEMPERATURE", "0.7"),
        "max_tokens": os.getenv("PROMPTRCA_MAX_TOKENS", "not set"),
        "aws_region": os.getenv("AWS_REGION", "not set"),
        "aws_default_region": os.getenv("AWS_DEFAULT_REGION", "not set"),
        "mcp_enabled": str(get_mcp_config()["enabled"]),
    }


# Global flag to prevent duplicate telemetry initialization
_telemetry_initialized = False

def reset_telemetry_initialization() -> None:
    """
    Reset the telemetry initialization flag.
    
    This is primarily for testing purposes to allow re-initialization
    of telemetry in test environments.
    """
    global _telemetry_initialized
    _telemetry_initialized = False

def setup_strands_telemetry() -> None:
    """
    Set up Strands OpenTelemetry tracing for observability.
    
    Configures OTLP exporter to send traces to various backends:
    - Langfuse (with Basic Auth)
    - AWS X-Ray (via OTLP)
    - Any other OTLP-compatible backend
    
    The backend is determined by the OTEL_EXPORTER_OTLP_ENDPOINT URL and available credentials.
    
    This function is idempotent - calling it multiple times will not create duplicate
    telemetry configurations.
    """
    global _telemetry_initialized
    
    # Prevent duplicate initialization
    if _telemetry_initialized:
        print("🔄 Strands telemetry already initialized, skipping duplicate setup")
        return
    
    try:
        from strands.telemetry import StrandsTelemetry
        
        # Get configuration from environment
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        service_name = os.getenv("OTEL_SERVICE_NAME", "promptrca")
        
        # Backend-specific credentials
        langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        
        # Generic OTLP headers (for any backend that needs custom headers)
        otlp_headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS")

        if not otlp_endpoint:
            print("⚠️  OTEL_EXPORTER_OTLP_ENDPOINT not set, skipping telemetry setup")
            return

        # Initialize Strands telemetry
        strands_telemetry = StrandsTelemetry()

        # Determine backend type and configure accordingly
        backend_type = _detect_backend_type(otlp_endpoint, langfuse_public_key, langfuse_secret_key)
        
        if backend_type == "langfuse":
            # Langfuse requires Basic Auth
            import base64
            credentials = f"{langfuse_public_key}:{langfuse_secret_key}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {"Authorization": f"Basic {encoded_credentials}"}
            os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {encoded_credentials}"
            
            strands_telemetry.setup_otlp_exporter(
                endpoint=otlp_endpoint,
                headers=headers
            )
            print(f"✅ Strands telemetry configured for Langfuse: {service_name} -> {otlp_endpoint}")
            
        elif backend_type == "xray":
            # X-Ray via OTLP (no special auth required, uses AWS credentials)
            strands_telemetry.setup_otlp_exporter(endpoint=otlp_endpoint)
            print(f"✅ Strands telemetry configured for AWS X-Ray: {service_name} -> {otlp_endpoint}")
            
        elif backend_type == "generic":
            # Generic OTLP backend - use any provided headers
            headers = {}
            if otlp_headers:
                # Parse headers from environment variable (format: "key1=value1,key2=value2")
                for header_pair in otlp_headers.split(','):
                    if '=' in header_pair:
                        key, value = header_pair.split('=', 1)
                        headers[key.strip()] = value.strip()
            
            strands_telemetry.setup_otlp_exporter(
                endpoint=otlp_endpoint,
                headers=headers if headers else None
            )
            print(f"✅ Strands telemetry configured for OTLP backend: {service_name} -> {otlp_endpoint}")
        
        # Set up console exporter for development (optional)
        if os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
            strands_telemetry.setup_console_exporter()
        
        # Mark telemetry as successfully initialized
        _telemetry_initialized = True
        
    except ImportError as e:
        print(f"⚠️  Strands telemetry not available: {e}")
    except Exception as e:
        print(f"⚠️  Failed to setup telemetry: {e}")


def _detect_backend_type(otlp_endpoint: str, langfuse_public_key: str, langfuse_secret_key: str) -> str:
    """
    Detect the backend type based on endpoint URL and available credentials.
    
    Args:
        otlp_endpoint: The OTLP endpoint URL
        langfuse_public_key: Langfuse public key (if available)
        langfuse_secret_key: Langfuse secret key (if available)
        
    Returns:
        str: Backend type ('langfuse', 'xray', or 'generic')
    """
    if not otlp_endpoint:
        return "generic"
    
    endpoint_lower = otlp_endpoint.lower()
    
    # Check for Langfuse-specific endpoints and credentials
    if (langfuse_public_key and langfuse_secret_key and 
        any(domain in endpoint_lower for domain in ['langfuse', 'cloud.langfuse.com'])):
        return "langfuse"
    
    # Check for X-Ray specific endpoints
    if any(domain in endpoint_lower for domain in ['xray', 'amazonaws.com/xray']):
        return "xray"
    
    # Default to generic OTLP backend
    return "generic"


def get_telemetry_config() -> Dict[str, Any]:
    """
    Get OpenTelemetry configuration from environment variables.
    
    Environment Variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL (default: None)
    - OTEL_SERVICE_NAME: Service name for traces (default: promptrca)
    - OTEL_CONSOLE_EXPORT: Enable console export for development (default: false)
    - OTEL_EXPORTER_OTLP_HEADERS: Custom headers for OTLP exporter (optional)
    - LANGFUSE_PUBLIC_KEY: Langfuse public key (optional)
    - LANGFUSE_SECRET_KEY: Langfuse secret key (optional)
    
    Returns:
        Dict[str, Any]: Telemetry configuration dictionary
    """
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    
    # Detect backend type
    backend_type = _detect_backend_type(otlp_endpoint, langfuse_public_key, langfuse_secret_key)
    
    return {
        "otlp_endpoint": otlp_endpoint,
        "service_name": os.getenv("OTEL_SERVICE_NAME", "promptrca"),
        "console_export": os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true",
        "enabled": bool(otlp_endpoint),
        "backend_type": backend_type,
        "langfuse_configured": bool(langfuse_public_key and langfuse_secret_key),
        "custom_headers": os.getenv("OTEL_EXPORTER_OTLP_HEADERS")
    }
