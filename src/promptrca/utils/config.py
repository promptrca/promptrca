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
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)


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
    
    return BedrockModel(model_id=model_id, temperature=temperature, streaming=False)








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


def setup_strands_telemetry() -> None:
    """
    Set up Strands OpenTelemetry tracing for observability.
    
    Configures OTLP exporter to send traces to Langfuse and enables
    Strands tracing for all agent interactions.
    """
    try:
        from strands.telemetry import StrandsTelemetry
        
        # Get configuration from environment
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        service_name = os.getenv("OTEL_SERVICE_NAME", "promptrca")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")

        if not otlp_endpoint:
            print("⚠️  OTEL_EXPORTER_OTLP_ENDPOINT not set, skipping telemetry setup")
            return

        if not public_key or not secret_key:
            print("⚠️  Langfuse credentials not set, skipping telemetry setup")
            return

        # Generate Basic Auth header from Langfuse API keys
        import base64
        credentials = f"{public_key}:{secret_key}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Set OTEL environment variables for the exporter
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {encoded_credentials}"

        # Initialize Strands telemetry
        strands_telemetry = StrandsTelemetry()

        # Set up OTLP exporter with endpoint and auth headers
        headers = {"Authorization": f"Basic {encoded_credentials}"}
        strands_telemetry.setup_otlp_exporter(
            endpoint=otlp_endpoint,
            headers=headers
        )
        
        # Set up console exporter for development (optional)
        if os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
            strands_telemetry.setup_console_exporter()
        
        print(f"✅ Strands telemetry configured: {service_name} -> {otlp_endpoint}")
        print(f"🔑 Generated Basic Auth header for Langfuse")
        
    except ImportError as e:
        print(f"⚠️  Strands telemetry not available: {e}")
    except Exception as e:
        print(f"⚠️  Failed to setup telemetry: {e}")


def get_telemetry_config() -> Dict[str, Any]:
    """
    Get OpenTelemetry configuration from environment variables.
    
    Environment Variables:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL (default: None)
    - OTEL_SERVICE_NAME: Service name for traces (default: promptrca)
    - OTEL_CONSOLE_EXPORT: Enable console export for development (default: false)
    
    Returns:
        Dict[str, Any]: Telemetry configuration dictionary
    """
    return {
        "otlp_endpoint": os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"),
        "service_name": os.getenv("OTEL_SERVICE_NAME", "promptrca"),
        "console_export": os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true",
        "enabled": bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
    }
