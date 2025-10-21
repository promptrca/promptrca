# Design Document

## Overview

This design refactors the PromptRCA swarm orchestrator to eliminate code duplication, remove placeholder implementations, and create a clean, maintainable architecture that leverages existing AWS tools and specialist classes. The refactoring will transform a monolithic 2000+ line file into a well-organized, modular system.

## Architecture

### Current State Analysis

**Problems Identified:**
- `swarm_orchestrator.py` is 2000+ lines with everything mixed together
- Placeholder specialist tools (`iam_specialist_tool`, `s3_specialist_tool`, etc.) that don't make real AWS API calls
- Duplicate functionality - real AWS tools exist in `tools/` directory but aren't used
- Specialist classes exist but are bypassed by placeholder tool implementations
- Agent definitions, tool implementations, and orchestration logic all in one file

**Existing Assets to Leverage:**
- Comprehensive AWS tools in `src/promptrca/tools/` (lambda_tools.py, stepfunctions_tools.py, etc.)
- Proper specialist classes in `src/promptrca/specialists/` (LambdaSpecialist, APIGatewaySpecialist, etc.)
- Working trace analysis and core orchestration logic
- Strands Swarm pattern implementation

### Target Architecture

```
src/promptrca/
├── agents/
│   ├── swarm_agents.py          # Agent definitions and prompts
│   └── agent_factory.py         # Agent creation utilities
├── core/
│   ├── swarm_orchestrator.py    # Orchestration logic only (~500 lines)
│   └── swarm_tools.py           # Tool wrappers for specialists
├── specialists/                 # Existing - no changes needed
│   ├── base_specialist.py
│   ├── lambda_specialist.py
│   └── ...
└── tools/                       # Existing - no changes needed
    ├── lambda_tools.py
    ├── stepfunctions_tools.py
    └── ...
```

## Components and Interfaces

### 1. Swarm Tools Module (`src/promptrca/core/swarm_tools.py`)

**Purpose:** Provide clean Strands tool wrappers that delegate to existing specialist classes following Strands best practices.

**Key Functions:**
```python
@tool(context=True)
def lambda_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """Real implementation using LambdaSpecialist class with proper ToolResult format"""
    
@tool(context=True)  
def apigateway_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """Real implementation using APIGatewaySpecialist class with proper ToolResult format"""
    
@tool(context=True)
def stepfunctions_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """Real implementation using StepFunctionsSpecialist class with proper ToolResult format"""
    
@tool(context=True)
def trace_specialist_tool(trace_ids: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """Real implementation using TraceSpecialist class with proper ToolResult format"""
```

**Strands Best Practices Applied:**
- All tools use `@tool(context=True)` to access ToolContext for invocation_state
- Return proper ToolResult dictionaries with status and content structure
- Access AWS client from `tool_context.invocation_state.get('aws_client')`
- Use structured error responses with status="error" and descriptive content
- Leverage invocation_state for cross-account credentials and shared context
- Each tool delegates to the corresponding specialist class
- No duplicate AWS API logic - specialists use existing AWS tools
- Consistent error handling and response formatting

### 2. Swarm Agents Module (`src/promptrca/agents/swarm_agents.py`)

**Purpose:** Define agent configurations, prompts, and tool assignments following Strands Swarm best practices.

**Key Components:**
```python
# Agent prompt templates following Strands best practices
TRACE_AGENT_PROMPT = """You are the trace analysis specialist and ENTRY POINT for AWS infrastructure investigations.

ROLE: Analyze X-Ray traces to understand service interactions and identify which services need detailed investigation.

ANALYSIS FOCUS:
- Service interaction patterns and call flows
- Error locations and failure points
- Performance bottlenecks and timeouts
- Cross-service integration issues

HANDOFF STRATEGY:
- Use handoff_to_agent() tool to transfer control to appropriate specialists
- Include specific findings and context in handoff message
- Provide context dictionary with trace findings for next agent

TERMINATION RULES (CRITICAL FOR COST CONTROL):
- ALWAYS hand off after trace analysis - NEVER do detailed service analysis
- If no traces available → hand off to lambda_specialist as default
- If multiple services involved → start with service showing most errors
- NEVER hand off back to trace_specialist once investigation starts

IMPORTANT: You are the investigation coordinator. Always hand off to specialists - never attempt detailed service analysis yourself."""

LAMBDA_AGENT_PROMPT = """You are a Lambda specialist in an AWS infrastructure investigation swarm.

ROLE: Analyze Lambda functions and identify issues using your specialist tools.

ANALYSIS FOCUS:
- Configuration and IAM permission issues
- Performance, memory, and timeout problems  
- Integration errors with other AWS services
- Runtime and deployment issues

WORKFLOW:
1. Use lambda_specialist_tool to analyze Lambda resources
2. Identify key findings and issues
3. Determine if other specialists need to investigate related services

HANDOFF RULES (CRITICAL FOR COST CONTROL):
- If you find API Gateway integration issues → hand off to apigateway_specialist
- If you find Step Functions integration issues → hand off to stepfunctions_specialist  
- If you find cross-service issues → hand off to appropriate specialist
- When analysis is complete and no other services need investigation → hand off to hypothesis_generator
- NEVER hand off back to trace_specialist
- NEVER hand off to the same specialist twice

TERMINATION: When your Lambda analysis is complete, you MUST hand off to hypothesis_generator."""

HYPOTHESIS_AGENT_PROMPT = """You are a hypothesis generation specialist for AWS infrastructure investigations.

ROLE: Analyze facts from specialist agents and generate evidence-based hypotheses about root causes.

WORKFLOW:
1. Wait to receive facts from specialist agents (lambda_specialist, apigateway_specialist, etc.)
2. Analyze facts systematically and generate 2-5 hypotheses with supporting evidence
3. Focus on AWS-specific patterns: permission issues, timeouts, resource constraints, integration failures

HANDOFF RULES (CRITICAL FOR COST CONTROL):
- ALWAYS hand off to root_cause_analyzer when you have generated hypotheses
- Include your hypotheses in the handoff message
- NEVER hand off back to any specialist agents
- NEVER attempt root cause analysis yourself

TERMINATION: You MUST hand off to root_cause_analyzer after generating hypotheses."""

ROOT_CAUSE_AGENT_PROMPT = """You are the final root cause analysis specialist for AWS infrastructure investigations.

ROLE: Provide the definitive root cause analysis and complete the investigation.

WORKFLOW:
1. Receive hypotheses from hypothesis_generator
2. Evaluate each hypothesis against available facts
3. Identify the most probable root cause
4. Provide actionable recommendations and next steps

TERMINATION RULES (CRITICAL FOR COST CONTROL):
- You are the FINAL agent in the investigation
- NEVER hand off to any other agent
- Provide a comprehensive final response
- Investigation ENDS with your response

IMPORTANT: You are the investigation terminus. Provide complete, actionable results and END the investigation."""

# Agent factory functions following Strands patterns
def create_trace_agent() -> Agent:
    """Create trace analysis agent with proper tools and configuration"""
    return Agent(
        name="trace_specialist",
        model=create_orchestrator_model(),
        system_prompt=TRACE_AGENT_PROMPT,
        tools=[trace_specialist_tool]
    )
    
def create_lambda_agent() -> Agent:
    """Create Lambda specialist agent with descriptive name and clear role"""
    return Agent(
        name="lambda_specialist", 
        model=create_lambda_agent_model(),
        system_prompt=LAMBDA_AGENT_PROMPT,
        tools=[lambda_specialist_tool]
    )
    
def create_swarm_agents() -> List[Agent]:
    """Create all swarm agents following Strands best practices"""
    return [
        create_trace_agent(),
        create_lambda_agent(),
        create_apigateway_agent(),
        create_stepfunctions_agent(),
        create_hypothesis_agent(),
        create_root_cause_agent()
    ]
```

**Strands Best Practices Applied:**
- Use descriptive agent names that reflect specialties
- Clear role definitions in system prompts with STRICT handoff rules
- Explicit handoff instructions using handoff_to_agent() tool
- Agent descriptions for capability understanding
- Proper tool assignments for each specialist
- Entry point clearly defined (trace_specialist)
- Specialized agents with complementary skills
- **CRITICAL**: Each agent has explicit termination conditions to prevent infinite loops

### 3. Refactored Swarm Orchestrator (`src/promptrca/core/swarm_orchestrator.py`)

**Purpose:** Focus solely on orchestration logic, resource discovery, result processing, and cross-account AWS client management.

**Key Responsibilities:**
- Initialize swarm with agents from swarm_agents module
- Parse investigation inputs including cross-account credentials
- Create AWS client with proper role ARN and external ID for cross-account access
- Pass AWS client through invocation_state to all specialist tools
- Discover AWS resources from traces using correct credentials
- Execute swarm investigation with proper AWS context
- Parse results into investigation reports

**Removed Responsibilities:**
- Tool implementations (moved to swarm_tools.py)
- Agent definitions (moved to swarm_agents.py)
- Placeholder AWS API calls (use real tools)

### 4. Integration with Existing Specialists

**Specialist Usage Pattern:**
```python
# In swarm_tools.py
@tool(context=True)
def lambda_specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> str:
    # Parse inputs
    resource = json.loads(resource_data)
    context_data = json.loads(investigation_context)
    
    # Get AWS client with proper cross-account credentials from invocation state
    aws_client = tool_context.invocation_state.get('aws_client')
    if not aws_client:
        raise AWSClientContextError("AWS client not found in invocation state")
    
    # Set AWS client context for tools to use
    set_aws_client(aws_client)
    
    # Create investigation context
    context = InvestigationContext(
        trace_ids=context_data.get('trace_ids', []),
        region=context_data.get('region'),
        parsed_inputs=context_data.get('parsed_inputs')
    )
    
    # Use existing specialist (which will use AWS tools with correct credentials)
    specialist = LambdaSpecialist()
    facts = await specialist.analyze(resource, context)
    
    # Format results
    return format_specialist_results('lambda', resource.get('name'), facts)
```

**Specialist Enhancement:**
- Ensure all specialists use existing AWS tools from tools/ directory
- Add missing specialist implementations for IAM, S3, SQS, SNS using existing tools
- Maintain consistent error handling and fact formatting

## Cross-Account Access Handling

### AWS Client Creation and Management

**Orchestrator Responsibility (Following Strands Best Practices):**
```python
# In SwarmOrchestrator.investigate()
async def investigate(
    self,
    inputs: Dict[str, Any],
    region: str = None,
    assume_role_arn: Optional[str] = None,
    external_id: Optional[str] = None
) -> InvestigationReport:
    # Create AWS client with cross-account credentials
    aws_client = AWSClient(
        region=region or self.region,
        role_arn=assume_role_arn,  # For cross-account access
        external_id=external_id    # For additional security
    )
    
    # Set in context for specialists to use
    set_aws_client(aws_client)
    
    # Create swarm with proper configuration following Strands best practices
    swarm = Swarm(
        agents=create_swarm_agents(),
        entry_point=trace_agent,  # Explicit entry point
        max_handoffs=12,          # Allow sufficient handoffs for investigation
        max_iterations=15,        # Allow multiple specialist interactions
        execution_timeout=450.0,  # 7.5 minutes for complete investigation
        node_timeout=60.0,        # 1 minute per agent
        repetitive_handoff_detection_window=8,  # Prevent ping-pong behavior
        repetitive_handoff_min_unique_agents=3
    )
    
    # Execute swarm with proper invocation_state following Strands patterns
    swarm_result = swarm(
        investigation_prompt,
        invocation_state={
            # Shared state for all agents (not visible to LLM)
            "aws_client": aws_client,  # Critical for cross-account access
            "resources": resources,
            "investigation_context": investigation_context,
            "region": region,
            "trace_ids": parsed_inputs.trace_ids,
            # Configuration that shouldn't appear in prompts
            "debug_mode": os.getenv('DEBUG_MODE', False),
            "investigation_id": investigation_id
        }
    )
```

**Tool Access Pattern (Following Strands Best Practices):**
```python
@tool(context=True)
def specialist_tool(resource_data: str, investigation_context: str, tool_context: ToolContext) -> dict:
    """Specialist tool following Strands ToolResult format and best practices."""
    try:
        # Get AWS client with correct cross-account credentials from invocation_state
        aws_client = tool_context.invocation_state.get('aws_client')
        if not aws_client:
            return {
                "status": "error",
                "content": [{"text": "AWS client with cross-account credentials not found in invocation state"}]
            }
        
        # Ensure context is set for AWS tools
        set_aws_client(aws_client)
        
        # Parse inputs with proper error handling
        resource = json.loads(resource_data)
        context_data = json.loads(investigation_context)
        
        # Create investigation context
        context = InvestigationContext(
            trace_ids=context_data.get('trace_ids', []),
            region=context_data.get('region'),
            parsed_inputs=context_data.get('parsed_inputs')
        )
        
        # Use existing specialist (which will use AWS tools with correct credentials)
        specialist = SpecialistClass()
        facts = await specialist.analyze(resource, context)
        
        # Return proper ToolResult format
        return {
            "status": "success",
            "content": [
                {"json": {
                    "specialist_type": "specialist_name",
                    "resource_name": resource.get('name', 'unknown'),
                    "facts": [fact.to_dict() for fact in facts],
                    "analysis_summary": f"Analyzed {len(facts)} facts"
                }}
            ]
        }
        
    except Exception as e:
        # Return structured error response
        return {
            "status": "error", 
            "content": [{"text": f"Specialist analysis failed: {str(e)}"}]
        }
```

### Cross-Account Security Validation

**Pre-Investigation Checks:**
- Validate assume_role_arn format if provided
- Validate external_id format if provided  
- Test role assumption before starting investigation
- Handle AssumeRole failures with clear error messages
- Log cross-account access attempts for security auditing

**Error Handling:**
- AccessDenied during role assumption → Clear error about role trust policy
- Invalid external_id → Clear error about external ID mismatch
- Role doesn't exist → Clear error about role ARN
- Insufficient permissions → Clear error about role permissions

## Data Models

### Tool Response Format
```python
class SpecialistResult(TypedDict):
    specialist_type: str
    resource_name: str
    facts: List[Dict[str, Any]]
    analysis_summary: str

class SpecialistErrorResult(TypedDict):
    specialist_type: str
    error: str
    error_type: str
    facts: List[Any]  # Empty for errors
```

### Investigation Context
```python
@dataclass
class InvestigationContext:
    trace_ids: List[str]
    region: str
    parsed_inputs: Any
    original_input: Optional[str] = None
    investigation_id: Optional[str] = None
    # Cross-account access parameters
    assume_role_arn: Optional[str] = None
    external_id: Optional[str] = None
```

## Error Handling

### AWS API Error Handling
- Use existing error handling patterns from AWS tools
- Return structured error information with AWS error codes
- Maintain error context for debugging
- Handle permission errors gracefully

### Specialist Error Handling
- Catch specialist analysis failures
- Return meaningful error messages
- Log errors for debugging
- Continue investigation with partial results when possible

## Testing Strategy

### Unit Tests
- Test each specialist tool wrapper independently
- Mock specialist classes to test tool logic
- Verify error handling for various failure scenarios
- Test result formatting and JSON serialization

### Integration Tests
- Test specialist tools with real AWS API calls (using test resources)
- Verify swarm orchestration with refactored components
- Test end-to-end investigation workflows
- Validate backward compatibility with existing interfaces

### Migration Tests
- Compare results before and after refactoring
- Ensure no regression in investigation quality
- Verify all existing functionality is preserved
- Test with known investigation scenarios

## Migration Strategy

### Phase 1: Create New Components
1. Create `swarm_tools.py` with real specialist tool implementations
2. Create `swarm_agents.py` with agent definitions
3. Add missing specialist implementations (IAM, S3, SQS, SNS)

### Phase 2: Refactor Orchestrator
1. Remove tool implementations from `swarm_orchestrator.py`
2. Import tools from `swarm_tools.py`
3. Import agents from `swarm_agents.py`
4. Reduce orchestrator to core logic only

### Phase 3: Testing and Validation
1. Run comprehensive tests to ensure functionality
2. Compare investigation results with original implementation
3. Fix any issues or regressions
4. Update documentation

### Phase 4: Cleanup
1. Remove placeholder tool implementations
2. Remove duplicate code
3. Clean up imports and dependencies
4. Final testing and validation

## Performance Considerations

### Reduced Memory Usage
- Smaller orchestrator file loads faster
- Modular imports reduce memory footprint
- Specialist classes loaded on demand

### Improved Maintainability
- Focused files are easier to understand and modify
- Clear separation of concerns
- Easier to add new specialists or modify existing ones

### Better Error Isolation
- Errors in one specialist don't affect others
- Clearer error messages and debugging
- Easier to identify and fix issues

## Security Considerations

### AWS Credentials and Cross-Account Access
- Use existing AWS client context management with proper role assumption
- Ensure all specialist tools receive AWS client with correct cross-account credentials
- Pass assume_role_arn and external_id from investigation inputs to AWS client creation
- Maintain AWS client in invocation_state for tools to access
- Ensure proper credential handling in all tools for multi-account investigations
- Validate role assumption and external ID before starting investigation
- Handle cross-account permission errors gracefully with clear error messages

### Error Information
- Avoid exposing sensitive information in error messages
- Log detailed errors securely
- Return sanitized error information to users

## Strands Best Practices Implementation

### Swarm Pattern Best Practices
- **Specialized agents with descriptive names**: Each agent has a clear role (trace_specialist, lambda_specialist, etc.)
- **Proper entry point definition**: trace_specialist serves as the investigation coordinator
- **Appropriate timeout configuration**: Balanced timeouts for investigation complexity
- **Repetitive handoff detection**: Prevents ping-pong behavior between agents
- **Diverse expertise**: Complementary skills across all specialist agents

### Tool Implementation Best Practices
- **ToolContext usage**: All tools use `@tool(context=True)` for invocation_state access
- **Proper ToolResult format**: Return structured dictionaries with status and content
- **Invocation state for configuration**: AWS clients and shared context via invocation_state
- **Structured error responses**: Consistent error format with descriptive messages
- **Async support**: Tools support async operations for AWS API calls

### Multi-Agent Coordination Best Practices
- **Shared context through invocation_state**: AWS clients and investigation context shared across agents
- **Clear handoff instructions**: Agents know when and how to hand off to specialists
- **Autonomous collaboration**: Agents decide investigation flow based on findings
- **Collective intelligence**: Shared working memory enables comprehensive analysis

## Investigation Flow Control and Cost Management

### Clear Investigation Phases
The swarm follows a structured investigation flow to prevent infinite loops and control costs:

```
Phase 1: TRACE ANALYSIS (Entry Point)
├── trace_specialist analyzes X-Ray traces
├── Identifies services involved in the issue
├── Determines investigation priority
└── MUST hand off to appropriate service specialists

Phase 2: SERVICE ANALYSIS (Parallel/Sequential)
├── lambda_specialist: Function config, logs, metrics, failures
├── apigateway_specialist: Integration config, IAM, execution logs
├── stepfunctions_specialist: Execution details, state failures
├── Other specialists as needed (IAM, S3, SQS, SNS)
└── Each specialist MUST hand off to hypothesis_generator when complete

Phase 3: HYPOTHESIS GENERATION (Synthesis)
├── hypothesis_generator collects all specialist findings
├── Generates 2-5 evidence-based hypotheses
├── Assigns confidence scores
└── MUST hand off to root_cause_analyzer

Phase 4: ROOT CAUSE ANALYSIS (Terminal)
├── root_cause_analyzer evaluates hypotheses
├── Identifies most probable root cause
├── Provides actionable recommendations
└── TERMINATES investigation (no further handoffs)
```

### Cost Control Mechanisms

**Swarm Configuration for Cost Control:**
```python
swarm = Swarm(
    agents=create_swarm_agents(),
    entry_point=trace_agent,
    max_handoffs=12,          # Strict limit: 1 trace → 6 specialists → 1 hypothesis → 1 root_cause = ~9 handoffs
    max_iterations=15,        # Allow some back-and-forth but prevent runaway
    execution_timeout=450.0,  # 7.5 minutes maximum (cost ceiling)
    node_timeout=60.0,        # 1 minute per agent (prevent stuck agents)
    repetitive_handoff_detection_window=8,  # Detect ping-pong behavior
    repetitive_handoff_min_unique_agents=3  # Require progress through different agents
)
```

**Agent Prompt Constraints:**
- **trace_specialist**: MUST hand off after trace analysis, never do detailed service analysis
- **Service specialists**: MUST hand off to hypothesis_generator when analysis complete, never to other service specialists
- **hypothesis_generator**: MUST hand off to root_cause_analyzer, never back to specialists
- **root_cause_analyzer**: TERMINAL agent, NEVER hands off to anyone

**Investigation Termination Rules:**
1. **Success termination**: root_cause_analyzer provides final analysis
2. **Timeout termination**: execution_timeout or node_timeout exceeded
3. **Loop detection**: repetitive handoff detection triggers termination
4. **Max handoffs**: hard limit prevents runaway investigations
5. **Error termination**: Critical errors stop investigation with partial results

### Investigation Progress Tracking

**Progress Indicators:**
```python
# Track investigation phases
investigation_phases = {
    "trace_analysis": False,
    "service_analysis": {},  # Track which services analyzed
    "hypothesis_generation": False,
    "root_cause_analysis": False
}

# Monitor handoff patterns
handoff_history = []  # Track agent transitions
unique_agents_used = set()  # Ensure diverse expertise
```

**Early Termination Conditions:**
- If trace analysis finds no issues → Early termination with "no issues found"
- If all discovered services analyzed → Force handoff to hypothesis_generator
- If hypothesis_generator runs twice → Force handoff to root_cause_analyzer
- If root_cause_analyzer runs → Investigation complete

### Cost Estimation and Monitoring

**Pre-Investigation Cost Estimation:**
- Estimate tokens based on discovered resources
- Warn user if investigation likely to exceed cost thresholds
- Provide option to limit scope (e.g., analyze only failed services)

**Real-Time Cost Monitoring:**
- Track token usage during investigation
- Implement circuit breaker if costs exceed thresholds
- Provide cost updates in investigation progress

### Performance and Reliability
- **Reduced memory usage**: Smaller orchestrator file loads faster, modular imports
- **Improved maintainability**: Focused files with clear separation of concerns
- **Better error isolation**: Errors in one specialist don't affect others
- **Safety mechanisms**: Timeouts, handoff limits, and repetitive behavior detection