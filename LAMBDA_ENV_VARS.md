# Lambda Environment Variables Configuration

This document lists all environment variables needed for the Lambda function to work like the server.

## Required Environment Variables

### AWS Configuration (Required)
```bash
AWS_REGION=eu-west-1              # AWS region for investigations
# OR
AWS_DEFAULT_REGION=eu-west-1      # Alternative region variable
```

### AWS Credentials (Required - typically via IAM role, but can use env vars)
```bash
AWS_ACCESS_KEY_ID=...             # If not using IAM role
AWS_SECRET_ACCESS_KEY=...         # If not using IAM role
AWS_SESSION_TOKEN=...             # If using temporary credentials
```

## Model Configuration (Optional - has defaults)

### Global Model Settings
```bash
BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0    # Default model for all agents
PROMPTRCA_TEMPERATURE=0.7                    # Default temperature
PROMPTRCA_MAX_TOKENS=4000                    # Optional: max tokens
```

### Orchestrator Model
```bash
PROMPTRCA_ORCHESTRATOR_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
PROMPTRCA_ORCHESTRATOR_TEMPERATURE=0.7
```

### Specialist Agent Models
```bash
# Lambda Specialist
PROMPTRCA_LAMBDA_MODEL_ID=openai.gpt-oss-120b-1:0
PROMPTRCA_LAMBDA_TEMPERATURE=0.5

# API Gateway Specialist
PROMPTRCA_APIGATEWAY_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_APIGATEWAY_TEMPERATURE=0.6

# Step Functions Specialist
PROMPTRCA_STEPFUNCTIONS_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_STEPFUNCTIONS_TEMPERATURE=0.6

# IAM Specialist
PROMPTRCA_IAM_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_IAM_TEMPERATURE=0.4

# DynamoDB Specialist
PROMPTRCA_DYNAMODB_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_DYNAMODB_TEMPERATURE=0.6

# S3 Specialist
PROMPTRCA_S3_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_S3_TEMPERATURE=0.6

# SQS Specialist
PROMPTRCA_SQS_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_SQS_TEMPERATURE=0.6

# SNS Specialist
PROMPTRCA_SNS_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_SNS_TEMPERATURE=0.6

# EventBridge Specialist
PROMPTRCA_EVENTBRIDGE_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_EVENTBRIDGE_TEMPERATURE=0.6

# VPC Specialist
PROMPTRCA_VPC_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_VPC_TEMPERATURE=0.6
```

### Analysis Agent Models
```bash
# Hypothesis Agent
PROMPTRCA_HYPOTHESIS_MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0
PROMPTRCA_HYPOTHESIS_TEMPERATURE=0.3

# Root Cause Agent
PROMPTRCA_ROOT_CAUSE_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
PROMPTRCA_ROOT_CAUSE_TEMPERATURE=0.2
```

### Specialist Category Override (applies to all specialists if set)
```bash
PROMPTRCA_SPECIALIST_MODEL_ID=...            # Overrides all specialist models
PROMPTRCA_SPECIALIST_TEMPERATURE=...         # Overrides all specialist temps
```

### Synthesis Model
```bash
PROMPTRCA_SYNTHESIS_TEMPERATURE=0.2
```

### Parser Model
```bash
PROMPTRCA_PARSER_TEMPERATURE=0.1
PROMPTRCA_PARSER_MAX_TOKENS=256
```

## Orchestrator Configuration
```bash
PROMPTRCA_ORCHESTRATOR=swarm                 # Use "swarm" for SwarmOrchestrator
```

Note: Currently SwarmOrchestrator uses hardcoded values, but these env vars may be used in future versions:
```bash
SWARM_MAX_HANDOFFS=12                        # Max agent handoffs
SWARM_MAX_ITERATIONS=15                      # Max iterations
SWARM_EXECUTION_TIMEOUT=450.0                # Total timeout in seconds
SWARM_NODE_TIMEOUT=60.0                      # Per-node timeout in seconds
```

## Observability / Telemetry (Optional)

### Langfuse Configuration
```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com     # Or https://us.cloud.langfuse.com
OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
OTEL_SERVICE_NAME=promptrca-lambda
```

### Generic OpenTelemetry Configuration
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-otlp-backend:4317
OTEL_SERVICE_NAME=promptrca-lambda
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer your-token
OTEL_CONSOLE_EXPORT=false                    # Set to "true" to print traces to console
```

### AWS X-Ray (alternative to Langfuse)
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=https://xray.amazonaws.com/v1/traces
OTEL_SERVICE_NAME=promptrca-lambda
AWS_REGION=eu-west-1
```

## AWS Knowledge MCP (Optional)
```bash
ENABLE_AWS_KNOWLEDGE_MCP=false               # Enable AWS Knowledge MCP integration
AWS_KNOWLEDGE_MCP_URL=https://knowledge-mcp.global.api.aws
AWS_KNOWLEDGE_MCP_TIMEOUT=5                  # Timeout in seconds
AWS_KNOWLEDGE_MCP_RETRIES=2                  # Max retries
```

## Development / Debug
```bash
DEBUG_MODE=false                              # Enable debug mode
```

## Minimum Configuration for Lambda

For a basic Lambda deployment, you only need:
```bash
AWS_REGION=eu-west-1
BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0
PROMPTRCA_TEMPERATURE=0.7
PROMPTRCA_ORCHESTRATOR=swarm
```

All other variables have sensible defaults or are optional.

## Full Production Configuration

For production use matching the server configuration:
```bash
# AWS
AWS_REGION=eu-west-1

# Models
BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0
PROMPTRCA_TEMPERATURE=0.7
PROMPTRCA_ORCHESTRATOR_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0
PROMPTRCA_ORCHESTRATOR_TEMPERATURE=0.7

# Orchestrator
PROMPTRCA_ORCHESTRATOR=swarm

# Observability (if using Langfuse)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
OTEL_EXPORTER_OTLP_ENDPOINT=https://cloud.langfuse.com/api/public/otel
OTEL_SERVICE_NAME=promptrca-lambda
```

## Setting in AWS Lambda

### Via Lambda Console
1. Go to Lambda Function → Configuration → Environment Variables
2. Add each variable as a key-value pair

### Via AWS CLI
```bash
aws lambda update-function-configuration \
  --function-name promptrca-investigator \
  --environment "Variables={
    AWS_REGION=eu-west-1,
    BEDROCK_MODEL_ID=openai.gpt-oss-120b-1:0,
    PROMPTRCA_TEMPERATURE=0.7,
    PROMPTRCA_ORCHESTRATOR=swarm
  }"
```

### Via Terraform
```hcl
resource "aws_lambda_function" "promptrca" {
  # ... other configuration ...
  
  environment {
    variables = {
      AWS_REGION              = "eu-west-1"
      BEDROCK_MODEL_ID        = "openai.gpt-oss-120b-1:0"
      PROMPTRCA_TEMPERATURE   = "0.7"
      PROMPTRCA_ORCHESTRATOR  = "swarm"
      # Add more as needed
    }
  }
}
```

### Via SAM Template
```yaml
Resources:
  PromptRCAFunction:
    Type: AWS::Serverless::Function
    Properties:
      Environment:
        Variables:
          AWS_REGION: eu-west-1
          BEDROCK_MODEL_ID: openai.gpt-oss-120b-1:0
          PROMPTRCA_TEMPERATURE: "0.7"
          PROMPTRCA_ORCHESTRATOR: swarm
```

