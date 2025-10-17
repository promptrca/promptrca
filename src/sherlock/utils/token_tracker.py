#!/usr/bin/env python3
"""
Sherlock Core - Token Usage Tracking
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

Token usage tracking with ContextVar for concurrency-safe per-investigation tracking.
"""

from contextvars import ContextVar
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from ..utils import get_logger
from .pricing import calculate_investigation_cost, get_cost_summary

logger = get_logger(__name__)

# Investigation-scoped tracker (asyncio-safe)
_current_tracker: ContextVar[Optional['TokenTracker']] = ContextVar('token_tracker', default=None)


@dataclass
class InvocationRecord:
    """Record of a single agent invocation with token usage."""
    agent_name: str
    model_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    timestamp: datetime = field(default_factory=datetime.now)


class TokenTracker:
    """Thread-safe token usage tracker using per-investigation scope."""
    
    def __init__(self):
        self.invocations: List[InvocationRecord] = []
        self.by_model: Dict[str, Dict[str, Any]] = {}
        self.by_agent: Dict[str, Dict[str, Any]] = {}
    
    def record_agent_invocation(self, agent_name: str, model_id: str, metrics_or_dict: Any):
        """
        Record token usage from an agent invocation.
        Defensive: handles None metrics, normalizes different key formats.
        """
        try:
            # Extract usage data defensively
            usage_data = self._extract_usage_data(metrics_or_dict, model_id)
            
            # Create invocation record
            record = InvocationRecord(
                agent_name=agent_name,
                model_id=usage_data['model_id'],
                input_tokens=usage_data['input_tokens'],
                output_tokens=usage_data['output_tokens'],
                total_tokens=usage_data['total_tokens']
            )
            
            # Store record
            self.invocations.append(record)
            
            # Update aggregations
            self._update_model_aggregation(record)
            self._update_agent_aggregation(record)
            
            logger.debug(f"📊 Recorded {agent_name}: {record.total_tokens} tokens ({record.input_tokens} in, {record.output_tokens} out)")
            
        except Exception as e:
            logger.warning(f"Failed to record token usage for {agent_name}: {e}")
            # Record zeros to maintain consistency
            self._record_zero_usage(agent_name, model_id)
    
    def _extract_usage_data(self, metrics_or_dict: Any, fallback_model_id: str) -> Dict[str, Any]:
        """Extract and normalize usage data from metrics."""
        if not metrics_or_dict:
            return self._create_zero_usage(fallback_model_id)
        
        # Debug logging
        logger.info(f"🔍 Extracting usage from: {type(metrics_or_dict)}")
        logger.info(f"🔍 Metrics attributes: {[attr for attr in dir(metrics_or_dict) if not attr.startswith('_')]}")
        
        # Try to print the actual metrics object
        try:
            logger.info(f"🔍 Metrics object: {metrics_or_dict}")
        except Exception as e:
            logger.info(f"🔍 Could not print metrics object: {e}")
        
        usage = {}
        
        # Try different ways to access usage data
        if hasattr(metrics_or_dict, 'accumulated_usage'):
            usage = metrics_or_dict.accumulated_usage
            logger.debug(f"Found accumulated_usage: {usage}")
        elif hasattr(metrics_or_dict, 'usage'):
            usage = metrics_or_dict.usage
            logger.debug(f"Found usage: {usage}")
        elif isinstance(metrics_or_dict, dict):
            usage = metrics_or_dict
            logger.debug(f"Using dict directly: {usage}")
        else:
            # Try to access common attributes directly
            usage = {}
            for attr in ['input_tokens', 'output_tokens', 'prompt_tokens', 'completion_tokens', 'total_tokens']:
                if hasattr(metrics_or_dict, attr):
                    usage[attr] = getattr(metrics_or_dict, attr)
                    logger.debug(f"Found {attr}: {usage[attr]}")
        
        if not usage:
            logger.warning(f"No usage data found in metrics: {metrics_or_dict}")
            return self._create_zero_usage(fallback_model_id)
        
        # Normalize keys (different providers use different names)
        input_tokens = (usage.get('input_tokens', 0) or 
                       usage.get('inputTokens', 0) or 
                       usage.get('prompt_tokens', 0))
        output_tokens = (usage.get('output_tokens', 0) or 
                        usage.get('outputTokens', 0) or 
                        usage.get('completion_tokens', 0))
        model_id = usage.get('model_id', fallback_model_id)
        
        # If we have total_tokens but not input/output, try to estimate
        total_tokens = usage.get('total_tokens', 0) or usage.get('totalTokens', 0)
        if not input_tokens and not output_tokens and total_tokens:
            # Rough estimate: 70% input, 30% output
            input_tokens = int(total_tokens * 0.7)
            output_tokens = int(total_tokens * 0.3)
            logger.debug(f"Estimated tokens from total: input={input_tokens}, output={output_tokens}")
        
        # Safely convert to int, handling Mock objects and other non-numeric types
        def safe_int(value, default=0):
            try:
                if hasattr(value, '__int__'):
                    return int(value)
                elif isinstance(value, (int, float, str)):
                    return int(float(value))
                else:
                    return default
            except (ValueError, TypeError):
                return default
        
        # Calculate total tokens - use provided total if available, otherwise sum input+output
        calculated_total = safe_int(input_tokens) + safe_int(output_tokens)
        provided_total = safe_int(total_tokens)
        final_total = provided_total if provided_total > 0 else calculated_total
        
        result = {
            'input_tokens': safe_int(input_tokens),
            'output_tokens': safe_int(output_tokens),
            'total_tokens': final_total,
            'model_id': model_id
        }
        
        logger.debug(f"Extracted usage data: {result}")
        return result
    
    def _create_zero_usage(self, model_id: str) -> Dict[str, Any]:
        """Create zero usage data."""
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'model_id': model_id
        }
    
    def _record_zero_usage(self, agent_name: str, model_id: str):
        """Record zero usage when metrics extraction fails."""
        record = InvocationRecord(
            agent_name=agent_name,
            model_id=model_id,
            input_tokens=0,
            output_tokens=0,
            total_tokens=0
        )
        self.invocations.append(record)
        self._update_model_aggregation(record)
        self._update_agent_aggregation(record)
    
    def _update_model_aggregation(self, record: InvocationRecord):
        """Update model-level aggregations."""
        model_id = record.model_id
        if model_id not in self.by_model:
            self.by_model[model_id] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'invocations': 0
            }
        
        self.by_model[model_id]['input_tokens'] += record.input_tokens
        self.by_model[model_id]['output_tokens'] += record.output_tokens
        self.by_model[model_id]['total_tokens'] += record.total_tokens
        self.by_model[model_id]['invocations'] += 1
    
    def _update_agent_aggregation(self, record: InvocationRecord):
        """Update agent-level aggregations."""
        agent_name = record.agent_name
        if agent_name not in self.by_agent:
            self.by_agent[agent_name] = {
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'invocations': 0,
                'model_id': record.model_id
            }
        
        self.by_agent[agent_name]['input_tokens'] += record.input_tokens
        self.by_agent[agent_name]['output_tokens'] += record.output_tokens
        self.by_agent[agent_name]['total_tokens'] += record.total_tokens
        self.by_agent[agent_name]['invocations'] += 1
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Return aggregated summary: totals + by_model + by_agent."""
        total_input = sum(record.input_tokens for record in self.invocations)
        total_output = sum(record.output_tokens for record in self.invocations)
        total_tokens = sum(record.total_tokens for record in self.invocations)
        
        return {
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_tokens': total_tokens,
            'by_model': dict(self.by_model),
            'by_agent': dict(self.by_agent)
        }
    
    def get_cost_analysis(self, use_batch_pricing: bool = False) -> Dict[str, Any]:
        """Return cost analysis based on current usage."""
        usage_summary = self.get_usage_summary()
        return calculate_investigation_cost(usage_summary, use_batch_pricing)
    
    def get_cost_summary(self) -> str:
        """Return a quick cost summary for logging."""
        usage_summary = self.get_usage_summary()
        return get_cost_summary(usage_summary)
    
    def get_detailed_report(self) -> Dict[str, Any]:
        """Return per-invocation list with timestamps."""
        return {
            'invocations': [
                {
                    'agent_name': record.agent_name,
                    'model_id': record.model_id,
                    'input_tokens': record.input_tokens,
                    'output_tokens': record.output_tokens,
                    'total_tokens': record.total_tokens,
                    'timestamp': record.timestamp.isoformat()
                }
                for record in self.invocations
            ],
            'summary': self.get_usage_summary()
        }
    
    def reset(self):
        """Clear all tracking data."""
        self.invocations.clear()
        self.by_model.clear()
        self.by_agent.clear()


# Context helpers
def set_current_tracker(tracker: TokenTracker):
    """Set the tracker for the current investigation context."""
    _current_tracker.set(tracker)


def get_current_tracker() -> Optional[TokenTracker]:
    """Get the tracker for the current investigation context."""
    return _current_tracker.get()


def extract_model_id_from_bedrock_model(model) -> str:
    """
    Extract model_id from a BedrockModel object.
    
    Args:
        model: BedrockModel object
        
    Returns:
        str: The model_id or 'unknown' if not found
    """
    if not model:
        return 'unknown'
    
    # Get model_id from config dict (standard BedrockModel structure)
    if hasattr(model, 'config') and isinstance(model.config, dict):
        return model.config.get('model_id', 'unknown')
    
    return 'unknown'


def extract_usage_from_agent_result(agent_result, model_id: str) -> Dict[str, Any]:
    """
    Utility function to extract usage data from AgentResult.
    Returns normalized usage data or zeros if extraction fails.
    """
    if not agent_result or not hasattr(agent_result, 'metrics') or not agent_result.metrics:
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'model_id': model_id
        }
    
    try:
        usage = getattr(agent_result.metrics, 'accumulated_usage', {})
        
        # Normalize keys
        input_tokens = (usage.get('input_tokens', 0) or 
                       usage.get('inputTokens', 0) or 
                       usage.get('prompt_tokens', 0))
        output_tokens = (usage.get('output_tokens', 0) or 
                        usage.get('outputTokens', 0) or 
                        usage.get('completion_tokens', 0))
        
        # Calculate total tokens - use provided total if available, otherwise sum input+output
        total_tokens = usage.get('total_tokens', 0) or usage.get('totalTokens', 0)
        calculated_total = int(input_tokens) + int(output_tokens) if input_tokens and output_tokens else 0
        provided_total = int(total_tokens) if total_tokens else 0
        final_total = provided_total if provided_total > 0 else calculated_total
        
        return {
            'input_tokens': int(input_tokens) if input_tokens else 0,
            'output_tokens': int(output_tokens) if output_tokens else 0,
            'total_tokens': final_total,
            'model_id': usage.get('model_id', model_id)
        }
    except Exception as e:
        logger.warning(f"Failed to extract usage from agent result: {e}")
        return {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0,
            'model_id': model_id
        }
