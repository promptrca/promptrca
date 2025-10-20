# Swarm Orchestrator Guide

## Overview

The Swarm Orchestrator implements Strands Agents best practices using the **Swarm Pattern** for collaborative multi-agent AWS infrastructure investigation.

## Key Features

### 🤖 Autonomous Agent Coordination
- Agents decide investigation flow based on findings
- Intelligent handoffs between specialists
- Emergent behavior for complex investigations

### 🔧 Tool-Agent Pattern
- Specialists wrapped as `@tool` decorated functions
- Modular and reusable components
- Follows Strands conventions

### 🔄 Shared Context
- `invocation_state` for context sharing
- Consistent data across all agents
- No context leakage to LLM prompts

### 🎯 Specialized Agents
- **Lambda Specialist**: Function config, logs, performance, IAM
- **API Gateway Specialist**: Configuration, stages, integrations
- **Step Functions Specialist**: State machines, executions, errors
- **Trace Specialist**: X-Ray traces, service interactions

## Usage

### Basic Investigation

```python
from src.promptrca.core.investigator import PromptRCAInvestigator

# Create investigator with Swarm orchestrator
investigator = PromptRCAInvestigator(
    region="us-east-1",
    xray_trace_id="1-67890123-abcdef1234567890abcdef12",
    investigation_target={
        "type": "lambda",
        "name": "my-function"
    },
    orchestrator_type="swarm"  # Use Swarm pattern
)

# Run investigation
report = await investigator.investigate()
```

### Environment Variable Configuration

```bash
# Set default orchestrator
export PROMPTRCA_ORCHESTRATOR=swarm

# Run investigation (will use Swarm by default)
python -m src.promptrca.cli investigate --trace-id 1-67890123-abcdef1234567890abcdef12
```

### Direct Orchestrator Usage

```python
from src.promptrca.core.swarm_orchestrator import SwarmOrchestrator

# Direct usage
orchestrator = SwarmOrchestrator(region="us-east-1")

result = await orchestrator.investigate({
    "xray_trace_id": "1-67890123-abcdef1234567890abcdef12",
    "investigation_target": {
        "type": "lambda",
        "name": "my-function"
    }
})
```

## Agent Behavior

### Investigation Flow

1. **Trace Specialist** analyzes X-Ray traces first
2. **Service Specialists** analyze their respective resources
3. **Collaborative Handoffs** when cross-service issues found
4. **Autonomous Coordination** based on findings

### Agent Prompts

Each agent has specialized system prompts:

```python
# Lambda Specialist
"You are a Lambda specialist agent for AWS infrastructure investigation.
Your expertise includes Lambda function configuration analysis, 
CloudWatch logs analysis, performance issues, and IAM permissions..."

# API Gateway Specialist  
"You are an API Gateway specialist agent for AWS infrastructure investigation.
Your expertise includes API Gateway configuration, stage analysis,
integration configurations, and execution logs..."
```

### Tool Integration

Specialists are wrapped as tools:

```python
@tool
def lambda_specialist_tool(resource_data: str, investigation_context: str) -> str:
    """Analyze Lambda function configuration, logs, and performance issues."""
    # Implementation uses existing LambdaSpecialist class
    # Returns JSON with facts and analysis
```

## Benefits vs Direct Orchestration

| Aspect | Direct Orchestrator | Swarm Orchestrator |
|--------|-------------------|-------------------|
| **Coordination** | Python code decides flow | Agents decide autonomously |
| **Patterns** | Custom implementation | Strands best practices |
| **Handoffs** | Manual coordination | Agent-to-agent communication |
| **Context** | Manual passing | Shared `invocation_state` |
| **Extensibility** | Add Python logic | Add new agents/tools |
| **Maintainability** | Custom patterns | Proven frameworks |

## Configuration

### Orchestrator Selection

```python
# In code
investigator = PromptRCAInvestigator(orchestrator_type="swarm")

# Environment variable
os.environ["PROMPTRCA_ORCHESTRATOR"] = "swarm"

# Default (if not specified)
# Uses "direct" orchestrator for backward compatibility
```

### Agent Configuration

Agents use existing model configuration:

```python
# Uses same model factories as other agents
model = create_hypothesis_agent_model()
agent = Agent(model=model, tools=[specialist_tools])
```

## Testing

### Unit Tests

```bash
# Test Swarm orchestrator
pytest tests/test_swarm_orchestrator.py

# Test tool functions
pytest tests/test_swarm_orchestrator.py::TestSwarmTools
```

### Integration Testing

```bash
# Test with sample data
python test_swarm_example.py

# Compare orchestrators
TEST_MODE=compare python test_swarm_example.py
```

### Manual Testing

```bash
# Set environment
export PROMPTRCA_ORCHESTRATOR=swarm

# Run investigation
python -m src.promptrca.cli investigate \
  --trace-id 1-67890123-abcdef1234567890abcdef12 \
  --function-name my-function
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure Strands is installed
2. **Tool Failures**: Check specialist class implementations
3. **Context Issues**: Verify `invocation_state` structure
4. **Agent Loops**: Check `max_iterations` setting

### Debug Mode

```python
import logging
logging.getLogger("src.promptrca").setLevel(logging.DEBUG)

# Run investigation with debug logging
```

### Monitoring

```python
# Check agent handoffs in logs
logger.info("Agent handoff patterns:")
# Look for handoff_to_agent tool calls
```

## Migration Guide

### From Direct to Swarm

1. **Update Code**:
   ```python
   # Before
   investigator = PromptRCAInvestigator(orchestrator_type="direct")
   
   # After  
   investigator = PromptRCAInvestigator(orchestrator_type="swarm")
   ```

2. **Test Compatibility**:
   ```bash
   # A/B test both orchestrators
   TEST_MODE=compare python test_swarm_example.py
   ```

3. **Monitor Performance**:
   - Compare investigation times
   - Check fact quality and quantity
   - Monitor error rates

### Rollback Plan

```python
# Environment variable rollback
export PROMPTRCA_ORCHESTRATOR=direct

# Or code-level rollback
investigator = PromptRCAInvestigator(orchestrator_type="direct")
```

## Future Enhancements

1. **Agent Memory**: Add conversation memory for complex investigations
2. **Custom Agents**: Framework for adding domain-specific agents
3. **Evaluation Metrics**: Automated quality assessment
4. **Performance Optimization**: Parallel agent execution improvements