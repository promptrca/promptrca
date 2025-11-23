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
from typing import Dict, Any
import json
from ..context import get_aws_client


@tool
def get_rds_instance_config(db_instance_identifier: str) -> str:
    """
    Retrieve RDS/Aurora database instance configuration for connection and performance analysis.

    Args:
        db_instance_identifier: The RDS instance identifier (e.g., "prod-db-instance")

    Returns:
        JSON string containing instance configuration including status, engine, instance class,
        storage, availability zone, endpoint, and more.
    """
    try:
        aws_client = get_aws_client()
        client = aws_client.get_client('rds')

        response = client.describe_db_instances(DBInstanceIdentifier=db_instance_identifier)

        if not response.get('DBInstances'):
            return json.dumps({"error": "DB instance not found", "db_instance_identifier": db_instance_identifier})

        db = response['DBInstances'][0]

        config = {
            "db_instance_identifier": db.get('DBInstanceIdentifier'),
            "db_instance_arn": db.get('DBInstanceArn'),
            "db_instance_status": db.get('DBInstanceStatus'),
            "engine": db.get('Engine'),
            "engine_version": db.get('EngineVersion'),
            "db_instance_class": db.get('DBInstanceClass'),
            "storage_type": db.get('StorageType'),
            "allocated_storage": db.get('AllocatedStorage'),
            "max_allocated_storage": db.get('MaxAllocatedStorage'),
            "endpoint": db.get('Endpoint', {}).get('Address'),
            "port": db.get('Endpoint', {}).get('Port'),
            "availability_zone": db.get('AvailabilityZone'),
            "multi_az": db.get('MultiAZ', False),
            "publicly_accessible": db.get('PubliclyAccessible', False),
            "storage_encrypted": db.get('StorageEncrypted', False),
            "db_parameter_groups": db.get('DBParameterGroups', []),
            "vpc_security_groups": db.get('VpcSecurityGroups', []),
            "db_subnet_group": db.get('DBSubnetGroup', {}).get('DBSubnetGroupName'),
            "preferred_maintenance_window": db.get('PreferredMaintenanceWindow'),
            "latest_restorable_time": str(db.get('LatestRestorableTime', '')),
            "backup_retention_period": db.get('BackupRetentionPeriod'),
            "performance_insights_enabled": db.get('PerformanceInsightsEnabled', False)
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "db_instance_identifier": db_instance_identifier})


@tool
def get_rds_cluster_config(db_cluster_identifier: str) -> str:
    """
    Retrieve RDS Aurora cluster configuration for cluster-level analysis.

    Args:
        db_cluster_identifier: The Aurora cluster identifier (e.g., "prod-aurora-cluster")

    Returns:
        JSON string containing cluster configuration including status, engine, endpoints,
        cluster members, and replication settings.
    """
    try:
        aws_client = get_aws_client()
        client = aws_client.get_client('rds')

        response = client.describe_db_clusters(DBClusterIdentifier=db_cluster_identifier)

        if not response.get('DBClusters'):
            return json.dumps({"error": "DB cluster not found", "db_cluster_identifier": db_cluster_identifier})

        cluster = response['DBClusters'][0]

        config = {
            "db_cluster_identifier": cluster.get('DBClusterIdentifier'),
            "db_cluster_arn": cluster.get('DBClusterArn'),
            "status": cluster.get('Status'),
            "engine": cluster.get('Engine'),
            "engine_version": cluster.get('EngineVersion'),
            "endpoint": cluster.get('Endpoint'),
            "reader_endpoint": cluster.get('ReaderEndpoint'),
            "port": cluster.get('Port'),
            "multi_az": cluster.get('MultiAZ', False),
            "database_name": cluster.get('DatabaseName'),
            "db_cluster_members": [
                {
                    "db_instance_identifier": member.get('DBInstanceIdentifier'),
                    "is_cluster_writer": member.get('IsClusterWriter', False),
                    "promotion_tier": member.get('PromotionTier', 1)
                }
                for member in cluster.get('DBClusterMembers', [])
            ],
            "vpc_security_groups": cluster.get('VpcSecurityGroups', []),
            "availability_zones": cluster.get('AvailabilityZones', []),
            "backup_retention_period": cluster.get('BackupRetentionPeriod'),
            "storage_encrypted": cluster.get('StorageEncrypted', False),
            "global_write_forwarding_status": cluster.get('GlobalWriteForwardingStatus')
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "db_cluster_identifier": db_cluster_identifier})


@tool
def get_rds_instance_metrics(db_instance_identifier: str, hours_back: int = 24) -> str:
    """
    Retrieve CloudWatch metrics for RDS instance performance analysis.

    Args:
        db_instance_identifier: The RDS instance identifier
        hours_back: Number of hours to look back for metrics (default: 24)

    Returns:
        JSON string containing metrics data for CPU, connections, storage, I/O, and more.
    """
    from datetime import datetime, timedelta

    try:
        aws_client = get_aws_client()
        client = aws_client.get_client('cloudwatch')

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)

        metrics = {}

        # Common RDS metrics
        metric_names = [
            'CPUUtilization', 'DatabaseConnections', 'FreeableMemory',
            'ReadIOPS', 'WriteIOPS', 'ReadLatency', 'WriteLatency',
            'FreeStorageSpace', 'ReplicaLag'
        ]

        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'DBInstanceIdentifier',
                        'Value': db_instance_identifier
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum', 'Minimum']
            )

            metrics[metric_name] = response.get('Datapoints', [])

        config = {
            "db_instance_identifier": db_instance_identifier,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "db_instance_identifier": db_instance_identifier})


@tool
def list_rds_instances() -> str:
    """
    List all RDS instances in the region.

    Returns:
        JSON string containing list of RDS instances with basic info.
    """
    try:
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('rds')

        response = client.describe_db_instances()
        instances = response.get('DBInstances', [])

        config = {
            "region": region,
            "instance_count": len(instances),
            "instances": [
                {
                    "db_instance_identifier": db.get('DBInstanceIdentifier'),
                    "engine": db.get('Engine'),
                    "db_instance_status": db.get('DBInstanceStatus'),
                    "endpoint": db.get('Endpoint', {}).get('Address')
                }
                for db in instances
            ]
        }

        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
