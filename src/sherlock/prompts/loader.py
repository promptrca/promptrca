#!/usr/bin/env python3
"""
Sherlock Core - Prompt Loader
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

Contact: christiangenn99+sherlock@gmail.com

Prompt loading utilities with caching and template variable substitution.
"""

import os
from typing import Dict, Any, Optional
from functools import lru_cache
from ..utils import get_logger

logger = get_logger(__name__)

# Cache for loaded prompts
_prompt_cache: Dict[str, str] = {}

def _get_prompts_dir() -> str:
    """Get the prompts directory path."""
    return os.path.dirname(os.path.abspath(__file__))

def load_prompt(prompt_path: str) -> str:
    """
    Load a prompt file from the prompts directory.
    
    Args:
        prompt_path: Path to prompt file relative to prompts directory (e.g., "specialized/lambda_agent")
        
    Returns:
        The prompt content as a string
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
        IOError: If there's an error reading the file
    """
    # Add .prompt extension if not present
    if not prompt_path.endswith('.prompt'):
        prompt_path += '.prompt'
    
    # Check cache first
    if prompt_path in _prompt_cache:
        return _prompt_cache[prompt_path]
    
    # Build full file path
    prompts_dir = _get_prompts_dir()
    full_path = os.path.join(prompts_dir, prompt_path)
    
    # Check if file exists
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Cache the content
        _prompt_cache[prompt_path] = content
        
        logger.debug(f"Loaded prompt: {prompt_path}")
        return content
        
    except IOError as e:
        logger.error(f"Error reading prompt file {prompt_path}: {e}")
        raise

def load_prompt_with_vars(prompt_path: str, **variables: Any) -> str:
    """
    Load a prompt file and substitute template variables.
    
    Args:
        prompt_path: Path to prompt file relative to prompts directory
        **variables: Template variables to substitute (e.g., function_name="my-function")
        
    Returns:
        The prompt content with variables substituted
        
    Example:
        load_prompt_with_vars("specialized/lambda_agent", function_name="my-function", context="error analysis")
    """
    prompt = load_prompt(prompt_path)
    
    # Simple template variable substitution
    # Replace {variable_name} with the provided value
    for var_name, var_value in variables.items():
        placeholder = f"{{{var_name}}}"
        prompt = prompt.replace(placeholder, str(var_value))
    
    return prompt

def clear_prompt_cache():
    """Clear the prompt cache. Useful for testing or when prompts are updated."""
    global _prompt_cache
    _prompt_cache.clear()
    logger.debug("Prompt cache cleared")

def list_available_prompts() -> list[str]:
    """
    List all available prompt files.
    
    Returns:
        List of prompt file paths (without .prompt extension)
    """
    prompts_dir = _get_prompts_dir()
    prompts = []
    
    for root, dirs, files in os.walk(prompts_dir):
        for file in files:
            if file.endswith('.prompt'):
                # Get relative path from prompts directory
                rel_path = os.path.relpath(os.path.join(root, file), prompts_dir)
                # Remove .prompt extension
                prompt_name = rel_path[:-7]  # Remove '.prompt'
                prompts.append(prompt_name)
    
    return sorted(prompts)
