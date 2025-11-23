#!/usr/bin/env python3
"""
DynamoDB Specialist for PromptRCA

Analyzes AWS DynamoDB tables for throttling issues, capacity problems,
hot partitions, and stream configuration issues.

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


class DynamoDBSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS DynamoDB tables."""

    @property
    def supported_resource_types(self) -> List[str]:
        return ['dynamodb', 'dynamodb_table']

    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze DynamoDB table configuration, metrics, and stream issues."""
        facts = []
        table_name = resource.get('name')

        if not table_name:
            return facts

        self.logger.info(f"   → Analyzing DynamoDB table: {table_name}")

        # Get DynamoDB table configuration
        facts.extend(await self._analyze_configuration(table_name))

        # Get DynamoDB table metrics
        facts.extend(await self._analyze_metrics(table_name))

        # Get DynamoDB streams configuration
        facts.extend(await self._analyze_streams(table_name))

        return self._limit_facts(facts)

    async def _analyze_configuration(self, table_name: str) -> List[Fact]:
        """Analyze DynamoDB table configuration."""
        facts = []

        try:
            from ..tools.dynamodb_tools import get_dynamodb_table_config
            config_json = get_dynamodb_table_config(table_name)
            config = json.loads(config_json)

            if 'error' not in config:
                billing_mode = config.get('billing_mode')
                table_status = config.get('table_status')
                item_count = config.get('item_count', 0)
                table_size_bytes = config.get('table_size_bytes', 0)
                gsi_count = len(config.get('global_secondary_indexes', []))
                lsi_count = len(config.get('local_secondary_indexes', []))

                facts.append(self._create_fact(
                    source='dynamodb_config',
                    content=f"DynamoDB table config loaded for {table_name}",
                    confidence=0.9,
                    metadata={
                        "table_name": table_name,
                        "billing_mode": billing_mode,
                        "table_status": table_status,
                        "item_count": item_count,
                        "table_size_bytes": table_size_bytes,
                        "gsi_count": gsi_count,
                        "lsi_count": lsi_count
                    }
                ))

                # Check for provisioned capacity settings
                if billing_mode == 'PROVISIONED':
                    provisioned_throughput = config.get('provisioned_throughput', {})
                    read_capacity = provisioned_throughput.get('ReadCapacityUnits', 0)
                    write_capacity = provisioned_throughput.get('WriteCapacityUnits', 0)

                    facts.append(self._create_fact(
                        source='dynamodb_config',
                        content=f"Table uses PROVISIONED billing: {read_capacity} RCU, {write_capacity} WCU",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "read_capacity_units": read_capacity,
                            "write_capacity_units": write_capacity,
                            "billing_mode": "PROVISIONED"
                        }
                    ))

                    # Check for low capacity settings
                    if read_capacity < 5 or write_capacity < 5:
                        facts.append(self._create_fact(
                            source='dynamodb_config',
                            content=f"Low provisioned capacity: {read_capacity} RCU, {write_capacity} WCU",
                            confidence=0.8,
                            metadata={
                                "table_name": table_name,
                                "read_capacity_units": read_capacity,
                                "write_capacity_units": write_capacity,
                                "potential_issue": "low_capacity"
                            }
                        ))

                # Check for GSI configuration issues
                if gsi_count > 0:
                    gsi_list = config.get('global_secondary_indexes', [])
                    for gsi in gsi_list:
                        gsi_name = gsi.get('IndexName')
                        gsi_status = gsi.get('IndexStatus')

                        if gsi_status != 'ACTIVE':
                            facts.append(self._create_fact(
                                source='dynamodb_config',
                                content=f"GSI {gsi_name} is not ACTIVE: {gsi_status}",
                                confidence=0.9,
                                metadata={
                                    "table_name": table_name,
                                    "gsi_name": gsi_name,
                                    "gsi_status": gsi_status,
                                    "potential_issue": "gsi_not_active"
                                }
                            ))

                # Check table status
                if table_status != 'ACTIVE':
                    facts.append(self._create_fact(
                        source='dynamodb_config',
                        content=f"Table status is not ACTIVE: {table_status}",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "table_status": table_status,
                            "potential_issue": "table_not_active"
                        }
                    ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for DynamoDB config analysis: {e}")
            else:
                self.logger.debug(f"Failed to get DynamoDB config for {table_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get DynamoDB config for {table_name}: {e}")

        return facts

    async def _analyze_metrics(self, table_name: str) -> List[Fact]:
        """Analyze DynamoDB table metrics."""
        facts = []

        try:
            from ..tools.dynamodb_tools import get_dynamodb_table_metrics
            metrics_json = get_dynamodb_table_metrics(table_name, hours_back=24)
            metrics = json.loads(metrics_json)

            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})

                # Check for throttling events
                read_throttle_events = metrics_data.get('ReadThrottleEvents', [])
                write_throttle_events = metrics_data.get('WriteThrottleEvents', [])

                read_throttle_count = sum(point.get('Sum', 0) for point in read_throttle_events)
                write_throttle_count = sum(point.get('Sum', 0) for point in write_throttle_events)

                if read_throttle_count > 0 or write_throttle_count > 0:
                    facts.append(self._create_fact(
                        source='dynamodb_metrics',
                        content=f"Throttling detected: {read_throttle_count} read throttles, {write_throttle_count} write throttles",
                        confidence=0.95,
                        metadata={
                            "table_name": table_name,
                            "read_throttle_events": read_throttle_count,
                            "write_throttle_events": write_throttle_count,
                            "issue_type": "throttling"
                        }
                    ))

                # Check consumed capacity
                consumed_read_capacity = metrics_data.get('ConsumedReadCapacityUnits', [])
                consumed_write_capacity = metrics_data.get('ConsumedWriteCapacityUnits', [])

                if consumed_read_capacity or consumed_write_capacity:
                    avg_read_consumed = sum(point.get('Average', 0) for point in consumed_read_capacity) / max(len(consumed_read_capacity), 1)
                    avg_write_consumed = sum(point.get('Average', 0) for point in consumed_write_capacity) / max(len(consumed_write_capacity), 1)
                    max_read_consumed = max([point.get('Maximum', 0) for point in consumed_read_capacity], default=0)
                    max_write_consumed = max([point.get('Maximum', 0) for point in consumed_write_capacity], default=0)

                    facts.append(self._create_fact(
                        source='dynamodb_metrics',
                        content=f"Consumed capacity: avg {avg_read_consumed:.1f} RCU, {avg_write_consumed:.1f} WCU; max {max_read_consumed:.1f} RCU, {max_write_consumed:.1f} WCU",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "avg_read_consumed": avg_read_consumed,
                            "avg_write_consumed": avg_write_consumed,
                            "max_read_consumed": max_read_consumed,
                            "max_write_consumed": max_write_consumed
                        }
                    ))

                # Check for errors
                user_errors = metrics_data.get('UserErrors', [])
                system_errors = metrics_data.get('SystemErrors', [])

                user_error_count = sum(point.get('Sum', 0) for point in user_errors)
                system_error_count = sum(point.get('Sum', 0) for point in system_errors)

                if user_error_count > 0:
                    facts.append(self._create_fact(
                        source='dynamodb_metrics',
                        content=f"User errors detected: {user_error_count} total",
                        confidence=0.85,
                        metadata={
                            "table_name": table_name,
                            "user_error_count": user_error_count,
                            "issue_type": "user_errors"
                        }
                    ))

                if system_error_count > 0:
                    facts.append(self._create_fact(
                        source='dynamodb_metrics',
                        content=f"System errors detected: {system_error_count} total",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "system_error_count": system_error_count,
                            "issue_type": "system_errors"
                        }
                    ))

                # Check latency
                latency_data = metrics_data.get('SuccessfulRequestLatency', [])
                if latency_data:
                    avg_latency = sum(point.get('Average', 0) for point in latency_data) / max(len(latency_data), 1)
                    max_latency = max([point.get('Maximum', 0) for point in latency_data], default=0)

                    if max_latency > 100:  # More than 100ms
                        facts.append(self._create_fact(
                            source='dynamodb_metrics',
                            content=f"High latency detected: avg {avg_latency:.1f}ms, max {max_latency:.1f}ms",
                            confidence=0.8,
                            metadata={
                                "table_name": table_name,
                                "avg_latency_ms": avg_latency,
                                "max_latency_ms": max_latency,
                                "issue_type": "high_latency"
                            }
                        ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for DynamoDB metrics analysis: {e}")
            else:
                self.logger.debug(f"Failed to get DynamoDB metrics for {table_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get DynamoDB metrics for {table_name}: {e}")

        return facts

    async def _analyze_streams(self, table_name: str) -> List[Fact]:
        """Analyze DynamoDB Streams configuration."""
        facts = []

        try:
            from ..tools.dynamodb_tools import describe_dynamodb_streams
            streams_json = describe_dynamodb_streams(table_name)
            streams = json.loads(streams_json)

            if 'error' not in streams:
                stream_enabled = streams.get('stream_enabled', False)
                stream_view_type = streams.get('stream_view_type')
                stream_status = streams.get('stream_status')

                if stream_enabled:
                    facts.append(self._create_fact(
                        source='dynamodb_streams',
                        content=f"DynamoDB Streams enabled: {stream_view_type}",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "stream_enabled": stream_enabled,
                            "stream_view_type": stream_view_type,
                            "stream_status": stream_status
                        }
                    ))

                    # Check stream status
                    if stream_status and stream_status != 'ENABLED':
                        facts.append(self._create_fact(
                            source='dynamodb_streams',
                            content=f"Stream status is not ENABLED: {stream_status}",
                            confidence=0.9,
                            metadata={
                                "table_name": table_name,
                                "stream_status": stream_status,
                                "potential_issue": "stream_not_enabled"
                            }
                        ))

                    # Check shard count
                    shards = streams.get('shards', [])
                    if shards:
                        facts.append(self._create_fact(
                            source='dynamodb_streams',
                            content=f"Stream has {len(shards)} shards",
                            confidence=0.85,
                            metadata={
                                "table_name": table_name,
                                "shard_count": len(shards)
                            }
                        ))
                else:
                    facts.append(self._create_fact(
                        source='dynamodb_streams',
                        content=f"DynamoDB Streams not enabled for table",
                        confidence=0.9,
                        metadata={
                            "table_name": table_name,
                            "stream_enabled": False
                        }
                    ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for DynamoDB streams analysis: {e}")
            else:
                self.logger.debug(f"Failed to get DynamoDB streams for {table_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get DynamoDB streams for {table_name}: {e}")

        return facts
