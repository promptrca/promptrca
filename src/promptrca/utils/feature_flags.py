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

Contact: christiangenn99+promptrca@gmail.com

Feature Flags - Gradual rollout and A/B testing support
"""

import os
import random
from typing import Dict, Any, Optional
from ..utils import get_logger

logger = get_logger(__name__)


class FeatureFlags:
    """
    Feature flag management for gradual rollout and A/B testing.

    Environment Variables:
    - PROMPTRCA_USE_DIRECT_ORCHESTRATION: Enable direct code orchestration (true/false)
    - PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE: Percentage of traffic to route to new orchestrator (0-100)
    - PROMPTRCA_FORCE_ORCHESTRATOR: Force specific orchestrator ('direct' or 'agent_tools')

    Examples:
        # Enable for all traffic
        PROMPTRCA_USE_DIRECT_ORCHESTRATION=true

        # Enable for 10% of traffic (canary)
        PROMPTRCA_USE_DIRECT_ORCHESTRATION=true
        PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE=10

        # Force specific orchestrator (for testing)
        PROMPTRCA_FORCE_ORCHESTRATOR=direct
    """

    # Cache for flag values to avoid repeated env var lookups
    _cache: Dict[str, Any] = {}

    @staticmethod
    def is_direct_orchestration_enabled(investigation_id: Optional[str] = None) -> bool:
        """
        Check if direct orchestration should be used for this investigation.

        Uses percentage-based rollout for gradual deployment.

        Args:
            investigation_id: Optional investigation ID for consistent routing

        Returns:
            True if direct orchestration should be used, False for agents-as-tools
        """
        # Check for forced orchestrator (for testing/debugging)
        force_orchestrator = os.getenv("PROMPTRCA_FORCE_ORCHESTRATOR", "").lower()
        if force_orchestrator == "direct":
            logger.info("🔧 Using DIRECT orchestration (forced via PROMPTRCA_FORCE_ORCHESTRATOR)")
            return True
        elif force_orchestrator == "agent_tools":
            logger.info("🔧 Using AGENT-TOOLS orchestration (forced via PROMPTRCA_FORCE_ORCHESTRATOR)")
            return False

        # Check if feature is enabled at all
        enabled = os.getenv("PROMPTRCA_USE_DIRECT_ORCHESTRATION", "false").lower() == "true"

        if not enabled:
            logger.debug("Direct orchestration disabled (PROMPTRCA_USE_DIRECT_ORCHESTRATION=false)")
            return False

        # Get rollout percentage (default: 100% if enabled)
        percentage_str = os.getenv("PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE", "100")
        try:
            percentage = int(percentage_str)
        except ValueError:
            logger.warning(f"Invalid PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE: {percentage_str}, defaulting to 100")
            percentage = 100

        # Validate percentage
        if percentage < 0 or percentage > 100:
            logger.warning(f"PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE out of range: {percentage}, defaulting to 100")
            percentage = 100

        # 100% rollout - always use direct orchestration
        if percentage == 100:
            logger.debug("Using DIRECT orchestration (100% rollout)")
            return True

        # 0% rollout - never use direct orchestration
        if percentage == 0:
            logger.debug("Using AGENT-TOOLS orchestration (0% rollout)")
            return False

        # Percentage-based rollout with consistent hashing
        if investigation_id:
            # Use consistent hashing for same investigation_id
            hash_value = hash(investigation_id) % 100
            use_direct = hash_value < percentage

            if use_direct:
                logger.info(f"🎯 Using DIRECT orchestration (hash={hash_value}, threshold={percentage})")
            else:
                logger.info(f"🎯 Using AGENT-TOOLS orchestration (hash={hash_value}, threshold={percentage})")

            return use_direct
        else:
            # Random selection for requests without ID
            use_direct = random.randint(0, 99) < percentage

            if use_direct:
                logger.info(f"🎲 Using DIRECT orchestration (random, p={percentage}%)")
            else:
                logger.info(f"🎲 Using AGENT-TOOLS orchestration (random, p={100-percentage}%)")

            return use_direct

    @staticmethod
    def get_orchestrator_type() -> str:
        """
        Get the configured orchestrator type for logging/metrics.

        Returns:
            'direct', 'agent_tools', or 'dynamic' (percentage-based)
        """
        force_orchestrator = os.getenv("PROMPTRCA_FORCE_ORCHESTRATOR", "").lower()
        if force_orchestrator:
            return force_orchestrator

        enabled = os.getenv("PROMPTRCA_USE_DIRECT_ORCHESTRATION", "false").lower() == "true"
        if not enabled:
            return "agent_tools"

        percentage_str = os.getenv("PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE", "100")
        try:
            percentage = int(percentage_str)
        except ValueError:
            percentage = 100

        if percentage == 100:
            return "direct"
        elif percentage == 0:
            return "agent_tools"
        else:
            return f"dynamic_{percentage}%"

    @staticmethod
    def get_all_flags() -> Dict[str, Any]:
        """
        Get all feature flag states for debugging/logging.

        Returns:
            Dictionary of all feature flags and their values
        """
        return {
            "use_direct_orchestration": os.getenv("PROMPTRCA_USE_DIRECT_ORCHESTRATION", "false"),
            "direct_orchestration_percentage": os.getenv("PROMPTRCA_DIRECT_ORCHESTRATION_PERCENTAGE", "100"),
            "force_orchestrator": os.getenv("PROMPTRCA_FORCE_ORCHESTRATOR", ""),
            "orchestrator_type": FeatureFlags.get_orchestrator_type(),
        }

    @staticmethod
    def print_configuration():
        """Print current feature flag configuration for debugging."""
        flags = FeatureFlags.get_all_flags()
        logger.info("=" * 60)
        logger.info("Feature Flag Configuration:")
        logger.info("=" * 60)
        for key, value in flags.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)
