#!/usr/bin/env python3
"""
Agent Retry Utilities for PromptRCA

Provides retry mechanisms for Strands agent invocations using tenacity.
"""

from typing import Any, Callable, Optional, Tuple
from strands import Agent
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryError
)
from ..utils import get_logger

logger = get_logger(__name__)

# Default retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_WAIT = 1.0
DEFAULT_MAX_WAIT = 60.0
DEFAULT_RETRYABLE_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    ValueError,
    RuntimeError
)


def create_retry_decorator(
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_wait: float = DEFAULT_INITIAL_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
    retryable_exceptions: Tuple[type, ...] = DEFAULT_RETRYABLE_EXCEPTIONS
) -> Callable:
    """
    Create a retry decorator for agent invocations.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        retryable_exceptions: Tuple of exception types to retry on
    
    Returns:
        Decorator function
    """
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=initial_wait, min=initial_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=before_sleep_log(logger, logger.level),
        after=after_log(logger, logger.level),
        reraise=True
    )
    def _retry_wrapper(func: Callable, *args, **kwargs):
        """Wrapper that retries function invocation."""
        return func(*args, **kwargs)
    
    return _retry_wrapper


def invoke_agent_with_retry(
    agent: Agent,
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_wait: float = DEFAULT_INITIAL_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
    retryable_exceptions: Tuple[type, ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    **kwargs
) -> Any:
    """
    Invoke a Strands agent with automatic retry on transient errors.
    
    Args:
        agent: Strands Agent instance
        prompt: Prompt to send to agent
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        retryable_exceptions: Tuple of exception types to retry on
        **kwargs: Additional arguments to pass to agent
    
    Returns:
        Agent result
    
    Raises:
        Exception: If all retries are exhausted
    """
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=initial_wait, min=initial_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=before_sleep_log(logger, logger.level),
        after=after_log(logger, logger.level),
        reraise=True
    )
    def _invoke():
        """Inner function that invokes the agent."""
        agent_name = getattr(agent, 'name', 'unknown')
        logger.debug(f"Invoking agent '{agent_name}' with retry support")
        return agent(prompt, **kwargs)
    
    try:
        return _invoke()
    except RetryError as e:
        logger.error(f"Agent invocation failed after {max_retries} retries: {e}")
        raise e.last_attempt.exception() from e


async def invoke_agent_async_with_retry(
    agent: Agent,
    prompt: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_wait: float = DEFAULT_INITIAL_WAIT,
    max_wait: float = DEFAULT_MAX_WAIT,
    retryable_exceptions: Tuple[type, ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    **kwargs
) -> Any:
    """
    Invoke a Strands agent asynchronously with automatic retry on transient errors.
    
    Args:
        agent: Strands Agent instance
        prompt: Prompt to send to agent
        max_retries: Maximum number of retry attempts
        initial_wait: Initial wait time in seconds
        max_wait: Maximum wait time in seconds
        retryable_exceptions: Tuple of exception types to retry on
        **kwargs: Additional arguments to pass to agent
    
    Returns:
        Agent result
    
    Raises:
        Exception: If all retries are exhausted
    """
    import asyncio
    
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=initial_wait, min=initial_wait, max=max_wait),
        retry=retry_if_exception_type(retryable_exceptions),
        before_sleep=before_sleep_log(logger, logger.level),
        after=after_log(logger, logger.level),
        reraise=True
    )
    async def _invoke_async():
        """Inner function that invokes the agent asynchronously."""
        agent_name = getattr(agent, 'name', 'unknown')
        logger.debug(f"Invoking agent '{agent_name}' asynchronously with retry support")
        return await agent.invoke_async(prompt, **kwargs)
    
    try:
        return await _invoke_async()
    except RetryError as e:
        logger.error(f"Agent async invocation failed after {max_retries} retries: {e}")
        raise e.last_attempt.exception() from e

