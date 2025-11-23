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

from strands import tool
from typing import Dict, Any, Optional
import json
from ..context import get_aws_client


@tool
def get_ecs_cluster_config(cluster_name: str) -> str:
    """
    Retrieve comprehensive ECS cluster configuration for capacity and task analysis.

    This tool fetches all critical cluster settings needed to diagnose ECS issues:
    - Cluster status and health
    - Registered container instances
    - Running and pending tasks count
    - Active services count
    - Capacity provider configuration
    - Container insights status

    Args:
        cluster_name: The ECS cluster name or ARN (e.g., "production-cluster")

    Returns:
        JSON string containing:
        - cluster_name: Name of the cluster
        - cluster_arn: Full ARN of the cluster
        - status: Cluster status (ACTIVE, PROVISIONING, DEPROVISIONING, FAILED, INACTIVE)
        - registered_container_instances: Number of EC2 instances in cluster
        - running_tasks_count: Number of currently running tasks
        - pending_tasks_count: Number of pending tasks
        - active_services_count: Number of active services
        - capacity_providers: List of capacity providers
        - default_capacity_provider_strategy: Default capacity provider strategy
        - settings: Cluster settings (containerInsights)
        - statistics: Cluster statistics

    Common Configuration Issues:
        - No capacity: registered_container_instances = 0
        - Tasks pending: pending_tasks_count > 0 with no capacity
        - Inactive cluster: status != ACTIVE
        - Missing capacity providers: No capacity providers configured

    Use Cases:
        - Task placement failures (no available capacity)
        - Service deployment issues (pending tasks)
        - Capacity planning (running vs pending tasks)
        - Container instance health (registered instances)
        - Capacity provider configuration verification

    Note: This tool provides current cluster state, not historical data.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('ecs')

        response = client.describe_clusters(clusters=[cluster_name])

        if not response.get('clusters'):
            return json.dumps({"error": "Cluster not found", "cluster_name": cluster_name})

        cluster = response['clusters'][0]

        config = {
            "cluster_name": cluster.get('clusterName'),
            "cluster_arn": cluster.get('clusterArn'),
            "status": cluster.get('status'),
            "registered_container_instances": cluster.get('registeredContainerInstancesCount', 0),
            "running_tasks_count": cluster.get('runningTasksCount', 0),
            "pending_tasks_count": cluster.get('pendingTasksCount', 0),
            "active_services_count": cluster.get('activeServicesCount', 0),
            "capacity_providers": cluster.get('capacityProviders', []),
            "default_capacity_provider_strategy": cluster.get('defaultCapacityProviderStrategy', []),
            "settings": cluster.get('settings', []),
            "statistics": cluster.get('statistics', [])
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster_name": cluster_name})


@tool
def get_ecs_service_config(cluster_name: str, service_name: str) -> str:
    """
    Retrieve ECS service configuration for deployment and scaling analysis.

    This tool fetches service settings to diagnose deployment failures, scaling issues,
    and service health problems.

    Args:
        cluster_name: The ECS cluster name (e.g., "production-cluster")
        service_name: The ECS service name (e.g., "api-service")

    Returns:
        JSON string containing:
        - service_name: Name of the service
        - service_arn: Full ARN of the service
        - status: Service status (ACTIVE, DRAINING, INACTIVE)
        - desired_count: Desired number of tasks
        - running_count: Number of running tasks
        - pending_count: Number of pending tasks
        - task_definition: Task definition ARN
        - deployment_configuration: Deployment settings
        - load_balancers: Load balancer configuration
        - network_configuration: VPC, subnets, security groups
        - launch_type: FARGATE or EC2
        - platform_version: Fargate platform version
        - health_check_grace_period: Health check grace period
        - scheduling_strategy: REPLICA or DAEMON
        - deployments: Current and past deployments
        - events: Recent service events

    Common Service Issues:
        - Deployment stuck: running_count < desired_count
        - Tasks failing: Check events for failure reasons
        - Health check failures: Tasks killed by load balancer
        - Insufficient capacity: Pending tasks with no resources

    Use Cases:
        - Deployment troubleshooting (stuck or failed deployments)
        - Scaling issues (desired vs running count mismatch)
        - Task placement failures (insufficient resources)
        - Load balancer integration problems
        - Network configuration issues

    Note: Events are limited to the most recent 100 events.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('ecs')

        response = client.describe_services(
            cluster=cluster_name,
            services=[service_name]
        )

        if not response.get('services'):
            return json.dumps({"error": "Service not found", "cluster_name": cluster_name, "service_name": service_name})

        service = response['services'][0]

        config = {
            "service_name": service.get('serviceName'),
            "service_arn": service.get('serviceArn'),
            "status": service.get('status'),
            "desired_count": service.get('desiredCount', 0),
            "running_count": service.get('runningCount', 0),
            "pending_count": service.get('pendingCount', 0),
            "task_definition": service.get('taskDefinition'),
            "deployment_configuration": service.get('deploymentConfiguration', {}),
            "load_balancers": service.get('loadBalancers', []),
            "network_configuration": service.get('networkConfiguration', {}),
            "launch_type": service.get('launchType'),
            "platform_version": service.get('platformVersion'),
            "health_check_grace_period": service.get('healthCheckGracePeriodSeconds'),
            "scheduling_strategy": service.get('schedulingStrategy'),
            "enable_ecs_managed_tags": service.get('enableECSManagedTags', False),
            "deployments": [
                {
                    "id": dep.get('id'),
                    "status": dep.get('status'),
                    "desired_count": dep.get('desiredCount'),
                    "running_count": dep.get('runningCount'),
                    "pending_count": dep.get('pendingCount'),
                    "failed_tasks": dep.get('failedTasks', 0),
                    "created_at": str(dep.get('createdAt', '')),
                    "updated_at": str(dep.get('updatedAt', ''))
                }
                for dep in service.get('deployments', [])
            ],
            "events": [
                {
                    "id": event.get('id'),
                    "created_at": str(event.get('createdAt', '')),
                    "message": event.get('message', '')
                }
                for event in service.get('events', [])[:10]  # Get last 10 events
            ]
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster_name": cluster_name, "service_name": service_name})


@tool
def get_ecs_task_definition(task_definition: str) -> str:
    """
    Retrieve ECS task definition for container configuration analysis.

    This tool fetches task definition to diagnose container failures, resource issues,
    and configuration problems.

    Args:
        task_definition: Task definition name or ARN (e.g., "api-task:5")

    Returns:
        JSON string containing:
        - family: Task definition family name
        - task_definition_arn: Full ARN
        - revision: Revision number
        - status: ACTIVE or INACTIVE
        - requires_compatibilities: FARGATE, EC2
        - cpu: Task-level CPU units
        - memory: Task-level memory (MiB)
        - network_mode: awsvpc, bridge, host, none
        - container_definitions: Container configurations
        - execution_role_arn: Task execution IAM role
        - task_role_arn: Task IAM role
        - volumes: Shared volumes

    Common Task Definition Issues:
        - Insufficient resources: CPU/memory too low
        - Missing IAM roles: No execution or task role
        - Image pull failures: Invalid image URL or permissions
        - Port conflicts: Multiple containers using same port
        - Environment variable issues: Missing required variables

    Use Cases:
        - Container startup failures (image, resources, IAM)
        - Resource allocation problems (CPU/memory limits)
        - IAM permission issues (execution and task roles)
        - Network configuration troubleshooting
        - Volume mount failures

    Note: This returns the task definition template, not running task details.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('ecs')

        response = client.describe_task_definition(taskDefinition=task_definition)
        task_def = response['taskDefinition']

        config = {
            "family": task_def.get('family'),
            "task_definition_arn": task_def.get('taskDefinitionArn'),
            "revision": task_def.get('revision'),
            "status": task_def.get('status'),
            "requires_compatibilities": task_def.get('requiresCompatibilities', []),
            "cpu": task_def.get('cpu'),
            "memory": task_def.get('memory'),
            "network_mode": task_def.get('networkMode'),
            "execution_role_arn": task_def.get('executionRoleArn'),
            "task_role_arn": task_def.get('taskRoleArn'),
            "volumes": task_def.get('volumes', []),
            "container_definitions": [
                {
                    "name": container.get('name'),
                    "image": container.get('image'),
                    "cpu": container.get('cpu', 0),
                    "memory": container.get('memory'),
                    "memory_reservation": container.get('memoryReservation'),
                    "essential": container.get('essential', True),
                    "port_mappings": container.get('portMappings', []),
                    "environment": container.get('environment', []),
                    "mount_points": container.get('mountPoints', []),
                    "log_configuration": container.get('logConfiguration', {})
                }
                for container in task_def.get('containerDefinitions', [])
            ]
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "task_definition": task_definition})


@tool
def list_ecs_tasks(cluster_name: str, service_name: Optional[str] = None, desired_status: str = "RUNNING") -> str:
    """
    List ECS tasks in a cluster or service.

    This tool lists tasks to identify running, stopped, or pending tasks.

    Args:
        cluster_name: The ECS cluster name (e.g., "production-cluster")
        service_name: Optional service name to filter tasks
        desired_status: Task status filter (RUNNING, STOPPED, PENDING)

    Returns:
        JSON string containing:
        - cluster_name: Cluster name
        - service_name: Service name (if provided)
        - desired_status: Status filter used
        - task_count: Number of tasks found
        - task_arns: List of task ARNs

    Use Cases:
        - Find running tasks for detailed analysis
        - Identify stopped tasks for failure investigation
        - Check pending tasks for placement issues

    Note: Returns task ARNs only, use describe_ecs_tasks for details.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('ecs')

        kwargs = {
            "cluster": cluster_name,
            "desiredStatus": desired_status
        }

        if service_name:
            kwargs["serviceName"] = service_name

        response = client.list_tasks(**kwargs)
        task_arns = response.get('taskArns', [])

        config = {
            "cluster_name": cluster_name,
            "service_name": service_name,
            "desired_status": desired_status,
            "task_count": len(task_arns),
            "task_arns": task_arns
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster_name": cluster_name})


@tool
def describe_ecs_tasks(cluster_name: str, task_arns: str) -> str:
    """
    Describe ECS tasks for detailed task analysis.

    This tool fetches detailed information about specific tasks including their
    status, container states, and failure reasons.

    Args:
        cluster_name: The ECS cluster name (e.g., "production-cluster")
        task_arns: Comma-separated list of task ARNs or task IDs

    Returns:
        JSON string containing:
        - cluster_name: Cluster name
        - tasks: Array of task details including:
          - task_arn: Full task ARN
          - task_definition_arn: Task definition used
          - last_status: Current task status
          - desired_status: Desired task status
          - containers: Container states
          - started_at: Task start time
          - stopped_at: Task stop time (if stopped)
          - stopped_reason: Reason for stopping
          - cpu: Allocated CPU
          - memory: Allocated memory

    Common Task Failure Reasons:
        - Essential container failed
        - Task failed ELB health checks
        - Insufficient resources
        - Image pull failed
        - Container runtime errors

    Use Cases:
        - Investigate task failures (stopped_reason)
        - Container crash analysis (container exit codes)
        - Resource allocation verification
        - Health check failure diagnosis

    Note: Can describe up to 100 tasks in a single call.
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('ecs')

        # Parse task ARNs (handle comma-separated string)
        task_list = [arn.strip() for arn in task_arns.split(',') if arn.strip()]

        if not task_list:
            return json.dumps({"error": "No task ARNs provided"})

        response = client.describe_tasks(
            cluster=cluster_name,
            tasks=task_list
        )

        tasks = response.get('tasks', [])

        config = {
            "cluster_name": cluster_name,
            "task_count": len(tasks),
            "tasks": [
                {
                    "task_arn": task.get('taskArn'),
                    "task_definition_arn": task.get('taskDefinitionArn'),
                    "last_status": task.get('lastStatus'),
                    "desired_status": task.get('desiredStatus'),
                    "started_at": str(task.get('startedAt', '')),
                    "stopped_at": str(task.get('stoppedAt', '')),
                    "stopped_reason": task.get('stoppedReason', ''),
                    "cpu": task.get('cpu'),
                    "memory": task.get('memory'),
                    "launch_type": task.get('launchType'),
                    "platform_version": task.get('platformVersion'),
                    "health_status": task.get('healthStatus'),
                    "containers": [
                        {
                            "name": container.get('name'),
                            "last_status": container.get('lastStatus'),
                            "exit_code": container.get('exitCode'),
                            "reason": container.get('reason', ''),
                            "health_status": container.get('healthStatus')
                        }
                        for container in task.get('containers', [])
                    ]
                }
                for task in tasks
            ],
            "failures": response.get('failures', [])
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster_name": cluster_name})


@tool
def get_ecs_cluster_metrics(cluster_name: str, hours_back: int = 24) -> str:
    """
    Retrieve CloudWatch metrics for ECS cluster performance analysis.

    This tool fetches key metrics to identify capacity issues, resource utilization,
    and service health problems.

    Args:
        cluster_name: The ECS cluster name (e.g., "production-cluster")
        hours_back: Number of hours to look back for metrics (default: 24)

    Returns:
        JSON string containing:
        - cluster_name: Cluster name
        - time_range: Metrics time range
        - metrics: Dictionary with metric data:
          - CPUUtilization: Cluster CPU usage
          - MemoryUtilization: Cluster memory usage

    Use Cases:
        - Resource utilization analysis
        - Capacity planning
        - Performance monitoring

    Note: Metrics are aggregated in 1-hour periods.
    """
    from datetime import datetime, timedelta

    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('cloudwatch')

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        metrics = {}

        # Common ECS cluster metrics
        metric_names = ['CPUUtilization', 'MemoryUtilization']

        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/ECS',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'ClusterName',
                        'Value': cluster_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )

            metrics[metric_name] = response.get('Datapoints', [])

        config = {
            "cluster_name": cluster_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "cluster_name": cluster_name})
