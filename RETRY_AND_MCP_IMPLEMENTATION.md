# Agent Retry and MCP Tools Implementation Summary

## Overview

This document summarizes the implementation of:
1. **Agent Retry Logic** - Using tenacity for automatic retries on agent failures
2. **MCP Tools Integration** - AWS Knowledge MCP tools available to agents

## Agent Retry Implementation

### Created Files

- **`src/promptrca/utils/agent_retry.py`** - Retry utility module with:
  - `invoke_agent_with_retry()` - Synchronous agent invocation with retry
  - `invoke_agent_async_with_retry()` - Async agent invocation with retry
  - Default configuration: 3 retries, exponential backoff (1s to 60s)
  - Retries on: `TimeoutError`, `ConnectionError`, `ValueError`, `RuntimeError`

### Updated Files with Retry Logic

1. **`src/promptrca/core/direct_orchestrator.py`**
   - Line 590: Added retry to specialist agent invocations
   - Uses `invoke_agent_with_retry()` wrapper

2. **`src/promptrca/core/structured_report_node.py`**
   - Line 83: Added retry to structured report generation
   - Uses `invoke_agent_async_with_retry()` for async invocation

3. **`src/promptrca/agents/hypothesis_agent.py`**
   - Line 138: Added retry to hypothesis generation
   - Uses `invoke_agent_with_retry()` wrapper

4. **`src/promptrca/agents/root_cause_agent.py`**
   - Line 171: Added retry to root cause analysis
   - Uses `invoke_agent_with_retry()` wrapper

### Retry Configuration

- **Max Retries**: 3 attempts
- **Backoff Strategy**: Exponential (1s → 2s → 4s → ... up to 60s max)
- **Retryable Exceptions**: 
  - `TimeoutError`
  - `ConnectionError`
  - `ValueError`
  - `RuntimeError`
- **Logging**: All retry attempts are logged at appropriate levels

## MCP Tools Integration

### MCP Tools Available

The following AWS Knowledge MCP tools are available to agents:
- `search_aws_documentation` - Search AWS documentation
- `read_aws_documentation` - Read full AWS documentation pages

### Agents with MCP Tools

All specialist agents have MCP tools enabled:

1. **Service Specialists** (in `swarm_agents.py`):
   - ✅ `create_lambda_agent()` - Line 118
   - ✅ `create_apigateway_agent()` - Line 137
   - ✅ `create_stepfunctions_agent()` - Line 156
   - ✅ `create_iam_agent()` - Line 175
   - ✅ `create_s3_agent()` - Line 194
   - ✅ `create_sqs_agent()` - Line 213
   - ✅ `create_sns_agent()` - Line 232

2. **Analysis Agents** (recently added):
   - ✅ `create_hypothesis_agent()` - Line 256 (added MCP tools)
   - ✅ `create_root_cause_agent()` - Line 280 (added MCP tools)
   - ✅ `create_root_cause_agent_standalone()` - Line 349 (added MCP tools)

### Benefits of MCP Tools

- **Better Analysis**: Agents can look up AWS documentation for IAM permissions, integration patterns, and best practices
- **Accurate Remediation**: Root cause agent can provide accurate remediation advice based on official AWS docs
- **Evidence-Based Hypotheses**: Hypothesis agent can verify patterns against AWS documentation

## Usage Examples

### Using Retry in Your Code

```python
from promptrca.utils.agent_retry import invoke_agent_with_retry

# Synchronous invocation with retry
result = invoke_agent_with_retry(
    agent,
    "Your prompt here",
    max_retries=3
)

# Async invocation with retry
result = await invoke_agent_async_with_retry(
    agent,
    "Your prompt here",
    max_retries=3
)
```

### Agents Using MCP Tools

Agents automatically have access to MCP tools. They can use them like:

```python
# Agent can call:
search_aws_documentation("API Gateway Step Functions IAM permissions")
read_aws_documentation("https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-api-gateway.html")
```

## Configuration

### Retry Configuration

Retry behavior can be customized by passing parameters:

```python
invoke_agent_with_retry(
    agent,
    prompt,
    max_retries=5,  # Custom retry count
    initial_wait=2.0,  # Start with 2s delay
    max_wait=120.0,  # Max 120s delay
    retryable_exceptions=(TimeoutError, ConnectionError)  # Only retry these
)
```

### MCP Configuration

MCP is configured via environment variables (see `env.example`):
- `AWS_KNOWLEDGE_MCP_ENABLED=true`
- `AWS_KNOWLEDGE_MCP_URL=https://knowledge-mcp.global.api.aws`
- `AWS_KNOWLEDGE_MCP_TIMEOUT=30`

## Testing

To test retry functionality:
1. Simulate transient errors (timeout, connection errors)
2. Verify retry attempts are logged
3. Confirm final failure after max retries

To test MCP tools:
1. Enable MCP in environment
2. Agents should be able to search/read AWS documentation
3. Check logs for MCP tool usage

## Notes

- Retry logic gracefully handles failures - if all retries are exhausted, the original exception is raised
- MCP tools gracefully degrade - if MCP is unavailable, tools return "Documentation unavailable" messages
- Both features work independently and don't interfere with each other

