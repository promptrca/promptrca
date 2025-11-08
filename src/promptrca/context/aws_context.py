#!/usr/bin/env python3
"""
PromptRCA Core - AI-powered root cause analysis for AWS infrastructure
Copyright (C) 2025 Christian Gennaro Faraone

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Contact: info@promptrca.com

"""

from contextvars import ContextVar
from typing import Optional

# Use TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..clients import AWSClient

# Per-request context variable for AWS client
# This is async-safe and thread-safe, ensuring proper isolation between concurrent investigations
_aws_client_context: ContextVar[Optional['AWSClient']] = ContextVar('aws_client', default=None)

# Fallback module-level storage for Swarm contexts where contextvars don't propagate
_aws_client_fallback: Optional['AWSClient'] = None


def set_aws_client(client: 'AWSClient') -> None:
    """
    Set the AWS client for the current request context.
    
    This should be called at the beginning of each investigation to establish
    the AWS credentials that all tools will use. The client is stored in b
    context variable that is isolated per async task or thread.
    
    Args:
        client: The AWSClient instance with assumed role credentials
    
    Example:
        aws_client = AWSClient(region='us-east-1', role_arn='arn:aws:iam::...')
        set_aws_client(aws_client)
    """
    _aws_client_context.set(client)


def get_aws_client() -> 'AWSClient':
    """
    Get the AWS client for the current request context.
    
    This is called internally by all AWS tools to retrieve the shared client
    instance. Tools should not receive aws_client as a parameter - instead,
    they call this function to get the client programmatically.
    
    Returns:
        The AWSClient instance for the current investigation
    
    Raises:
        RuntimeError: If no AWS client has been set in the current context.
                     This indicates set_aws_client() was not called before
                     the tool was invoked.
    
    Example:
        aws_client = get_aws_client()
        lambda_client = aws_client.get_client('lambda')
    """
    client = _aws_client_context.get()
    if client is None:
        raise RuntimeError(
            "No AWS client found in context. "
            "Must call set_aws_client() before using AWS tools. "
            "This is a programming error - the investigation orchestrator "
            "should have set the client in context before invoking tools."
        )
    return client


def clear_aws_client() -> None:
    """
    Clear the AWS client from the current request context.
    
    This should be called at the end of each investigation (in a finally block)
    to ensure proper cleanup and prevent context leakage between investigations.
    
    Example:
        try:
            set_aws_client(aws_client)
            # ... run investigation ...
        finally:
            clear_aws_client()
    """
    _aws_client_context.set(None)

