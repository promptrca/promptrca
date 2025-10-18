# Langfuse Integration for Sherlock

This document explains the Langfuse observability integration for Sherlock investigations.

## What's Been Implemented

### 1. Langfuse Dashboard (Self-Hosted)
- **PostgreSQL database** for storing traces
- **ClickHouse database** for analytics and metrics (required for v3+)
- **Redis** for caching
- **Langfuse server** with web UI
- Dashboard available at: `http://localhost:3000`

### 2. OpenTelemetry Tracing
- Strands SDK integration configured
- OTLP exporter sends traces to Langfuse
- Automatic capture of:
  - Agent lifecycle and execution flow
  - LLM calls with prompts and responses
  - Tool executions and results
  - Token usage per agent invocation
  - Performance metrics and timing

### 3. Trace Attributes
Enhanced traces include metadata for filtering and analysis:
- **Service identification**: service.name, agent.type
- **AWS context**: aws.service, agent.region
- **Investigation context**: Captured through agent prompts

### 4. Cost Tracking Maintained
- Existing TokenTracker still active for cost calculations
- Per-investigation cost breakdowns in API responses
- Langfuse provides additional observability

## Quick Start

### 1. Start the Stack

```bash
# Copy environment variables
cp env.example .env

# Edit .env and set secure keys for Langfuse (optional, defaults provided)
# LANGFUSE_NEXTAUTH_SECRET=<your-secret>
# LANGFUSE_ENCRYPTION_KEY=<your-encryption-key>

# Start all services
docker-compose up -d

# Check services are running
docker-compose ps
```

### 2. Access Langfuse Dashboard

1. Open browser to `http://localhost:3000`
2. Create an account (first-time setup)
3. Navigate to "Traces" section

### 3. Run an Investigation

```bash
# Example investigation
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{
    "free_text_input": "My Lambda function payment-processor is failing with errors"
  }'
```

### 4. View Traces in Langfuse

1. Go to Langfuse dashboard (`http://localhost:3000`)
2. Click on "Traces" in the sidebar
3. You should see traces for:
   - Lead orchestrator execution
   - Specialized agent calls (Lambda, IAM, etc.)
   - Tool executions (get_lambda_config, get_cloudwatch_logs, etc.)
   - LLM invocations with token counts

## Trace Structure

Each investigation creates a hierarchical trace:

```
Strands Agent (lead_orchestrator)
├── Cycle 1
│   ├── Model invoke (LLM call)
│   ├── Tool: get_xray_trace
│   └── Tool: investigate_lambda_function
│       └── Strands Agent (lambda_specialist)
│           ├── Cycle 1
│           │   ├── Model invoke
│           │   ├── Tool: get_lambda_config
│           │   └── Tool: get_cloudwatch_logs
│           └── Choice (response)
└── Choice (final response)
```

## Filtering Traces

Use trace attributes to filter investigations:

- **By agent type**: `agent.type = "lead_orchestrator"`
- **By AWS service**: `aws.service = "lambda"`
- **By region**: `agent.region = "eu-west-1"`
- **By service**: `service.name = "sherlock-orchestrator"`

## Environment Variables

### Required for Tracing
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://langfuse:3000/ingest
OTEL_SERVICE_NAME=sherlock-server  # or sherlock-lambda
```

### Optional for Development
```bash
OTEL_CONSOLE_EXPORT=true  # Also print traces to console
```

### Langfuse Configuration
```bash
LANGFUSE_DB_NAME=langfuse
LANGFUSE_DB_USER=langfuse
LANGFUSE_DB_PASSWORD=langfuse
LANGFUSE_CLICKHOUSE_DB=langfuse
LANGFUSE_CLICKHOUSE_USER=langfuse
LANGFUSE_CLICKHOUSE_PASSWORD=langfuse
LANGFUSE_NEXTAUTH_SECRET=your-secret-key-change-in-production
LANGFUSE_ENCRYPTION_KEY=your-encryption-key-change-in-production
```

## Troubleshooting

### No Traces Appearing

1. **Check Langfuse is running**:
   ```bash
   docker-compose ps langfuse
   curl http://localhost:3000/api/public/health
   ```

2. **Check OTLP endpoint is set**:
   ```bash
   docker-compose logs sherlock-server | grep "telemetry"
   # Should see: "✅ Strands telemetry configured"
   ```

3. **Check for errors in Sherlock logs**:
   ```bash
   docker-compose logs sherlock-server
   ```

4. **Verify network connectivity**:
   ```bash
   docker-compose exec sherlock-server ping -c 3 langfuse
   ```

### Langfuse Won't Start

1. **Check database is healthy**:
   ```bash
   docker-compose logs langfuse-db
   ```

2. **Reset the stack**:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

### Cost Tracking Still Works

The existing TokenTracker is still active and provides:
- Per-investigation cost summaries in API responses
- Token usage by agent and model
- Cost calculations with actual pricing

Langfuse provides additional observability but doesn't replace cost tracking.

## Production Considerations

Before deploying to production:

1. **Set secure secrets** in `.env`:
   - `LANGFUSE_NEXTAUTH_SECRET`
   - `LANGFUSE_ENCRYPTION_KEY`
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_PRIVATE_KEY`

2. **Use persistent volumes** for PostgreSQL data

3. **Configure backup** for Langfuse database

4. **Consider sampling** for high-volume environments:
   ```bash
   OTEL_TRACES_SAMPLER=traceidratio
   OTEL_TRACES_SAMPLER_ARG=0.1  # Sample 10% of traces
   ```

5. **Monitor Langfuse resource usage** and scale as needed

## Benefits

### For Debugging
- See complete execution flow across all agents
- Inspect LLM prompts and responses
- Identify which tools were called and their results
- Track errors through the agent hierarchy

### For Performance
- Identify slow agents or tools
- Optimize tool execution order
- Find bottlenecks in agent chain

### For Cost Analysis
- Token usage per agent type
- Compare different model configurations
- Identify expensive operations

## Additional Resources

- [Langfuse Documentation](https://langfuse.com/docs)
- [Strands Telemetry Guide](https://strandsagents.com/latest/documentation/docs/user-guide/observability-evaluation/traces/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)

