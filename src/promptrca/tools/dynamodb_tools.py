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

"""

from strands import tool
from typing import Dict, Any
import json
from ..utils.config import get_region


@tool
def get_dynamodb_table_config(table_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve comprehensive DynamoDB table configuration for capacity and performance analysis.
    
    This tool fetches all critical table settings needed to diagnose DynamoDB issues:
    - Billing mode (provisioned vs on-demand)
    - Capacity settings (read/write units)
    - Index configuration (GSI/LSI)
    - Encryption and security settings
    - Stream configuration
    - Table status and metadata
    
    Args:
        table_name: The DynamoDB table name (e.g., "users", "orders-prod")
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - table_name: Name of the table
        - table_arn: Full ARN of the table
        - table_status: Current status (ACTIVE, CREATING, UPDATING, DELETING)
        - creation_date: When the table was created
        - item_count: Number of items in the table
        - table_size_bytes: Total size of the table
        - key_schema: Primary key definition
        - attribute_definitions: Attribute type definitions
        - provisioned_throughput: Read/write capacity units (if provisioned billing)
        - billing_mode: Billing mode (PROVISIONED or PAY_PER_REQUEST)
        - global_secondary_indexes: GSI configurations
        - local_secondary_indexes: LSI configurations
        - stream_specification: DynamoDB Streams configuration
        - sse_description: Server-side encryption settings
        - table_class: Storage class (STANDARD or STANDARD_IA)
    
    Common Configuration Issues:
        - Insufficient capacity: Provisioned throughput too low for workload
        - Missing indexes: Queries failing due to missing GSI/LSI
        - Billing mode mismatch: On-demand vs provisioned capacity issues
        - Encryption problems: SSE configuration issues
        - Stream configuration: Missing or misconfigured streams
    
    Use Cases:
        - Capacity planning and optimization
        - Throttling analysis (check provisioned vs consumed capacity)
        - Index optimization (verify GSI/LSI configuration)
        - Security auditing (encryption and access patterns)
        - Performance tuning (billing mode and capacity settings)
        - Stream setup verification (for real-time processing)
    
    Note: This tool provides the current configuration, not historical changes.
    """
    import boto3
    
    try:
        client = boto3.client('dynamodb', region_name=region)
        response = client.describe_table(TableName=table_name)
        table = response['Table']
        
        config = {
            "table_name": table.get('TableName'),
            "table_arn": table.get('TableArn'),
            "table_status": table.get('TableStatus'),
            "creation_date": str(table.get('CreationDateTime')),
            "item_count": table.get('ItemCount', 0),
            "table_size_bytes": table.get('TableSizeBytes', 0),
            "key_schema": table.get('KeySchema', []),
            "attribute_definitions": table.get('AttributeDefinitions', []),
            "provisioned_throughput": table.get('ProvisionedThroughput', {}),
            "billing_mode": table.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED'),
            "global_secondary_indexes": table.get('GlobalSecondaryIndexes', []),
            "local_secondary_indexes": table.get('LocalSecondaryIndexes', []),
            "stream_specification": table.get('StreamSpecification', {}),
            "sse_description": table.get('SSEDescription', {}),
            "archival_summary": table.get('ArchivalSummary', {}),
            "table_class": table.get('TableClass', 'STANDARD')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "table_name": table_name})


@tool
def get_dynamodb_table_metrics(table_name: str, hours_back: int = 24, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve CloudWatch metrics for DynamoDB table performance and throttling analysis.
    
    This tool fetches key performance metrics to identify capacity issues, throttling,
    and usage patterns. Critical for diagnosing DynamoDB performance problems and
    optimizing capacity allocation.
    
    Args:
        table_name: The DynamoDB table name (e.g., "users", "orders-prod")
        hours_back: Number of hours to look back for metrics (default: 24)
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - table_name: Name of the table
        - time_range: Start/end times and duration of metrics collection
        - metrics: Dictionary with metric data:
          - ConsumedReadCapacityUnits: Actual read capacity consumed
          - ConsumedWriteCapacityUnits: Actual write capacity consumed
          - ReadThrottleEvents: Number of read throttling events
          - WriteThrottleEvents: Number of write throttling events
          - SuccessfulRequestLatency: Request latency statistics
          - UserErrors: Client-side errors (4xx)
          - SystemErrors: Server-side errors (5xx)
    
    Key Metrics Analysis:
        - Throttling: ReadThrottleEvents > 0 or WriteThrottleEvents > 0 indicates capacity issues
        - Capacity Utilization: Consumed vs Provisioned capacity (if provisioned billing)
        - Error Rates: High UserErrors or SystemErrors indicate problems
        - Latency: High SuccessfulRequestLatency suggests performance issues
        - Burst Patterns: Sudden spikes in consumed capacity
    
    Use Cases:
        - Throttling investigation (identify capacity bottlenecks)
        - Performance optimization (analyze usage patterns)
        - Capacity planning (right-size provisioned throughput)
        - Error analysis (investigate user and system errors)
        - Cost optimization (optimize on-demand vs provisioned billing)
        - SLA monitoring (availability and performance metrics)
    
    Note: Metrics are aggregated in 1-hour periods for the specified time range.
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common DynamoDB metrics
        metric_names = [
            'ConsumedReadCapacityUnits', 'ConsumedWriteCapacityUnits',
            'ReadThrottleEvents', 'WriteThrottleEvents',
            'SuccessfulRequestLatency', 'UserErrors', 'SystemErrors'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/DynamoDB',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'TableName',
                        'Value': table_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "table_name": table_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "table_name": table_name})


@tool
def describe_dynamodb_streams(table_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Retrieve DynamoDB Streams configuration for real-time data processing analysis.
    
    This tool examines the DynamoDB Streams setup for a table to identify
    stream-related issues, configuration problems, or missing stream capabilities.
    Essential for diagnosing real-time processing and event-driven architecture issues.
    
    Args:
        table_name: The DynamoDB table name (e.g., "users", "orders-prod")
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - table_name: Name of the table
        - stream_enabled: Whether streams are enabled (true/false)
        - stream_view_type: Type of stream (KEYS_ONLY, NEW_IMAGE, OLD_IMAGE, NEW_AND_OLD_IMAGES)
        - latest_stream_label: Latest stream label
        - latest_stream_arn: ARN of the latest stream
        - stream_arn: Full stream ARN (if enabled)
        - stream_status: Stream status (ENABLED, ENABLING, DISABLED, DISABLING)
        - creation_request_id: ID of the stream creation request
        - shards: Array of stream shard information
    
    Common Stream Issues:
        - Streams disabled: Table doesn't have streams enabled
        - Wrong view type: Stream view type doesn't match application needs
        - Stream errors: Stream processing failures or errors
        - Missing consumers: No Lambda functions or Kinesis consumers
        - Shard issues: Stream shard processing problems
    
    Use Cases:
        - Real-time processing verification (check stream configuration)
        - Event-driven architecture debugging (verify stream setup)
        - Data replication issues (check stream status and shards)
        - Lambda trigger problems (verify stream ARN and configuration)
        - Kinesis integration issues (check stream consumer setup)
        - Data consistency analysis (verify stream view type)
    
    Note: Stream information is retrieved from the table configuration and stream details.
    """
    import boto3
    
    try:
        client = boto3.client('dynamodb', region_name=region)
        response = client.describe_table(TableName=table_name)
        table = response['Table']
        
        stream_spec = table.get('StreamSpecification', {})
        
        config = {
            "table_name": table_name,
            "stream_enabled": stream_spec.get('StreamEnabled', False),
            "stream_view_type": stream_spec.get('StreamViewType'),
            "latest_stream_label": table.get('LatestStreamLabel'),
            "latest_stream_arn": table.get('LatestStreamArn')
        }
        
        # If streams are enabled, get more details
        if config["stream_enabled"] and config["latest_stream_arn"]:
            try:
                streams_client = boto3.client('dynamodbstreams', region_name=region)
                stream_response = streams_client.describe_stream(StreamArn=config["latest_stream_arn"])
                stream = stream_response['StreamDescription']
                
                config.update({
                    "stream_arn": stream.get('StreamArn'),
                    "stream_status": stream.get('StreamStatus'),
                    "creation_request_id": stream.get('CreationRequestId'),
                    "shards": [
                        {
                            "shard_id": shard.get('ShardId'),
                            "sequence_number_range": shard.get('SequenceNumberRange', {}),
                            "parent_shard_id": shard.get('ParentShardId')
                        }
                        for shard in stream.get('Shards', [])
                    ]
                })
            except Exception as stream_error:
                config["stream_error"] = str(stream_error)
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "table_name": table_name})


@tool
def list_dynamodb_tables(region: str = None) -> str:
    region = region or get_region()
    """
    List all DynamoDB tables in the region for discovery and inventory purposes.
    
    This tool provides a comprehensive list of all DynamoDB tables in the specified
    region, useful for discovery, inventory management, and identifying tables
    that might be related to an investigation.
    
    Args:
        region: AWS region (default: from environment config)
    
    Returns:
        JSON string containing:
        - region: AWS region searched
        - table_count: Total number of tables found
        - tables: Array of table names
    
    Use Cases:
        - Table discovery (find tables related to an investigation)
        - Inventory management (audit all tables in a region)
        - Cross-table analysis (identify related tables)
        - Security auditing (review all table access)
        - Cost analysis (identify all billable tables)
        - Migration planning (catalog tables for migration)
    
    Note: This tool only lists table names, not their configurations or metrics.
    """
    import boto3
    
    try:
        client = boto3.client('dynamodb', region_name=region)
        response = client.list_tables()
        
        tables = response.get('TableNames', [])
        
        config = {
            "region": region,
            "table_count": len(tables),
            "tables": tables
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "region": region})
