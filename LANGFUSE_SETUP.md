# OpenTelemetry Observability for PromptRCA

This document explains the OpenTelemetry observability integration for PromptRCA investigations, supporting multiple backends including Langfuse, AWS X-Ray, and other OTLP-compatible systems.

## What's Been Implemented

### 1. Generic OpenTelemetry Setup
- **Backend-agnostic**: Supports Langfuse, AWS X-Ray, and any OTLP-compatible backend
- **Automatic detection**: Backend type is detected based on endpoint URL and credentials
- **Strands SDK integration**: Configured for comprehensive tracing
- **OTLP exporter**: Sends traces to your chosen backend

### 2. Supported Backends

#### Langfuse (Self-Hosted or Cloud)
- **PostgreSQL database** for storing traces
- **ClickHouse database** for analytics and metrics (required for v3+)
- **Redis** for caching
- **Langfuse server** with web UI
- Dashboard available at: `http://localhost:3000`

#### AWS X-Ray
- **Native AWS integration** via OTLP
- **AWS credentials** automatically used for authentication
- **X-Ray console** for trace visualization
- **Service map** and performance insights

#### Generic OTLP Backends
- **Jaeger**, **Zipkin**, **New Relic**, **Datadog**, etc.
- **Custom headers** support for authentication
- **Flexible configuration** via environment variables

### 3. Automatic Trace Capture
- Agent lifecycle and execution flow
- LLM calls with prompts and responses
- Tool executions and results
- Token usage per agent invocation
- Performance metrics and timing

### 4. Trace Attributes
Enhanced traces include metadata for filtering and analysis:
- **Service identification**: service.name, agent.type
- **AWS context**: aws.service, agent.region
- **Investigation context**: Captured through agent prompts

### 5. Cost Tracking Maintained
- Existing TokenTracker still active for cost calculations
- Per-investigation cost breakdowns in API responses
- OpenTelemetry provides additional observability

## Quick Start

### Option 1: Langfuse Setup

#### 1. Start the Langfuse Stack

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

#### 2. Access Langfuse Dashboard

1. Open browser to `http://localhost:3000`
2. Create an account (first-time setup)
3. Navigate to "Traces" section

### Option 2: AWS X-Ray Setup

#### 1. Configure AWS Credentials

```bash
# Option A: AWS CLI
aws configure

# Option B: Environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=eu-west-1

# Option C: IAM Role (if running on EC2/Lambda)
# No additional configuration needed
```

#### 2. Update Environment Configuration

```bash
# Copy environment variables
cp env.example .env

# Edit .env and configure for X-Ray
OTEL_EXPORTER_OTLP_ENDPOINT=https://xray.amazonaws.com/v1/traces
OTEL_SERVICE_NAME=promptrca-server
AWS_REGION=eu-west-1

# Comment out Langfuse configuration
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
```

#### 3. Start PromptRCA

```bash
# Start only the PromptRCA service (no Langfuse stack needed)
docker-compose up promptrca-server
```

### Option 3: Generic OTLP Backend

#### 1. Configure Your Backend

```bash
# Copy environment variables
cp env.example .env

# Edit .env for your OTLP backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-backend:4317/v1/traces
OTEL_SERVICE_NAME=promptrca-server
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer your-token
```

### 4. Run an Investigation

```bash
# Example investigation
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{
    "free_text_input": "My Lambda function payment-processor is failing with errors"
  }'
```

### 5. View Traces

#### Langfuse
1. Go to Langfuse dashboard (`http://localhost:3000`)
2. Click on "Traces" in the sidebar

#### AWS X-Ray
1. Go to AWS X-Ray console
2. Navigate to "Traces" section
3. Filter by service name: `promptrca-server`

#### Generic Backend
1. Access your backend's web UI
2. Look for traces with service name: `promptrca-server`

You should see traces for:
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
- **By service**: `service.name = "promptrca-orchestrator"`

## Environment Variables

### Required for Tracing
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=<your-backend-endpoint>
OTEL_SERVICE_NAME=promptrca-server  # or promptrca-lambda
```

### Backend-Specific Configuration

#### Langfuse
```bash
# Langfuse OTLP endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
# OR for self-hosted: http://langfuse:3000/api/public/otel

# Langfuse credentials (auto-generates Basic Auth)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

# Langfuse self-hosted stack (if using docker-compose)
LANGFUSE_DB_NAME=langfuse
LANGFUSE_DB_USER=langfuse
LANGFUSE_DB_PASSWORD=langfuse
LANGFUSE_CLICKHOUSE_DB=langfuse
LANGFUSE_CLICKHOUSE_USER=langfuse
LANGFUSE_CLICKHOUSE_PASSWORD=langfuse
LANGFUSE_NEXTAUTH_SECRET=your-secret-key-change-in-production
LANGFUSE_ENCRYPTION_KEY=your-encryption-key-change-in-production
```

#### AWS X-Ray
```bash
# X-Ray OTLP endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=https://xray.amazonaws.com/v1/traces

# AWS credentials (choose one method)
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=eu-west-1
# OR use AWS CLI: aws configure
# OR use IAM roles (if running on EC2/Lambda)
```

#### Generic OTLP Backend
```bash
# Your OTLP backend endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-backend:4317/v1/traces

# Custom headers (optional)
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer your-token,Other-Header=value
```

### Optional for Development
```bash
OTEL_CONSOLE_EXPORT=true  # Also print traces to console
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
   docker-compose logs promptrca-server | grep "telemetry"
   # Should see: "✅ Strands telemetry configured"
   ```

3. **Check for errors in PromptRCA logs**:
   ```bash
   docker-compose logs promptrca-server
   ```

4. **Verify network connectivity**:
   ```bash
   docker-compose exec promptrca-server ping -c 3 langfuse
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

