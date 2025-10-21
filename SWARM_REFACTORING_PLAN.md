# Swarm Orchestrator Refactoring Plan

## Code Improvements for Maintainability

### 1. **Extract Duplicate Code into Helper Functions**

**Issue**: The specialist tools (lambda, apigateway, stepfunctions) have nearly identical code structure with only minor differences.

**Solution**: Create a generic `_create_specialist_tool` helper function.

```python
def _extract_resource_from_data(resource_data_parsed: Any, resource_type: str, context_data: dict) -> dict:
    """Extract a specific resource type from parsed data or create placeholder."""
    if isinstance(resource_data_parsed, list):
        resources = [r for r in resource_data_parsed if r.get('type') == resource_type]
        if resources:
            return resources[0]
        # No resources found, create placeholder
        return {
            'type': resource_type,
            'name': 'unknown',
            'id': 'unknown',
            'region': context_data.get('region', 'us-east-1')
        }
    else:
        return resource_data_parsed

def _run_specialist_analysis(specialist, resource: dict, context: InvestigationContext) -> List[Fact]:
    """Run specialist analysis in a new event loop (sync wrapper for async)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(specialist.analyze(resource, context))
    finally:
        loop.close()

def _format_specialist_results(specialist_type: str, resource_name: str, facts: List[Fact]) -> dict:
    """Format specialist analysis results as JSON-serializable dict."""
    return {
        "specialist_type": specialist_type,
        "resource_name": resource_name,
        "facts": [
            {
                "source": fact.source,
                "content": fact.content,
                "confidence": fact.confidence,
                "metadata": fact.metadata
            }
            for fact in facts
        ],
        "analysis_summary": f"Analyzed {specialist_type} {resource_name} - found {len(facts)} facts"
    }
```

### 2. **Consolidate Specialist Tools**

**Issue**: Four nearly identical tool functions with duplicated logic.

**Solution**: Use a factory pattern or decorator to generate specialist tools.

```python
def create_specialist_tool(specialist_class, specialist_type: str):
    """Factory function to create specialist tools with consistent behavior."""
    
    @tool
    def specialist_tool(resource_data: str, investigation_context: str) -> str:
        f"""
        Analyze {specialist_type} resources for configuration issues and errors.
        
        Args:
            resource_data: JSON string containing resource information
            investigation_context: JSON string with trace IDs, region, and context
        
        Returns:
            JSON string with analysis results
        """
        try:
            resource_data_parsed = json.loads(resource_data)
            context_data = json.loads(investigation_context)
            
            # Extract resource
            resource = _extract_resource_from_data(
                resource_data_parsed, specialist_type, context_data
            )
            
            # Create context
            context = InvestigationContext(
                trace_ids=context_data.get('trace_ids', []),
                region=context_data.get('region', 'us-east-1'),
                parsed_inputs=context_data.get('parsed_inputs')
            )
            
            # Run analysis
            specialist = specialist_class()
            facts = _run_specialist_analysis(specialist, resource, context)
            
            # Format results
            results = _format_specialist_results(
                specialist_type, resource.get('name', 'unknown'), facts
            )
            
            return json.dumps(results, indent=2)
            
        except Exception as e:
            logger.error(f"{specialist_type.title()} specialist tool failed: {e}")
            return json.dumps({
                "specialist_type": specialist_type,
                "error": str(e),
                "facts": []
            })
    
    return specialist_tool

# Create tools using factory
lambda_specialist_tool = create_specialist_tool(LambdaSpecialist, "lambda")
apigateway_specialist_tool = create_specialist_tool(APIGatewaySpecialist, "apigateway")
stepfunctions_specialist_tool = create_specialist_tool(StepFunctionsSpecialist, "stepfunctions")
```

### 3. **Extract Configuration Constants**

**Issue**: Magic numbers and strings scattered throughout the code.

**Solution**: Define constants at module level.

```python
# Swarm configuration defaults
DEFAULT_MAX_HANDOFFS = 5
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_EXECUTION_TIMEOUT = 90.0
DEFAULT_NODE_TIMEOUT = 30.0

# Agent prompt templates
TRACE_AGENT_PROMPT = """You are a trace analysis specialist. Be CONCISE and FOCUSED.

Your job:
1. Use trace_specialist_tool to analyze X-Ray traces
2. Identify errors and service interactions
3. Hand off to relevant specialists with specific findings
4. Provide brief, actionable insights

Be direct and avoid lengthy explanations."""

LAMBDA_AGENT_PROMPT = """You are a Lambda specialist. Be CONCISE.

Analyze Lambda functions using lambda_specialist_tool. Focus on:
- Configuration and IAM issues
- Performance and timeout problems
- Integration errors

Provide brief findings. Hand off only when necessary."""
```

### 4. **Improve Error Handling**

**Issue**: Generic exception handling loses context.

**Solution**: Create specific exception types and better error messages.

```python
class SpecialistToolError(Exception):
    """Base exception for specialist tool errors."""
    pass

class ResourceDataError(SpecialistToolError):
    """Error parsing or validating resource data."""
    pass

class SpecialistAnalysisError(SpecialistToolError):
    """Error during specialist analysis execution."""
    pass

# Usage
try:
    resource_data_parsed = json.loads(resource_data)
except json.JSONDecodeError as e:
    raise ResourceDataError(f"Invalid JSON in resource_data: {e}")
```

### 5. **Add Type Hints and Documentation**

**Issue**: Some functions lack clear type hints and docstrings.

**Solution**: Add comprehensive type hints and docstrings.

```python
from typing import TypedDict, Literal

class SpecialistResult(TypedDict):
    """Type definition for specialist tool results."""
    specialist_type: str
    resource_name: str
    facts: List[Dict[str, Any]]
    analysis_summary: str

def _extract_resource_from_data(
    resource_data_parsed: Union[Dict[str, Any], List[Dict[str, Any]]],
    resource_type: Literal["lambda", "apigateway", "stepfunctions"],
    context_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Extract a specific resource type from parsed data.
    
    Args:
        resource_data_parsed: Parsed resource data (single dict or list)
        resource_type: Type of resource to extract
        context_data: Investigation context containing region and other metadata
    
    Returns:
        Resource dictionary, either extracted or placeholder
    
    Examples:
        >>> data = [{"type": "lambda", "name": "my-func"}]
        >>> _extract_resource_from_data(data, "lambda", {"region": "us-east-1"})
        {"type": "lambda", "name": "my-func"}
    """
```

### 6. **Separate Concerns**

**Issue**: SwarmOrchestrator class mixes orchestration, agent creation, and tool definitions.

**Solution**: Split into separate modules.

```
src/promptrca/core/swarm/
├── __init__.py
├── orchestrator.py       # Main SwarmOrchestrator class
├── tools.py             # Specialist tool definitions
├── agents.py            # Agent creation functions
├── helpers.py           # Shared helper functions
└── config.py            # Configuration constants
```

### 7. **Improve Logging**

**Issue**: Inconsistent logging levels and messages.

**Solution**: Standardize logging with structured messages.

```python
logger.debug(
    "Extracting resource from data",
    extra={
        "resource_type": resource_type,
        "data_type": type(resource_data_parsed).__name__,
        "has_resources": bool(resources) if isinstance(resource_data_parsed, list) else True
    }
)

logger.info(
    "Specialist analysis completed",
    extra={
        "specialist_type": specialist_type,
        "resource_name": resource_name,
        "facts_found": len(facts),
        "duration_ms": duration
    }
)
```

### 8. **Add Validation Functions**

**Issue**: Implicit assumptions about data structure.

**Solution**: Explicit validation functions.

```python
def validate_resource_data(data: Any) -> None:
    """Validate resource data structure."""
    if not isinstance(data, (dict, list)):
        raise ResourceDataError(f"Expected dict or list, got {type(data)}")
    
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                raise ResourceDataError(f"List items must be dicts, got {type(item)}")
            if 'type' not in item:
                raise ResourceDataError("Resource items must have 'type' field")

def validate_investigation_context(context: Any) -> None:
    """Validate investigation context structure."""
    if not isinstance(context, dict):
        raise ResourceDataError(f"Context must be dict, got {type(context)}")
    
    required_fields = ['region']
    for field in required_fields:
        if field not in context:
            raise ResourceDataError(f"Context missing required field: {field}")
```

## Benefits

1. **Reduced Duplication**: ~200 lines of duplicated code → ~50 lines of shared helpers
2. **Easier Testing**: Helper functions can be unit tested independently
3. **Better Error Messages**: Specific exceptions with context
4. **Clearer Intent**: Named constants and helper functions
5. **Easier Maintenance**: Changes to specialist logic only need to happen once
6. **Better Documentation**: Type hints and docstrings make code self-documenting
7. **Separation of Concerns**: Each module has a single responsibility

## Implementation Priority

1. **High Priority** (Do first):
   - Extract duplicate code into helpers
   - Add configuration constants
   - Improve error handling

2. **Medium Priority** (Do next):
   - Add comprehensive type hints
   - Improve logging
   - Add validation functions

3. **Low Priority** (Nice to have):
   - Separate into multiple modules
   - Create factory pattern for tools

This refactoring maintains all existing functionality while making the code significantly more maintainable.