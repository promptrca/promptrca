# Strands Swarm Refactor - Best Practices Implementation

## Overview

Refactored PromptRCA to follow Strands Agents best practices using the **Swarm Pattern** for collaborative multi-agent AWS infrastructure investigation.

## Architecture Changes

### Before: Custom Python Orchestration
```
DirectOrchestrator (Python)
├── Manual specialist coordination
├── Custom fact collection
├── Sequential/parallel execution via asyncio
└── No agent-to-agent communication
```

### After: Strands Swarm Pattern
```
SwarmOrchestrator (Strands)
├── Autonomous agent coordination
├── Tool-Agent pattern implementation
├── Shared context across agents
└── Agent-to-agent handoffs
```

## Key Improvements

### 1. Tool-Agent Pattern Implementation
- **Before**: Direct specialist class invocation
- **After**: Specialists wrapped as `@tool` decorated functions
- **Benefit**: Modularity and reusability following Strands conventions

### 2. Autonomous Agent Coordination
- **Before**: Python code decides investigation flow
- **After**: Agents decide handoffs based on findings
- **Benefit**: Emergent behavior and intelligent routing

### 3. Shared Context
- **Before**: Manual context passing
- **After**: `invocation_state` for shared context across agents
- **Benefit**: Consistent context without exposing to LLM prompts

### 4. Specialized Agent Prompts
- **Before**: Generic tool execution
- **After**: Domain-specific system prompts for each specialist
- **Benefit**: Better domain expertise and decision making

## Agent Specialization

### Lambda Specialist Agent
- **Tools**: `lambda_specialist_tool`
- **Expertise**: Function config, logs, performance, IAM permissions
- **Handoffs**: To API Gateway/Step Functions when integration issues found

### API Gateway Specialist Agent  
- **Tools**: `apigateway_specialist_tool`
- **Expertise**: Configuration, stages, integrations, execution logs
- **Handoffs**: To Lambda/Step Functions for service-specific issues

### Step Functions Specialist Agent
- **Tools**: `stepfunctions_specialist_tool` 
- **Expertise**: State machine executions, errors, permissions
- **Handoffs**: To Lambda/API Gateway for integration problems

### Trace Analysis Specialist Agent
- **Tools**: `trace_specialist_tool`
- **Expertise**: X-Ray traces, service interactions, cross-service errors
- **Handoffs**: To service specialists for specific service issues

## Benefits of Swarm Pattern

### 1. Matches Investigation Workflow
- **Specialized Expertise**: Each agent has domain knowledge
- **Collaborative Handoffs**: Agents pass findings to each other
- **Emergent Behavior**: Investigation path depends on discoveries
- **Shared Context**: All agents access trace IDs, region, resources

### 2. Strands Best Practices
- Uses proven multi-agent patterns
- Follows Tool-Agent pattern conventions
- Implements proper agent coordination
- Leverages `invocation_state` for context sharing

### 3. Improved Maintainability
- Clear separation of concerns
- Reusable tool components
- Standardized agent interfaces
- Better error handling and logging

## Usage Example

```python
from src.promptrca.core.swarm_orchestrator import SwarmOrchestrator

orchestrator = SwarmOrchestrator(region="us-east-1")

result = await orchestrator.investigate({
    "xray_trace_id": "1-67...",
    "investigation_target": {
        "type": "lambda",
        "name": "my-function"
    }
})
```

## Migration Path

1. **Phase 1**: Deploy SwarmOrchestrator alongside existing orchestrators
2. **Phase 2**: A/B test Swarm vs Direct orchestration
3. **Phase 3**: Migrate to Swarm as primary orchestrator
4. **Phase 4**: Deprecate custom orchestration patterns

## Testing Strategy

- Unit tests for each tool-wrapped specialist
- Integration tests for swarm coordination
- Comparison tests against existing orchestrators
- Performance benchmarking

## Next Steps

1. Add comprehensive error handling for tool failures
2. Implement agent memory for complex investigations
3. Add evaluation metrics for swarm effectiveness
4. Create monitoring for agent handoff patterns