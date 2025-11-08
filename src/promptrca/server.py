#!/usr/bin/env python3
"""
PromptRCA Core - HTTP Server
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

Contact: info@promptrca.com

PromptRCA HTTP Server - AI Root-Cause Investigator
HTTP server implementation using Starlette
"""

import argparse
import os
import json
from typing import Dict, Any

# IMPORTANT: Initialize telemetry BEFORE any imports
from .utils.config import setup_strands_telemetry
setup_strands_telemetry()

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from .handlers import handle_investigation, get_region
from .utils.config import get_environment_info, DEFAULT_REGION


async def invoke(request):
    """
    PromptRCA investigation entrypoint for HTTP server.
    Uses shared handler logic from handlers.py
    
    Expects structured format:
    {
        "investigation": {
            "input": "Free text description",
            "xray_trace_id": "1-...",  # optional
            "region": "eu-west-1"  # optional
        },
        "service_config": {
            "role_arn": "arn:aws:iam::...",  # optional
            "external_id": "...",  # optional
            "region": "eu-west-1"  # optional
        }
    }
    """
    try:
        # Parse JSON payload from request body
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({
            "success": False,
            "error": "Invalid JSON in request body"
        }, status_code=400)
    
    # Validate structured format
    if "investigation" not in payload or "service_config" not in payload:
        return JSONResponse({
            "success": False,
            "error": "Payload must have 'investigation' and 'service_config' keys in structured format",
            "received_keys": list(payload.keys())
        }, status_code=400)
    
    result = await handle_investigation(payload)

    # Add server-specific metadata
    if "investigation" in result:
        result["investigation"]["execution_environment"] = "http_server"

    return JSONResponse(result)


# Health check endpoint
async def health(request):
    """Health check endpoint - simple status check."""
    return JSONResponse({
        "status": "healthy",
        "service": "promptrca-server",
        "version": "1.0.0"
    })


# Status endpoint
async def status(request):
    """Status endpoint with detailed service information."""
    try:
        # Get environment info
        env_info = get_environment_info()
        
        
        return JSONResponse({
            "status": "healthy",
            "service": "promptrca-server",
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


# Ping endpoint for health checks
async def ping(request):
    """Ping endpoint for health checks."""
    return JSONResponse({"status": "ok"})


# Create Starlette application with routes
app = Starlette(routes=[
    Route("/invocations", invoke, methods=["POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/status", status, methods=["GET"]),
    Route("/ping", ping, methods=["GET"]),
])


def main():
    """Main entry point for the HTTP server."""
    # Telemetry is now initialized at module import time (see top of file)
    # No need to call setup_strands_telemetry() here

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PromptRCA AI Root-Cause Investigator HTTP Server")
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
    parser.add_argument("--host",
                       default="0.0.0.0",
                       help="Host to bind to (default: 0.0.0.0)")
    
    args = parser.parse_args()
    
    # Update the region if provided via command line
    if args.region != DEFAULT_REGION:
        os.environ["AWS_REGION"] = args.region
    
    print("🔍 PromptRCA - AI Root-Cause Investigator (HTTP Server)")
    print("=====================================================")
    print(f"🌍 AWS Region: {get_region()}")
    print(f"🌐 Starting HTTP server on http://{args.host}:{args.port}")
    print("")
    print("📝 Investigation Request (Structured Format):")
    print("curl -X POST http://localhost:8080/invocations \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"investigation\": {\"input\": \"My Lambda function payment-processor is failing with division by zero errors. X-Ray trace: 1-68e904af-484b173354fff9607ee41871\"}, \"service_config\": {}}'")
    print("")
    print("🔧 Structured Input Example:")
    print("curl -X POST http://localhost:8080/invocations \\")
    print("  -H 'Content-Type: application/json' \\")
    print(f"  -d '{{\"investigation\": {{\"input\": \"test\", \"region\": \"{get_region()}\"}}, \"service_config\": {{\"region\": \"{get_region()}\"}}}}'")
    print("")
    print("🏥 Health Check:")
    print("curl http://localhost:8080/health")
    print("")
    print("📊 Status Check:")
    print("curl http://localhost:8080/status")
    print("")
    print("🏓 Ping:")
    print("curl http://localhost:8080/ping")
    print("=====================================================")
    
    # Always use uvicorn (both for development and production)
    import uvicorn
    if args.reload:
        print("🔄 Hot reloading enabled - server will restart on code changes")
    
    uvicorn.run(
        "promptrca.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
