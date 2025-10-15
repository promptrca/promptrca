#!/usr/bin/env python3
"""
Sherlock Core - AI-powered root cause analysis for AWS infrastructure
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

"""

from strands import tool
from typing import Dict, Any
import json
from ..utils.config import get_region


@tool
def get_dynamodb_table_config(table_name: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get DynamoDB table configuration and status.
    
    Args:
        table_name: The DynamoDB table name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with table configuration
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
    Get CloudWatch metrics for a DynamoDB table.
    
    Args:
        table_name: The DynamoDB table name
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with table metrics
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
def describe_dynamodb_streams(describe: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get DynamoDB streams configuration for a table.
    
    Args:
        table_name: The DynamoDB table name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with streams configuration
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
def list_dynamodb_tables(list: str, region: str = None) -> str:
    region = region or get_region()
    """
    List all DynamoDB tables in the region.
    
    Args:
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with table list
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
