#!/usr/bin/env python3
"""
Sherlock Core - Token Pricing Configuration
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

Token pricing configuration for cost calculation and analysis.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class ModelPricing:
    """Pricing information for a specific model."""
    model_id: str
    input_tokens_per_1k: Decimal
    output_tokens_per_1k: Decimal
    input_tokens_per_1k_batch: Optional[Decimal] = None
    output_tokens_per_1k_batch: Optional[Decimal] = None
    input_tokens_per_1k_cache_write: Optional[Decimal] = None
    input_tokens_per_1k_cache_read: Optional[Decimal] = None
    currency: str = "USD"
    
    def calculate_cost(self, input_tokens: int, output_tokens: int, use_batch: bool = False) -> Decimal:
        """
        Calculate the cost for given token usage.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            use_batch: Whether to use batch pricing (if available)
            
        Returns:
            Total cost in the specified currency
        """
        input_price = self.input_tokens_per_1k_batch if use_batch and self.input_tokens_per_1k_batch else self.input_tokens_per_1k
        output_price = self.output_tokens_per_1k_batch if use_batch and self.output_tokens_per_1k_batch else self.output_tokens_per_1k
        
        input_cost = (Decimal(input_tokens) / 1000) * input_price
        output_cost = (Decimal(output_tokens) / 1000) * output_price
        
        return (input_cost + output_cost).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)


# OpenAI Models Pricing (as of 2025)
OPENAI_PRICING = {
    "openai.gpt-oss-20b-1:0": ModelPricing(
        model_id="openai.gpt-oss-20b-1:0",
        input_tokens_per_1k=Decimal("0.00008"),
        output_tokens_per_1k=Decimal("0.00035"),
        input_tokens_per_1k_batch=Decimal("0.00004"),
        output_tokens_per_1k_batch=Decimal("0.00018")
    ),
    "openai.gpt-oss-120b-1:0": ModelPricing(
        model_id="openai.gpt-oss-120b-1:0",
        input_tokens_per_1k=Decimal("0.00018"),
        output_tokens_per_1k=Decimal("0.0007"),
        input_tokens_per_1k_batch=Decimal("0.00009"),
        output_tokens_per_1k_batch=Decimal("0.00035")
    )
}

# Anthropic Models Pricing (as of 2025)
ANTHROPIC_PRICING = {
    "anthropic.claude-haiku-4-5-20251001-v1:0": ModelPricing(
        model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
        input_tokens_per_1k=Decimal("0.001"),
        output_tokens_per_1k=Decimal("0.005"),
        input_tokens_per_1k_batch=Decimal("0.0005"),
        output_tokens_per_1k_batch=Decimal("0.0025"),
        input_tokens_per_1k_cache_write=Decimal("0.00125"),
        input_tokens_per_1k_cache_read=Decimal("0.0001")
    ),
    "anthropic.claude-sonnet-4-5-20250929-v1:0": ModelPricing(
        model_id="anthropic.claude-sonnet-4-5-20250929-v1:0",
        input_tokens_per_1k=Decimal("0.003"),
        output_tokens_per_1k=Decimal("0.015"),
        input_tokens_per_1k_cache_write=Decimal("0.00375"),
        input_tokens_per_1k_cache_read=Decimal("0.0003")
    ),
    "anthropic.claude-sonnet-4-20250514-v1:0": ModelPricing(
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        input_tokens_per_1k=Decimal("0.003"),
        output_tokens_per_1k=Decimal("0.015"),
        input_tokens_per_1k_cache_write=Decimal("0.00375"),
        input_tokens_per_1k_cache_read=Decimal("0.0003")
    ),
    "anthropic.claude-3-7-sonnet-20250219-v1:0": ModelPricing(
        model_id="anthropic.claude-3-7-sonnet-20250219-v1:0",
        input_tokens_per_1k=Decimal("0.003"),
        output_tokens_per_1k=Decimal("0.015"),
        input_tokens_per_1k_cache_write=Decimal("0.00375"),
        input_tokens_per_1k_cache_read=Decimal("0.0003")
    ),
    "anthropic.claude-3-5-sonnet-20240620-v1:0": ModelPricing(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        input_tokens_per_1k=Decimal("0.003"),
        output_tokens_per_1k=Decimal("0.015"),
        input_tokens_per_1k_cache_write=Decimal("0.00375"),
        input_tokens_per_1k_cache_read=Decimal("0.0003")
    ),
    "anthropic.claude-3-haiku-20240307-v1:0": ModelPricing(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        input_tokens_per_1k=Decimal("0.001"),
        output_tokens_per_1k=Decimal("0.005"),
        input_tokens_per_1k_batch=Decimal("0.0005"),
        output_tokens_per_1k_batch=Decimal("0.0025"),
        input_tokens_per_1k_cache_write=Decimal("0.00125"),
        input_tokens_per_1k_cache_read=Decimal("0.0001")
    )
}

# Default pricing for unknown models (conservative estimate)
DEFAULT_PRICING = ModelPricing(
    model_id="unknown",
    input_tokens_per_1k=Decimal("0.0001"),  # Conservative estimate
    output_tokens_per_1k=Decimal("0.0004"),  # Conservative estimate
)


def get_model_pricing(model_id: str) -> ModelPricing:
    """
    Get pricing information for a specific model.
    
    Args:
        model_id: The model identifier
        
    Returns:
        ModelPricing object for the model, or default pricing if not found
    """
    # Check OpenAI models first
    if model_id in OPENAI_PRICING:
        return OPENAI_PRICING[model_id]
    
    # Check Anthropic models
    if model_id in ANTHROPIC_PRICING:
        return ANTHROPIC_PRICING[model_id]
    
    # Return default pricing for unknown models
    return DEFAULT_PRICING


def calculate_investigation_cost(token_usage: Dict[str, Any], use_batch_pricing: bool = False) -> Dict[str, Any]:
    """
    Calculate the total cost for an investigation based on token usage.
    
    Args:
        token_usage: Token usage data from TokenTracker
        use_batch_pricing: Whether to use batch pricing (if available)
        
    Returns:
        Dictionary with cost breakdown
    """
    if not token_usage:
        return {
            "total_cost": Decimal("0.00"),
            "currency": "USD",
            "by_model": {},
            "by_agent": {},
            "summary": {
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_tokens": 0,
                "total_cost": Decimal("0.00")
            }
        }
    
    total_cost = Decimal("0.00")
    by_model_costs = {}
    by_agent_costs = {}
    
    # Calculate costs by model
    for model_id, usage in token_usage.get("by_model", {}).items():
        pricing = get_model_pricing(model_id)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        model_cost = pricing.calculate_cost(input_tokens, output_tokens, use_batch_pricing)
        by_model_costs[model_id] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": usage.get("total_tokens", 0),
            "cost": float(model_cost),
            "currency": pricing.currency,
            "pricing": {
                "input_per_1k": float(pricing.input_tokens_per_1k),
                "output_per_1k": float(pricing.output_tokens_per_1k),
                "batch_input_per_1k": float(pricing.input_tokens_per_1k_batch) if pricing.input_tokens_per_1k_batch else None,
                "batch_output_per_1k": float(pricing.output_tokens_per_1k_batch) if pricing.output_tokens_per_1k_batch else None,
                "cache_write_input_per_1k": float(pricing.input_tokens_per_1k_cache_write) if pricing.input_tokens_per_1k_cache_write else None,
                "cache_read_input_per_1k": float(pricing.input_tokens_per_1k_cache_read) if pricing.input_tokens_per_1k_cache_read else None
            }
        }
        total_cost += model_cost
    
    # Calculate costs by agent
    for agent_name, usage in token_usage.get("by_agent", {}).items():
        model_id = usage.get("model_id", "unknown")
        pricing = get_model_pricing(model_id)
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        
        agent_cost = pricing.calculate_cost(input_tokens, output_tokens, use_batch_pricing)
        by_agent_costs[agent_name] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": usage.get("total_tokens", 0),
            "cost": float(agent_cost),
            "currency": pricing.currency,
            "model_id": model_id
        }
    
    return {
        "total_cost": float(total_cost),
        "currency": "USD",
        "by_model": by_model_costs,
        "by_agent": by_agent_costs,
        "summary": {
            "total_input_tokens": token_usage.get("total_input_tokens", 0),
            "total_output_tokens": token_usage.get("total_output_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
            "total_cost": float(total_cost),
            "pricing_type": "batch" if use_batch_pricing else "standard"
        }
    }


def format_cost_report(cost_data: Dict[str, Any]) -> str:
    """
    Format cost data into a human-readable report.
    
    Args:
        cost_data: Cost data from calculate_investigation_cost
        
    Returns:
        Formatted cost report string
    """
    summary = cost_data["summary"]
    currency = cost_data["currency"]
    
    report = []
    report.append("💰 Investigation Cost Report")
    report.append("=" * 50)
    report.append(f"Total Cost: ${summary['total_cost']:.6f} {currency}")
    report.append(f"Total Tokens: {summary['total_tokens']:,}")
    report.append(f"  - Input: {summary['total_input_tokens']:,}")
    report.append(f"  - Output: {summary['total_output_tokens']:,}")
    report.append(f"Pricing: {summary['pricing_type']}")
    report.append("")
    
    # By model breakdown
    if cost_data["by_model"]:
        report.append("📊 Cost by Model:")
        for model_id, data in cost_data["by_model"].items():
            report.append(f"  {model_id}:")
            report.append(f"    Cost: ${data['cost']:.6f} {data['currency']}")
            report.append(f"    Tokens: {data['total_tokens']:,} ({data['input_tokens']:,} in, {data['output_tokens']:,} out)")
            report.append(f"    Rate: ${data['pricing']['input_per_1k']:.5f}/{data['pricing']['output_per_1k']:.5f} per 1K tokens")
            if data['pricing']['batch_input_per_1k']:
                report.append(f"    Batch Rate: ${data['pricing']['batch_input_per_1k']:.5f}/{data['pricing']['batch_output_per_1k']:.5f} per 1K tokens")
            if data['pricing']['cache_write_input_per_1k']:
                report.append(f"    Cache Write: ${data['pricing']['cache_write_input_per_1k']:.5f} per 1K tokens")
            if data['pricing']['cache_read_input_per_1k']:
                report.append(f"    Cache Read: ${data['pricing']['cache_read_input_per_1k']:.5f} per 1K tokens")
            report.append("")
    
    # By agent breakdown
    if cost_data["by_agent"]:
        report.append("🤖 Cost by Agent:")
        for agent_name, data in cost_data["by_agent"].items():
            report.append(f"  {agent_name}:")
            report.append(f"    Cost: ${data['cost']:.6f} {data['currency']}")
            report.append(f"    Tokens: {data['total_tokens']:,} ({data['input_tokens']:,} in, {data['output_tokens']:,} out)")
            report.append(f"    Model: {data['model_id']}")
            report.append("")
    
    return "\n".join(report)


def get_cost_summary(token_usage: Dict[str, Any]) -> str:
    """
    Get a quick cost summary for logging.
    
    Args:
        token_usage: Token usage data from TokenTracker
        
    Returns:
        Short cost summary string
    """
    if not token_usage:
        return "💰 Cost: $0.00 (no token usage data)"
    
    cost_data = calculate_investigation_cost(token_usage)
    total_cost = cost_data["summary"]["total_cost"]
    total_tokens = cost_data["summary"]["total_tokens"]
    
    return f"💰 Cost: ${total_cost:.6f} USD ({total_tokens:,} tokens)"


# Export commonly used functions
__all__ = [
    "get_model_pricing",
    "calculate_investigation_cost", 
    "format_cost_report",
    "get_cost_summary",
    "OPENAI_PRICING",
    "ANTHROPIC_PRICING",
    "DEFAULT_PRICING"
]
