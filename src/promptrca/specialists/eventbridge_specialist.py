#!/usr/bin/env python3
"""
EventBridge Specialist for PromptRCA

Analyzes AWS EventBridge rules, targets, event patterns, and delivery failures.

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

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class EventBridgeSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS EventBridge rules and event buses."""

    @property
    def supported_resource_types(self) -> List[str]:
        return ['eventbridge', 'eventbridge_rule', 'events', 'events_rule']

    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze EventBridge rule configuration, targets, and metrics."""
        facts = []
        rule_name = resource.get('name')

        if not rule_name:
            return facts

        self.logger.info(f"   → Analyzing EventBridge rule: {rule_name}")

        # Get EventBridge rule configuration
        facts.extend(await self._analyze_rule_configuration(rule_name))

        # Get EventBridge rule targets
        facts.extend(await self._analyze_targets(rule_name))

        # Get EventBridge rule metrics
        facts.extend(await self._analyze_metrics(rule_name))

        return self._limit_facts(facts)

    async def _analyze_rule_configuration(self, rule_name: str) -> List[Fact]:
        """Analyze EventBridge rule configuration."""
        facts = []

        try:
            from ..tools.eventbridge_tools import get_eventbridge_rule_config
            config_json = get_eventbridge_rule_config(rule_name)
            config = json.loads(config_json)

            if 'error' not in config:
                rule_state = config.get('state')
                event_pattern = config.get('event_pattern')
                schedule_expression = config.get('schedule_expression')
                event_bus_name = config.get('event_bus_name', 'default')

                facts.append(self._create_fact(
                    source='eventbridge_config',
                    content=f"EventBridge rule config loaded for {rule_name}",
                    confidence=0.9,
                    metadata={
                        "rule_name": rule_name,
                        "state": rule_state,
                        "event_bus_name": event_bus_name,
                        "has_event_pattern": event_pattern is not None,
                        "has_schedule": schedule_expression is not None
                    }
                ))

                # Check if rule is disabled
                if rule_state == 'DISABLED':
                    facts.append(self._create_fact(
                        source='eventbridge_config',
                        content=f"EventBridge rule is DISABLED",
                        confidence=0.95,
                        metadata={
                            "rule_name": rule_name,
                            "rule_state": rule_state,
                            "potential_issue": "rule_disabled"
                        }
                    ))

                # Check for event pattern
                if event_pattern:
                    try:
                        pattern_obj = json.loads(event_pattern) if isinstance(event_pattern, str) else event_pattern
                        facts.append(self._create_fact(
                            source='eventbridge_config',
                            content=f"Event pattern configured with {len(pattern_obj)} filters",
                            confidence=0.85,
                            metadata={
                                "rule_name": rule_name,
                                "event_pattern": pattern_obj
                            }
                        ))
                    except json.JSONDecodeError:
                        facts.append(self._create_fact(
                            source='eventbridge_config',
                            content=f"Event pattern may have JSON syntax errors",
                            confidence=0.8,
                            metadata={
                                "rule_name": rule_name,
                                "potential_issue": "invalid_event_pattern"
                            }
                        ))

                # Check for schedule expression
                if schedule_expression:
                    facts.append(self._create_fact(
                        source='eventbridge_config',
                        content=f"Scheduled rule: {schedule_expression}",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "schedule_expression": schedule_expression
                        }
                    ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for EventBridge config analysis: {e}")
            else:
                self.logger.debug(f"Failed to get EventBridge config for {rule_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get EventBridge config for {rule_name}: {e}")

        return facts

    async def _analyze_targets(self, rule_name: str) -> List[Fact]:
        """Analyze EventBridge rule targets."""
        facts = []

        try:
            from ..tools.eventbridge_tools import get_eventbridge_targets
            targets_json = get_eventbridge_targets(rule_name)
            targets_data = json.loads(targets_json)

            if 'error' not in targets_data:
                target_count = targets_data.get('target_count', 0)
                targets = targets_data.get('targets', [])

                if target_count == 0:
                    facts.append(self._create_fact(
                        source='eventbridge_targets',
                        content=f"No targets configured for rule",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "target_count": 0,
                            "potential_issue": "no_targets"
                        }
                    ))
                else:
                    facts.append(self._create_fact(
                        source='eventbridge_targets',
                        content=f"Rule has {target_count} target(s) configured",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "target_count": target_count
                        }
                    ))

                    # Analyze each target
                    for target in targets:
                        target_arn = target.get('arn', '')
                        target_id = target.get('id', '')
                        has_dlq = target.get('dead_letter_config') is not None
                        has_retry_policy = target.get('retry_policy') is not None

                        # Extract service type from ARN
                        service_type = 'unknown'
                        if ':lambda:' in target_arn:
                            service_type = 'lambda'
                        elif ':sqs:' in target_arn:
                            service_type = 'sqs'
                        elif ':sns:' in target_arn:
                            service_type = 'sns'
                        elif ':states:' in target_arn:
                            service_type = 'stepfunctions'
                        elif ':kinesis:' in target_arn:
                            service_type = 'kinesis'
                        elif ':ecs:' in target_arn:
                            service_type = 'ecs'

                        facts.append(self._create_fact(
                            source='eventbridge_targets',
                            content=f"Target {target_id}: {service_type} service",
                            confidence=0.85,
                            metadata={
                                "rule_name": rule_name,
                                "target_id": target_id,
                                "target_arn": target_arn,
                                "service_type": service_type,
                                "has_dlq": has_dlq,
                                "has_retry_policy": has_retry_policy
                            }
                        ))

                        # Check for missing DLQ or retry policy
                        if not has_dlq and not has_retry_policy:
                            facts.append(self._create_fact(
                                source='eventbridge_targets',
                                content=f"Target {target_id} lacks DLQ and retry policy",
                                confidence=0.75,
                                metadata={
                                    "rule_name": rule_name,
                                    "target_id": target_id,
                                    "potential_issue": "no_error_handling"
                                }
                            ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for EventBridge targets analysis: {e}")
            else:
                self.logger.debug(f"Failed to get EventBridge targets for {rule_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get EventBridge targets for {rule_name}: {e}")

        return facts

    async def _analyze_metrics(self, rule_name: str) -> List[Fact]:
        """Analyze EventBridge rule metrics."""
        facts = []

        try:
            from ..tools.eventbridge_tools import get_eventbridge_metrics
            metrics_json = get_eventbridge_metrics(rule_name, hours_back=24)
            metrics = json.loads(metrics_json)

            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})

                # Check for failed invocations
                failed_invocations = metrics_data.get('FailedInvocations', [])
                failed_count = sum(point.get('Sum', 0) for point in failed_invocations)

                if failed_count > 0:
                    facts.append(self._create_fact(
                        source='eventbridge_metrics',
                        content=f"Failed invocations detected: {failed_count} total",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "failed_invocations": failed_count,
                            "issue_type": "invocation_failures"
                        }
                    ))

                # Check for successful invocations
                successful_invocations = metrics_data.get('SuccessfulInvocations', [])
                success_count = sum(point.get('Sum', 0) for point in successful_invocations)

                if success_count > 0:
                    facts.append(self._create_fact(
                        source='eventbridge_metrics',
                        content=f"Successful invocations: {success_count} total",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "successful_invocations": success_count
                        }
                    ))

                # Check for throttling
                throttled_rules = metrics_data.get('ThrottledRules', [])
                throttle_count = sum(point.get('Sum', 0) for point in throttled_rules)

                if throttle_count > 0:
                    facts.append(self._create_fact(
                        source='eventbridge_metrics',
                        content=f"Throttling detected: {throttle_count} throttled requests",
                        confidence=0.9,
                        metadata={
                            "rule_name": rule_name,
                            "throttled_requests": throttle_count,
                            "issue_type": "throttling"
                        }
                    ))

                # Check matched events
                matched_events = metrics_data.get('MatchedEvents', [])
                matched_count = sum(point.get('Sum', 0) for point in matched_events)

                if matched_count > 0:
                    facts.append(self._create_fact(
                        source='eventbridge_metrics',
                        content=f"Matched events: {matched_count} total",
                        confidence=0.85,
                        metadata={
                            "rule_name": rule_name,
                            "matched_events": matched_count
                        }
                    ))

                # Calculate failure rate if we have both successes and failures
                if success_count > 0 or failed_count > 0:
                    total_invocations = success_count + failed_count
                    failure_rate = failed_count / total_invocations if total_invocations > 0 else 0

                    if failure_rate > 0.1:  # More than 10% failure rate
                        facts.append(self._create_fact(
                            source='eventbridge_metrics',
                            content=f"High failure rate: {failure_rate:.1%}",
                            confidence=0.9,
                            metadata={
                                "rule_name": rule_name,
                                "failure_rate": failure_rate,
                                "total_invocations": total_invocations,
                                "issue_type": "high_failure_rate"
                            }
                        ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for EventBridge metrics analysis: {e}")
            else:
                self.logger.debug(f"Failed to get EventBridge metrics for {rule_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get EventBridge metrics for {rule_name}: {e}")

        return facts
