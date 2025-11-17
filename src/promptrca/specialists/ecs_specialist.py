#!/usr/bin/env python3
"""
ECS Specialist for PromptRCA

Analyzes AWS ECS clusters, services, and tasks for container failures,
deployment issues, and resource constraints.

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


class ECSSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS ECS clusters, services, and tasks."""

    @property
    def supported_resource_types(self) -> List[str]:
        return ['ecs', 'ecs_cluster', 'ecs_service', 'ecs_task']

    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze ECS cluster, service, or task configuration and issues."""
        facts = []
        resource_type = resource.get('type', 'ecs')

        # Handle different resource types
        if 'cluster' in resource_type.lower():
            cluster_name = resource.get('name')
            if cluster_name:
                self.logger.info(f"   → Analyzing ECS cluster: {cluster_name}")
                facts.extend(await self._analyze_cluster(cluster_name))
        elif 'service' in resource_type.lower():
            cluster_name = resource.get('cluster_name')
            service_name = resource.get('name')
            if cluster_name and service_name:
                self.logger.info(f"   → Analyzing ECS service: {service_name}")
                facts.extend(await self._analyze_service(cluster_name, service_name))
        else:
            # Default to cluster analysis if we just have a name
            resource_name = resource.get('name')
            if resource_name:
                self.logger.info(f"   → Analyzing ECS resource: {resource_name}")
                # Try cluster first
                facts.extend(await self._analyze_cluster(resource_name))

        return self._limit_facts(facts)

    async def _analyze_cluster(self, cluster_name: str) -> List[Fact]:
        """Analyze ECS cluster configuration and capacity."""
        facts = []

        try:
            from ..tools.ecs_tools import get_ecs_cluster_config
            config_json = get_ecs_cluster_config(cluster_name)
            config = json.loads(config_json)

            if 'error' not in config:
                status = config.get('status')
                registered_instances = config.get('registered_container_instances', 0)
                running_tasks = config.get('running_tasks_count', 0)
                pending_tasks = config.get('pending_tasks_count', 0)
                active_services = config.get('active_services_count', 0)

                facts.append(self._create_fact(
                    source='ecs_cluster_config',
                    content=f"ECS cluster config loaded for {cluster_name}",
                    confidence=0.9,
                    metadata={
                        "cluster_name": cluster_name,
                        "status": status,
                        "registered_container_instances": registered_instances,
                        "running_tasks_count": running_tasks,
                        "pending_tasks_count": pending_tasks,
                        "active_services_count": active_services
                    }
                ))

                # Check cluster status
                if status != 'ACTIVE':
                    facts.append(self._create_fact(
                        source='ecs_cluster_config',
                        content=f"Cluster status is not ACTIVE: {status}",
                        confidence=0.9,
                        metadata={
                            "cluster_name": cluster_name,
                            "status": status,
                            "potential_issue": "cluster_not_active"
                        }
                    ))

                # Check for capacity issues
                if pending_tasks > 0 and registered_instances == 0:
                    facts.append(self._create_fact(
                        source='ecs_cluster_config',
                        content=f"No capacity: {pending_tasks} pending tasks with 0 container instances",
                        confidence=0.95,
                        metadata={
                            "cluster_name": cluster_name,
                            "pending_tasks": pending_tasks,
                            "registered_instances": registered_instances,
                            "issue_type": "insufficient_capacity"
                        }
                    ))
                elif pending_tasks > 0:
                    facts.append(self._create_fact(
                        source='ecs_cluster_config',
                        content=f"Tasks pending: {pending_tasks} tasks waiting for placement",
                        confidence=0.85,
                        metadata={
                            "cluster_name": cluster_name,
                            "pending_tasks": pending_tasks,
                            "potential_issue": "task_placement"
                        }
                    ))

                # Get cluster metrics
                facts.extend(await self._analyze_cluster_metrics(cluster_name))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for ECS cluster analysis: {e}")
            else:
                self.logger.debug(f"Failed to get ECS cluster config for {cluster_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get ECS cluster config for {cluster_name}: {e}")

        return facts

    async def _analyze_service(self, cluster_name: str, service_name: str) -> List[Fact]:
        """Analyze ECS service configuration and deployment status."""
        facts = []

        try:
            from ..tools.ecs_tools import get_ecs_service_config
            config_json = get_ecs_service_config(cluster_name, service_name)
            config = json.loads(config_json)

            if 'error' not in config:
                status = config.get('status')
                desired_count = config.get('desired_count', 0)
                running_count = config.get('running_count', 0)
                pending_count = config.get('pending_count', 0)
                task_definition = config.get('task_definition', '')
                launch_type = config.get('launch_type', 'EC2')

                facts.append(self._create_fact(
                    source='ecs_service_config',
                    content=f"ECS service config loaded for {service_name}",
                    confidence=0.9,
                    metadata={
                        "cluster_name": cluster_name,
                        "service_name": service_name,
                        "status": status,
                        "desired_count": desired_count,
                        "running_count": running_count,
                        "pending_count": pending_count,
                        "launch_type": launch_type
                    }
                ))

                # Check for deployment issues
                if running_count < desired_count:
                    facts.append(self._create_fact(
                        source='ecs_service_config',
                        content=f"Service deployment issue: running {running_count}/{desired_count} tasks",
                        confidence=0.9,
                        metadata={
                            "cluster_name": cluster_name,
                            "service_name": service_name,
                            "running_count": running_count,
                            "desired_count": desired_count,
                            "issue_type": "deployment_stuck"
                        }
                    ))

                # Check service events for errors
                events = config.get('events', [])
                for event in events[:5]:  # Check last 5 events
                    message = event.get('message', '').lower()
                    if any(keyword in message for keyword in ['failed', 'unable', 'error', 'insufficient']):
                        facts.append(self._create_fact(
                            source='ecs_service_config',
                            content=f"Service event: {event.get('message', '')}",
                            confidence=0.85,
                            metadata={
                                "cluster_name": cluster_name,
                                "service_name": service_name,
                                "event_time": event.get('created_at', ''),
                                "potential_issue": "service_event_error"
                            }
                        ))

                # Check deployments
                deployments = config.get('deployments', [])
                for deployment in deployments:
                    failed_tasks = deployment.get('failed_tasks', 0)
                    if failed_tasks > 0:
                        facts.append(self._create_fact(
                            source='ecs_service_config',
                            content=f"Deployment has {failed_tasks} failed tasks",
                            confidence=0.9,
                            metadata={
                                "cluster_name": cluster_name,
                                "service_name": service_name,
                                "deployment_id": deployment.get('id', ''),
                                "failed_tasks": failed_tasks,
                                "issue_type": "task_failures"
                            }
                        ))

                # Analyze task definition if we have it
                if task_definition:
                    facts.extend(await self._analyze_task_definition(task_definition))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for ECS service analysis: {e}")
            else:
                self.logger.debug(f"Failed to get ECS service config for {service_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get ECS service config for {service_name}: {e}")

        return facts

    async def _analyze_task_definition(self, task_definition: str) -> List[Fact]:
        """Analyze ECS task definition configuration."""
        facts = []

        try:
            from ..tools.ecs_tools import get_ecs_task_definition
            config_json = get_ecs_task_definition(task_definition)
            config = json.loads(config_json)

            if 'error' not in config:
                cpu = config.get('cpu')
                memory = config.get('memory')
                network_mode = config.get('network_mode')
                execution_role = config.get('execution_role_arn')
                task_role = config.get('task_role_arn')
                containers = config.get('container_definitions', [])

                facts.append(self._create_fact(
                    source='ecs_task_definition',
                    content=f"Task definition: {cpu} CPU, {memory} memory, {len(containers)} containers",
                    confidence=0.85,
                    metadata={
                        "task_definition": task_definition,
                        "cpu": cpu,
                        "memory": memory,
                        "network_mode": network_mode,
                        "container_count": len(containers)
                    }
                ))

                # Check for missing IAM roles
                if not execution_role:
                    facts.append(self._create_fact(
                        source='ecs_task_definition',
                        content=f"No execution role configured (required for Fargate and ECR image pull)",
                        confidence=0.8,
                        metadata={
                            "task_definition": task_definition,
                            "potential_issue": "missing_execution_role"
                        }
                    ))

                # Check container configurations
                for container in containers:
                    container_name = container.get('name')
                    container_cpu = container.get('cpu', 0)
                    container_memory = container.get('memory')
                    essential = container.get('essential', True)

                    # Check for low resources
                    if container_memory and int(container_memory) < 128:
                        facts.append(self._create_fact(
                            source='ecs_task_definition',
                            content=f"Container {container_name} has very low memory: {container_memory}MB",
                            confidence=0.75,
                            metadata={
                                "task_definition": task_definition,
                                "container_name": container_name,
                                "memory": container_memory,
                                "potential_issue": "low_memory"
                            }
                        ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for task definition analysis: {e}")
            else:
                self.logger.debug(f"Failed to get task definition for {task_definition}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get task definition for {task_definition}: {e}")

        return facts

    async def _analyze_cluster_metrics(self, cluster_name: str) -> List[Fact]:
        """Analyze ECS cluster metrics."""
        facts = []

        try:
            from ..tools.ecs_tools import get_ecs_cluster_metrics
            metrics_json = get_ecs_cluster_metrics(cluster_name, hours_back=24)
            metrics = json.loads(metrics_json)

            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})

                # Check CPU utilization
                cpu_utilization = metrics_data.get('CPUUtilization', [])
                if cpu_utilization:
                    avg_cpu = sum(point.get('Average', 0) for point in cpu_utilization) / max(len(cpu_utilization), 1)
                    max_cpu = max([point.get('Maximum', 0) for point in cpu_utilization], default=0)

                    if max_cpu > 80:
                        facts.append(self._create_fact(
                            source='ecs_metrics',
                            content=f"High CPU utilization: avg {avg_cpu:.1f}%, max {max_cpu:.1f}%",
                            confidence=0.85,
                            metadata={
                                "cluster_name": cluster_name,
                                "avg_cpu_utilization": avg_cpu,
                                "max_cpu_utilization": max_cpu,
                                "issue_type": "high_cpu"
                            }
                        ))

                # Check memory utilization
                memory_utilization = metrics_data.get('MemoryUtilization', [])
                if memory_utilization:
                    avg_memory = sum(point.get('Average', 0) for point in memory_utilization) / max(len(memory_utilization), 1)
                    max_memory = max([point.get('Maximum', 0) for point in memory_utilization], default=0)

                    if max_memory > 80:
                        facts.append(self._create_fact(
                            source='ecs_metrics',
                            content=f"High memory utilization: avg {avg_memory:.1f}%, max {max_memory:.1f}%",
                            confidence=0.85,
                            metadata={
                                "cluster_name": cluster_name,
                                "avg_memory_utilization": avg_memory,
                                "max_memory_utilization": max_memory,
                                "issue_type": "high_memory"
                            }
                        ))

        except RuntimeError as e:
            if "AWS client" in str(e):
                self.logger.error(f"AWS client context not available for ECS metrics analysis: {e}")
            else:
                self.logger.debug(f"Failed to get ECS metrics for {cluster_name}: {e}")
        except Exception as e:
            self.logger.debug(f"Failed to get ECS metrics for {cluster_name}: {e}")

        return facts
