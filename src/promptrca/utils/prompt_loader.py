#!/usr/bin/env python3
"""
Prompt Loader Utility for PromptRCA

Provides utilities for loading prompts from external files, supporting
both simple text loading and template rendering with variables.

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

import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(prompt_name: str, variables: Optional[Dict[str, Any]] = None, category: Optional[str] = None) -> str:
    """
    Load a prompt from a markdown file.

    Args:
        prompt_name: Name of the prompt file (without extension)
        variables: Optional variables for template substitution
        category: Optional subdirectory ('graph', 'swarm', 'orchestrator')

    Returns:
        The loaded prompt text

    Raises:
        FileNotFoundError: If the prompt file doesn't exist

    Examples:
        >>> load_prompt("trace_specialist", category="swarm")
        >>> load_prompt("input_parser", category="graph")
        >>> load_prompt("lambda_specialist", {"region": "us-east-1"}, category="swarm")
    """
    # If category specified, look in subdirectory
    if category:
        prompt_file = PROMPTS_DIR / category / f"{prompt_name}.md"
    else:
        # Try to find in subdirectories (for backward compatibility)
        for subdir in ['graph', 'specialists']:
            prompt_file = PROMPTS_DIR / subdir / f"{prompt_name}.md"
            if prompt_file.exists():
                break
        else:
            # Fallback to root directory
            prompt_file = PROMPTS_DIR / f"{prompt_name}.md"

    if not prompt_file.exists():
        # Fallback to .txt if .md doesn't exist
        prompt_file = prompt_file.with_suffix('.txt')

    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_name} (searched in {PROMPTS_DIR})")

    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt_text = f.read()
            
        # Simple variable substitution if provided
        if variables:
            prompt_text = prompt_text.format(**variables)
            
        logger.debug(f"Loaded prompt '{prompt_name}' ({len(prompt_text)} chars)")
        return prompt_text
        
    except Exception as e:
        logger.error(f"Failed to load prompt '{prompt_name}': {e}")
        raise


def list_available_prompts() -> Dict[str, list[str]]:
    """
    List all available prompt files organized by category.

    Returns:
        Dictionary mapping categories to lists of prompt names
    """
    if not PROMPTS_DIR.exists():
        return {}

    prompts_by_category = {}

    # Check subdirectories
    for category in ['graph', 'specialists']:
        category_dir = PROMPTS_DIR / category
        if category_dir.exists():
            prompts = []
            for file_path in category_dir.glob("*.md"):
                prompts.append(file_path.stem)
            for file_path in category_dir.glob("*.txt"):
                if file_path.stem not in prompts:
                    prompts.append(file_path.stem)
            prompts_by_category[category] = sorted(prompts)

    # Check root directory for backward compatibility
    root_prompts = []
    for file_path in PROMPTS_DIR.glob("*.md"):
        root_prompts.append(file_path.stem)
    for file_path in PROMPTS_DIR.glob("*.txt"):
        if file_path.stem not in root_prompts:
            root_prompts.append(file_path.stem)
    if root_prompts:
        prompts_by_category['root'] = sorted(root_prompts)

    return prompts_by_category


def validate_prompts() -> Dict[str, bool]:
    """
    Validate that all expected prompt files exist in their correct categories.

    Returns:
        Dictionary mapping prompt names to existence status
    """
    expected_prompts = [
        # Graph node prompts
        "input_parser",
        "hypothesis_generator",

        # Specialist prompts (used in swarm and by specialized agents)
        "trace_specialist",
        "lambda_specialist",
        "apigateway_specialist",
        "stepfunctions_specialist",
        "iam_specialist",
        "s3_specialist",
        "sqs_specialist",
        "sns_specialist",
        "dynamodb_specialist",
        "eventbridge_specialist",
        "vpc_specialist",
        "root_cause_analyzer",
    ]

    results = {}
    for prompt_name in expected_prompts:
        try:
            load_prompt(prompt_name)
            results[prompt_name] = True
        except FileNotFoundError:
            results[prompt_name] = False

    return results


# Template-based prompt loading (for future use)
def load_prompt_template(prompt_name: str, **kwargs) -> str:
    """
    Load a prompt with Jinja2 template rendering (if needed in future).
    
    Args:
        prompt_name: Name of the prompt file
        **kwargs: Template variables
        
    Returns:
        Rendered prompt text
    """
    try:
        # Try to import jinja2 for advanced templating
        from jinja2 import Template
        
        prompt_text = load_prompt(prompt_name)
        template = Template(prompt_text)
        return template.render(**kwargs)
        
    except ImportError:
        # Fallback to simple string formatting
        logger.warning("Jinja2 not available, using simple string formatting")
        return load_prompt(prompt_name, kwargs)