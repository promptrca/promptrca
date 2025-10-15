#!/usr/bin/env python3
"""
Sherlock Core - AI-powered root cause analysis for AWS infrastructure
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

Sherlock AgentCore Server - AI Root-Cause Investigator
Local HTTP server implementation using Amazon Bedrock AgentCore
"""

import argparse
import os
from typing import Dict, Any
from bedrock_agentcore import BedrockAgentCoreApp

from .handlers import handle_investigation, get_region, DEFAULT_REGION

# AgentCore setup
app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sherlock investigation entrypoint for AgentCore server.
    Uses shared handler logic from handlers.py
    """
    result = handle_investigation(payload)

    # Add server-specific metadata
    if "investigation" in result:
        result["investigation"]["execution_environment"] = "agentcore_server"

    return result


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Sherlock AI Root-Cause Investigator")
    parser.add_argument("--region", "-r", 
                       default=DEFAULT_REGION,
                       help=f"AWS region for investigations (default: {DEFAULT_REGION})")
    parser.add_argument("--port", "-p",
                       type=int,
                       default=8080,
                       help="Port to run the server on (default: 8080)")
    
    args = parser.parse_args()
    
    # Update the region if provided via command line
    if args.region != DEFAULT_REGION:
        os.environ["AWS_REGION"] = args.region
    
    print("🔍 Sherlock - AI Root-Cause Investigator (Multi-Input)")
    print("=====================================================")
    print(f"🌍 AWS Region: {get_region()}")
    print(f"🌐 Starting AgentCore server on http://localhost:{args.port}")
    print("")
    print("📝 Free Text Input (Recommended):")
    print("curl -X POST http://localhost:8080/invocations \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"free_text_input\": \"My Lambda function payment-processor is failing with division by zero errors. X-Ray trace: 1-68e904af-484b173354fff9607ee41871\"}'")
    print("")
    print("🔧 Legacy Structured Input:")
    print("curl -X POST http://localhost:8080/invocations \\")
    print("  -H 'Content-Type: application/json' \\")
    print(f"  -d '{{\"function_name\": \"test-function\", \"region\": \"{get_region()}\"}}'")
    print("=====================================================")
    app.run(port=args.port)
