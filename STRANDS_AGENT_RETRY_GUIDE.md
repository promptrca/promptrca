# Strands Agent Retry Guide

## Overview

Strands Agents does **not have built-in retry mechanisms** for agent failures. However, you can implement retry logic using several approaches:

1. **Hooks** - Intercept errors and retry at the hook level
2. **Wrapper Functions** - Wrap agent invocations with retry decorators
3. **Multi-Agent Hooks** - Handle retries at the orchestrator level
4. **Manual Retry Logic** - Implement custom retry in your code

## Approach 1: Using Hooks for Retry

The most flexible approach is to use Strands hooks to intercept errors and implement retry logic.

### Single Agent Retry Hook

```python
from strands import Agent
from strands.hooks import HookProvider, HookRegistry, AfterInvocationEvent, BeforeInvocationEvent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import asyncio
from typing import Any

class AgentRetryHook(HookProvider):
    """Hook that retries agent invocations on failure."""
    
    def __init__(self, max_retries: int = 3, retryable_exceptions: tuple = (Exception,)):
        """
        Initialize retry hook.
        
        Args:
            max_retries: Maximum number of retry attempts
            retryable_exceptions: Tuple of exception types to retry on
        """
        self.max_retries = max_retries
        self.retryable_exceptions = retryable_exceptions
        self.current_attempt = 0
        self.original_request = None
        self.original_kwargs = None
    
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self._store_request)
        registry.add_callback(AfterInvocationEvent, self._handle_failure)
    
    def _store_request(self, event: BeforeInvocationEvent) -> None:
        """Store the original request for potential retry."""
        # Note: This is a simplified approach - actual implementation would need
        # to store the full invocation context
        pass
    
    def _handle_failure(self, event: AfterInvocationEvent) -> None:
        """Handle failures and trigger retries if needed."""
        # Note: AfterInvocationEvent doesn't directly expose exceptions
        # You'd need to check event.result or use a different approach
        pass
```

**Limitation**: Hooks don't directly expose exceptions, so this approach is limited.

## Approach 2: Wrapper Function with Retry Decorator (Recommended)

The most practical approach is to wrap agent invocations with a retry decorator:

```python
from strands import Agent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)
from typing import Any, Callable
import logging

logger = logging.getLogger(__name__)

def retry_agent_invocation(
    max_retries: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator to retry agent invocations on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        retryable_exceptions: Tuple of exception types to retry on
    """
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=initial_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        reraise=True
    )
    def _retry_wrapper(agent: Agent, *args, **kwargs):
        """Wrapper that retries agent invocation."""
        try:
            return agent(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Agent invocation failed (attempt {_retry_wrapper.retry.statistics['attempt_number']}): {e}")
            raise
    
    return _retry_wrapper

# Usage
agent = Agent(tools=[...])

# Retry on any exception, up to 3 times
retry_func = retry_agent_invocation(max_retries=3)
result = retry_func(agent, "Your prompt here")

# Or use as a decorator for async functions
@retry_agent_invocation(max_retries=3, retryable_exceptions=(TimeoutError, ConnectionError))
async def invoke_agent(agent: Agent, prompt: str):
    return await agent.invoke_async(prompt)
```

## Approach 3: Manual Retry Logic

For more control, implement manual retry logic:

```python
from strands import Agent
from typing import Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

def invoke_with_retry(
    agent: Agent,
    prompt: str,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Invoke agent with retry logic.
    
    Args:
        agent: Strands Agent instance
        prompt: Prompt to send to agent
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for exponential backoff
        retryable_exceptions: Tuple of exception types to retry on
        **kwargs: Additional arguments to pass to agent
    
    Returns:
        Agent result
    
    Raises:
        Exception: If all retries are exhausted
    """
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Agent invocation attempt {attempt + 1}/{max_retries}")
            result = agent(prompt, **kwargs)
            logger.info(f"Agent invocation succeeded on attempt {attempt + 1}")
            return result
            
        except retryable_exceptions as e:
            last_exception = e
            logger.warning(
                f"Agent invocation failed on attempt {attempt + 1}/{max_retries}: {e}"
            )
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} retry attempts exhausted")
                raise
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise Exception("Agent invocation failed for unknown reason")

# Usage
agent = Agent(tools=[...])
result = invoke_with_retry(
    agent,
    "Your prompt here",
    max_retries=3,
    retryable_exceptions=(TimeoutError, ConnectionError, ValueError)
)
```

## Approach 4: Multi-Agent Orchestrator Retry

For multi-agent patterns (Graph, Swarm, Workflow), implement retry at the orchestrator level:

```python
from strands.multiagent import Graph, Swarm
from strands.hooks import HookProvider, HookRegistry
from strands.hooks.multiagent import AfterNodeCallEvent, BeforeNodeCallEvent
from typing import Any
import logging

logger = logging.getLogger(__name__)

class NodeRetryHook(HookProvider):
    """Hook that retries node execution on failure in multi-agent orchestrators."""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.node_attempts = {}
    
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeNodeCallEvent, self._track_attempt)
        registry.add_callback(AfterNodeCallEvent, self._check_for_retry)
    
    def _track_attempt(self, event: BeforeNodeCallEvent) -> None:
        """Track attempt number for each node."""
        node_id = event.node_id
        if node_id not in self.node_attempts:
            self.node_attempts[node_id] = 0
        self.node_attempts[node_id] += 1
        logger.info(f"Node {node_id} attempt {self.node_attempts[node_id]}")
    
    def _check_for_retry(self, event: AfterNodeCallEvent) -> None:
        """Check if node needs retry based on result."""
        node_id = event.node_id
        # Check if result indicates failure
        # Note: Actual implementation would need to inspect event.result
        # and determine if retry is needed
        pass

# Usage with Graph
graph = Graph(
    agents={"agent1": agent1, "agent2": agent2},
    hooks=[NodeRetryHook(max_retries=3)]
)
```

## Approach 5: Async Retry with asyncio

For async agent invocations:

```python
import asyncio
from strands import Agent
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

async def invoke_async_with_retry(
    agent: Agent,
    prompt: str,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """Async version of invoke_with_retry."""
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Agent async invocation attempt {attempt + 1}/{max_retries}")
            result = await agent.invoke_async(prompt, **kwargs)
            logger.info(f"Agent async invocation succeeded on attempt {attempt + 1}")
            return result
            
        except retryable_exceptions as e:
            last_exception = e
            logger.warning(
                f"Agent async invocation failed on attempt {attempt + 1}/{max_retries}: {e}"
            )
            
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay:.2f} seconds...")
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                logger.error(f"All {max_retries} retry attempts exhausted")
                raise
    
    if last_exception:
        raise last_exception
    raise Exception("Agent async invocation failed for unknown reason")

# Usage
agent = Agent(tools=[...])
result = await invoke_async_with_retry(
    agent,
    "Your prompt here",
    max_retries=3
)
```

## Best Practices

1. **Selective Retrying**: Only retry on specific exception types (e.g., `TimeoutError`, `ConnectionError`), not all exceptions
2. **Exponential Backoff**: Use exponential backoff to avoid overwhelming the system
3. **Max Retries**: Set reasonable limits (typically 3-5 attempts)
4. **Logging**: Log all retry attempts for debugging
5. **Timeout Handling**: Consider timeout errors separately from other errors
6. **Circuit Breaker**: For production, consider implementing a circuit breaker pattern

## Example: Complete Retry Implementation

```python
from strands import Agent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import logging

logger = logging.getLogger(__name__)

# Configure retry decorator
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    retry=retry_if_exception_type((TimeoutError, ConnectionError, ValueError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.INFO),
    reraise=True
)
def invoke_agent_with_retry(agent: Agent, prompt: str, **kwargs):
    """Invoke agent with automatic retry on transient errors."""
    logger.info(f"Invoking agent with prompt: {prompt[:100]}...")
    return agent(prompt, **kwargs)

# Usage
agent = Agent(tools=[...])
try:
    result = invoke_agent_with_retry(agent, "Your prompt here")
except Exception as e:
    logger.error(f"Agent invocation failed after all retries: {e}")
    # Handle final failure
```

## References

- [Strands Hooks Documentation](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/)
- [Strands Multi-Agent Hooks](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/experimental/multi-agent-hooks/)
- [Tenacity Retry Library](https://tenacity.readthedocs.io/)

