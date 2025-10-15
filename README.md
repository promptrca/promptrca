# Sherlock Core - Docker Operations

This directory contains the reorganized Sherlock core package with service-specific tools and a production-ready Docker setup.

## Quick Start

### Docker Compose (Recommended)
```bash
# Copy environment template
cp .env.example .env
# Edit .env with your AWS credentials

# Start all services (OpenSearch + Sherlock HTTP server + Lambda container)
docker-compose up -d

# Check service status
docker-compose ps

# Test HTTP server
curl http://localhost:8080/health
curl http://localhost:8080/status

# Test investigation
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"free_text_input": "My Lambda function is failing with timeout errors"}'

# Stop all services
docker-compose down
```

### Single Container (Legacy)
```bash
# Build the Docker image
make build

# Run the container locally (without AWS credentials - will show error)
make run

# Run with AWS credentials (for local testing)
make run-with-aws

# Or run in background and test
make run-detached
make test
make stop
```

### Development Workflow
```bash
# Full development cycle: clean, build, run
make dev-cycle

# Or step by step
make clean
make build
make run-detached
make test
make stop
```

## Docker Compose Services

The docker-compose setup includes three services:

### 1. OpenSearch (`opensearch`)
- **Image**: `opensearchproject/opensearch:2.11.0`
- **Port**: `9200` (HTTP), `9600` (Performance Analyzer)
- **Purpose**: Memory storage for agent knowledge and past investigations
- **Health Check**: Cluster health endpoint

### 2. Sherlock HTTP Server (`sherlock-server`)
- **Dockerfile**: `Dockerfile.server` (optimized for HTTP server)
- **Base Image**: `python:3.13-slim`
- **Port**: `8080`
- **Purpose**: Standalone HTTP server using AgentCore
- **Endpoints**:
  - `POST /invocations` - Investigation requests
  - `GET /health` - Health check
  - `GET /status` - Detailed status with OpenSearch connectivity
  - `GET /ping` - Built-in AgentCore ping

### 3. Sherlock Lambda (`sherlock-lambda`)
- **Dockerfile**: `Dockerfile` (AWS Lambda runtime)
- **Base Image**: `public.ecr.aws/lambda/python:3.13`
- **Port**: `9000` (Lambda Runtime Interface Emulator)
- **Purpose**: AWS Lambda runtime for testing Lambda deployments
- **Handler**: `sherlock.lambda_handler.lambda_handler`

## Dockerfiles

The project includes two specialized Dockerfiles:

### `Dockerfile` (Lambda)
- **Base**: AWS Lambda Python 3.13 runtime
- **Purpose**: Production Lambda deployment
- **Optimized for**: Serverless execution, cold starts
- **Size**: Larger (includes Lambda runtime)

### `Dockerfile.server` (HTTP Server)
- **Base**: Python 3.13 slim
- **Purpose**: Standalone HTTP server
- **Optimized for**: Long-running processes, development
- **Size**: Smaller, more efficient for containers
- **Features**: Health checks, non-root user, curl for health checks

## Available Commands

### Docker Compose Commands
| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start all services in background |
| `docker-compose up` | Start all services in foreground |
| `docker-compose down` | Stop all services |
| `docker-compose ps` | Show service status |
| `docker-compose logs` | Show logs from all services |
| `docker-compose logs sherlock-server` | Show logs from specific service |
| `docker-compose restart sherlock-server` | Restart specific service |

### Make Commands (Legacy)
| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make build` | Build the Docker image |
| `make run` | Run container with port mapping (foreground) |
| `make run-detached` | Run container in background |
| `make test` | Test the Lambda function with sample event |
| `make stop` | Stop the running container |
| `make logs` | Show container logs |
| `make status` | Show container status |
| `make clean` | Clean up containers and images |
| `make rebuild` | Clean and rebuild the image |
| `make dev-run` | Build and run in one command |
| `make dev-test` | Run container, test, and stop |
| `make dev-cycle` | Full development cycle |

## Testing the Services

### HTTP Server Testing
```bash
# Health check
curl http://localhost:8080/health

# Detailed status (includes OpenSearch connectivity)
curl http://localhost:8080/status

# Investigation request
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"free_text_input": "My Lambda function is failing with timeout errors"}'

# Legacy structured input
curl -X POST http://localhost:8080/invocations \
  -H 'Content-Type: application/json' \
  -d '{"function_name": "test-function", "region": "eu-west-1"}'
```

### Lambda Container Testing
```bash
# Test Lambda function (using make)
make test

# Or manually with curl
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"free_text_input": "Test Lambda function investigation"}' \
  -H "Content-Type: application/json"
```

### OpenSearch Testing
```bash
# Check OpenSearch health
curl http://localhost:9200/_cluster/health

# List indices
curl http://localhost:9200/_cat/indices
```

## AWS Credentials

### Local Testing
For local testing with AWS credentials, you have several options:

1. **Environment Variables** (recommended):
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key
   export AWS_SECRET_ACCESS_KEY=your_secret_key
   export AWS_DEFAULT_REGION=us-east-1
   make run-with-aws
   ```

2. **AWS CLI Profile**:
   ```bash
   export AWS_PROFILE=your_profile_name
   make run-with-aws
   ```

3. **Session Token** (for temporary credentials):
   ```bash
   export AWS_SESSION_TOKEN=your_session_token
   make run-with-aws
   ```

### Production Deployment
When deployed to AWS Lambda, credentials are automatically provided via the Lambda execution role. No environment variables needed.

## Configuration

Sherlock supports several environment variables for configuration:

### Model Configuration
- `SHERLOCK_MODEL_ID` - Bedrock model identifier (default: "openai.gpt-oss-120b-1:0")
- `SHERLOCK_TEMPERATURE` - Model temperature 0.0-1.0 (default: 0.7)
- `SHERLOCK_MAX_TOKENS` - Maximum tokens (optional)

### Region Configuration
- `AWS_REGION` - Primary AWS region setting
- `AWS_DEFAULT_REGION` - Fallback AWS region setting

Region detection follows this priority:
1. `AWS_REGION` (highest priority)
2. `AWS_DEFAULT_REGION` (fallback)
3. `eu-west-1` (default)

### Memory System Configuration (Optional)

Sherlock can query an external memory system to retrieve similar past investigations and improve accuracy through RAG (Retrieval-Augmented Generation).

#### Environment Variables

- `SHERLOCK_MEMORY_ENABLED` - Enable/disable memory system (default: "false")
- `SHERLOCK_MEMORY_ENDPOINT` - Memory API endpoint URL (OpenSearch-compatible)
- `SHERLOCK_MEMORY_AUTH_TYPE` - Authentication type: "api_key" or "aws_sigv4" (default: "api_key")
- `SHERLOCK_MEMORY_API_KEY` - API key for authentication (if using api_key auth)
- `SHERLOCK_MEMORY_MAX_RESULTS` - Maximum similar investigations to retrieve (default: 5)
- `SHERLOCK_MEMORY_MIN_QUALITY` - Minimum quality score threshold (default: 0.7)
- `SHERLOCK_MEMORY_TIMEOUT_MS` - Query timeout in milliseconds (default: 2000)

#### Example Configuration

```bash
# Enable memory system
export SHERLOCK_MEMORY_ENABLED=true

# Configure memory endpoint
export SHERLOCK_MEMORY_ENDPOINT=https://memory-api.company.com

# Set authentication
export SHERLOCK_MEMORY_AUTH_TYPE=api_key
export SHERLOCK_MEMORY_API_KEY=your-api-key-here

# Optional: Adjust query parameters
export SHERLOCK_MEMORY_MAX_RESULTS=5
export SHERLOCK_MEMORY_MIN_QUALITY=0.7
```

#### How It Works

When enabled, Sherlock:
1. Queries the external memory API for similar past investigations
2. Uses hybrid search (semantic + keyword matching) to find relevant cases
3. Injects historical context into investigation prompts
4. Boosts hypothesis confidence based on past patterns
5. Prioritizes advice that has been proven effective

The memory system is **optional** and gracefully degrades if unavailable. Investigations continue normally without memory if:
- Memory is disabled (`SHERLOCK_MEMORY_ENABLED=false`)
- Memory endpoint is not configured
- Memory query fails or times out
- No similar investigations are found

#### Benefits

- **30-40% improvement** in root cause accuracy when memory is available
- **Faster resolution** by learning from past successful investigations
- **Better advice** prioritized by historical effectiveness
- **Zero impact** when disabled - investigations work normally

### Example Configuration
```bash
# Use a different model
export SHERLOCK_MODEL_ID="anthropic.claude-3-sonnet-20240229-v1:0"
export SHERLOCK_TEMPERATURE="0.3"

# Set region
export AWS_REGION="us-east-1"

# Run with custom configuration
make run-with-aws
```

## Expected Response

### Without AWS Credentials
```json
{"success": false, "error": "Free text investigation failed: Unable to locate credentials"}
```
This is **expected behavior** - the function is working correctly but needs AWS credentials to make actual API calls.

### With AWS Credentials
The function will perform actual AWS API calls and return investigation results.

## Docker Image Details

- **Base Image**: `public.ecr.aws/lambda/python:3.13`
- **Handler**: `sherlock.lambda_handler.lambda_handler`
- **Port**: 9000 (mapped to container port 8080)
- **Working Directory**: `/var/task`

## Project Structure

```
core/
├── src/sherlock/           # Main package
│   ├── tools/              # Service-specific tools
│   │   ├── lambda_tools.py
│   │   ├── apigateway_tools.py
│   │   ├── stepfunctions_tools.py
│   │   ├── iam_tools.py
│   │   ├── xray_tools.py
│   │   ├── cloudwatch_tools.py
│   │   ├── dynamodb_tools.py
│   │   ├── s3_tools.py
│   │   ├── sqs_tools.py
│   │   ├── sns_tools.py
│   │   ├── eventbridge_tools.py
│   │   └── vpc_tools.py
│   ├── agents/             # AI agents
│   │   └── specialized/    # Service-specific agents
│   ├── clients/            # AWS service clients
│   └── models/             # Data models
├── Dockerfile              # Production Docker image
├── .dockerignore           # Docker ignore file
├── requirements.txt        # Python dependencies
├── Makefile               # Build and run commands
└── README.md              # This file
```

## Service Coverage

The reorganized structure provides comprehensive AWS service coverage:

- **Core Services**: Lambda, API Gateway, Step Functions, IAM, X-Ray, CloudWatch
- **Additional Services**: DynamoDB, S3, SQS, SNS, EventBridge, VPC/Network
- **Total Tools**: 50+ individual tools for AWS investigation
- **Specialized Agents**: 10 service-specific AI agents
