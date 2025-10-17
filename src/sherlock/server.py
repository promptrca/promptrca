#!/usr/bin/env python3
"""
Sherlock Core - HTTP Server
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

Sherlock HTTP Server - AI Root-Cause Investigator
HTTP server implementation using Amazon Bedrock AgentCore
"""

import argparse
import os
import asyncio
import base64
from typing import Dict, Any

# IMPORTANT: Set OTEL headers and initialize telemetry BEFORE any imports
if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
    credentials = f"{os.getenv('LANGFUSE_PUBLIC_KEY')}:{os.getenv('LANGFUSE_SECRET_KEY')}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {encoded_credentials}"

    # Initialize Strands telemetry BEFORE importing any Strands code
    try:
        from strands.telemetry import StrandsTelemetry
        # Try traces-specific endpoint first, fall back to general endpoint
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT") or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            strands_telemetry = StrandsTelemetry()
            headers = {"Authorization": f"Basic {encoded_credentials}"}
            strands_telemetry.setup_otlp_exporter(endpoint=otlp_endpoint, headers=headers)

            # Set up console exporter for development (optional)
            if os.getenv("OTEL_CONSOLE_EXPORT", "false").lower() == "true":
                strands_telemetry.setup_console_exporter()

            print(f"✅ Strands telemetry initialized early: {os.getenv('OTEL_SERVICE_NAME', 'sherlock')} -> {otlp_endpoint}")
    except Exception as e:
        print(f"⚠️  Failed to initialize telemetry early: {e}")

from bedrock_agentcore import BedrockAgentCoreApp
from starlette.responses import JSONResponse

from .handlers import handle_investigation, get_region
from .utils.config import get_environment_info, DEFAULT_REGION

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


# Health check endpoint
async def health(request):
    """Health check endpoint - simple status check."""
    return JSONResponse({
        "status": "healthy",
        "service": "sherlock-agentcore",
        "version": "1.0.0"
    })

app.add_route("/health", health, methods=["GET"])


# Status endpoint
async def status(request):
    """Status endpoint with detailed service information."""
    try:
        # Get environment info
        env_info = get_environment_info()
        
        
        return JSONResponse({
            "status": "healthy",
            "service": "sherlock-agentcore",
            "version": "1.0.0",
            "environment": env_info,
            "endpoints": {
                "investigations": "/invocations",
                "health": "/health",
                "status": "/status",
                "ping": "/ping"
            }
        })
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e)
        }, status_code=500)

app.add_route("/status", status, methods=["GET"])


def main():
    """Main entry point for the HTTP server."""
    # Telemetry is now initialized at module import time (see top of file)
    # No need to call setup_strands_telemetry() here

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Sherlock AI Root-Cause Investigator HTTP Server")
    parser.add_argument("--region", "-r", 
                       default=DEFAULT_REGION,
                       help=f"AWS region for investigations (default: {DEFAULT_REGION})")
    parser.add_argument("--port", "-p",
                       type=int,
                       default=8080,
                       help="Port to run the server on (default: 8080)")
    parser.add_argument("--reload",
                       action="store_true",
                       help="Enable hot reloading for development")
    
    args = parser.parse_args()
    
    # Update the region if provided via command line
    if args.region != DEFAULT_REGION:
        os.environ["AWS_REGION"] = args.region
    
    print("🔍 Sherlock - AI Root-Cause Investigator (HTTP Server)")
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
    print("")
    print("🏥 Health Check:")
    print("curl http://localhost:8080/health")
    print("")
    print("📊 Status Check:")
    print("curl http://localhost:8080/status")
    print("=====================================================")
    
    if args.reload:
        # Use uvicorn with hot reloading for development
        import uvicorn
        print("🔄 Hot reloading enabled - server will restart on code changes")
        uvicorn.run("sherlock.server:app", host="0.0.0.0", port=args.port, reload=True)
    else:
        # Use AgentCore's built-in server for production
        app.run(port=args.port)


if __name__ == "__main__":
    main()
