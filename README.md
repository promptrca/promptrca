# Sherlock Core - Docker Operations

This directory contains the reorganized Sherlock core package with service-specific tools and a production-ready Docker setup.

## Quick Start

### Build and Run
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

## Available Commands

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

## Testing the Lambda Function

Once the container is running, you can test it with:

```bash
# Using make
make test

# Or manually with curl
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{"free_text_input": "Test Lambda function investigation"}' \
  -H "Content-Type: application/json"
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
