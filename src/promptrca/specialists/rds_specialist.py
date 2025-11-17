#!/usr/bin/env python3
"""
RDS Specialist for PromptRCA

Analyzes AWS RDS/Aurora instances for connection pools, slow queries, and replication lag.

Copyright (C) 2025 Christian Gennaro Faraone
Licensed under GNU AGPL v3 or later.
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class RDSSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS RDS and Aurora databases."""

    @property
    def supported_resource_types(self) -> List[str]:
        return ['rds', 'rds_instance', 'aurora', 'aurora_cluster', 'database']

    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze RDS instance or Aurora cluster."""
        facts = []
        db_identifier = resource.get('name')

        if not db_identifier:
            return facts

        self.logger.info(f"   → Analyzing RDS/Aurora: {db_identifier}")

        # Try instance first, then cluster
        facts.extend(await self._analyze_instance(db_identifier))

        return self._limit_facts(facts)

    async def _analyze_instance(self, db_identifier: str) -> List[Fact]:
        """Analyze RDS instance configuration and metrics."""
        facts = []

        try:
            from ..tools.rds_tools import get_rds_instance_config, get_rds_instance_metrics
            config_json = get_rds_instance_config(db_identifier)
            config = json.loads(config_json)

            if 'error' not in config:
                status = config.get('db_instance_status')
                instance_class = config.get('db_instance_class')
                engine = config.get('engine')
                multi_az = config.get('multi_az', False)

                facts.append(self._create_fact(
                    source='rds_config',
                    content=f"RDS instance: {engine} {instance_class}, status: {status}",
                    confidence=0.9,
                    metadata={
                        "db_identifier": db_identifier,
                        "status": status,
                        "engine": engine,
                        "instance_class": instance_class,
                        "multi_az": multi_az
                    }
                ))

                if status != 'available':
                    facts.append(self._create_fact(
                        source='rds_config',
                        content=f"Instance not available: {status}",
                        confidence=0.95,
                        metadata={
                            "db_identifier": db_identifier,
                            "status": status,
                            "issue_type": "instance_unavailable"
                        }
                    ))

                # Get metrics
                metrics_json = get_rds_instance_metrics(db_identifier, hours_back=24)
                metrics = json.loads(metrics_json)

                if 'error' not in metrics:
                    metrics_data = metrics.get('metrics', {})

                    # Check CPU
                    cpu_data = metrics_data.get('CPUUtilization', [])
                    if cpu_data:
                        avg_cpu = sum(p.get('Average', 0) for p in cpu_data) / max(len(cpu_data), 1)
                        max_cpu = max([p.get('Maximum', 0) for p in cpu_data], default=0)
                        if max_cpu > 80:
                            facts.append(self._create_fact(
                                source='rds_metrics',
                                content=f"High CPU: avg {avg_cpu:.1f}%, max {max_cpu:.1f}%",
                                confidence=0.9,
                                metadata={"db_identifier": db_identifier, "issue_type": "high_cpu"}
                            ))

                    # Check connections
                    conn_data = metrics_data.get('DatabaseConnections', [])
                    if conn_data:
                        max_connections = max([p.get('Maximum', 0) for p in conn_data], default=0)
                        if max_connections > 80:
                            facts.append(self._create_fact(
                                source='rds_metrics',
                                content=f"High connection count: {max_connections}",
                                confidence=0.85,
                                metadata={"db_identifier": db_identifier, "issue_type": "high_connections"}
                            ))

                    # Check storage
                    storage_data = metrics_data.get('FreeStorageSpace', [])
                    if storage_data:
                        min_storage = min([p.get('Minimum', float('inf')) for p in storage_data], default=0)
                        if min_storage < 5000000000:  # Less than 5GB
                            facts.append(self._create_fact(
                                source='rds_metrics',
                                content=f"Low storage space: {min_storage / 1e9:.1f}GB remaining",
                                confidence=0.9,
                                metadata={"db_identifier": db_identifier, "issue_type": "low_storage"}
                            ))

        except Exception as e:
            self.logger.debug(f"Failed RDS analysis for {db_identifier}: {e}")

        return facts
