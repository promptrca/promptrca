#!/usr/bin/env python3
"""
Sherlock Core - Configuration utilities
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

Contact: christiangenn99+sherlock@gmail.com

Centralized configuration utilities for Sherlock.
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
    - SHERLOCK_MODEL_ID: Bedrock model identifier (default: "openai.gpt-oss-120b-1:0")
    - SHERLOCK_TEMPERATURE: Model temperature 0.0-1.0 (default: 0.7)
    - SHERLOCK_MAX_TOKENS: Maximum tokens (optional)
    
    Returns:
        Dict[str, Any]: Configuration dictionary for BedrockModel
    """
    config = {
        "model_id": os.getenv("SHERLOCK_MODEL_ID", "openai.gpt-oss-120b-1:0"),
        "temperature": float(os.getenv("SHERLOCK_TEMPERATURE", "0.7")),
        "streaming": False
    }
    
    # Add max_tokens if specified
    max_tokens = os.getenv("SHERLOCK_MAX_TOKENS")
    if max_tokens:
        config["max_tokens"] = int(max_tokens)
    
    return config


def create_bedrock_model() -> BedrockModel:
    """
    Create a BedrockModel instance with environment-based configuration.
    
    Returns:
        BedrockModel: Configured Bedrock model instance
    """
    config = get_bedrock_model_config()
    return BedrockModel(**config)


def get_environment_info() -> Dict[str, str]:
    """
    Get information about current environment configuration.
    
    Returns:
        Dict[str, str]: Environment configuration summary
    """
    return {
        "region": get_region(),
        "model_id": os.getenv("SHERLOCK_MODEL_ID", "openai.gpt-oss-120b-1:0"),
        "temperature": os.getenv("SHERLOCK_TEMPERATURE", "0.7"),
        "max_tokens": os.getenv("SHERLOCK_MAX_TOKENS", "not set"),
        "aws_region": os.getenv("AWS_REGION", "not set"),
        "aws_default_region": os.getenv("AWS_DEFAULT_REGION", "not set")
    }
