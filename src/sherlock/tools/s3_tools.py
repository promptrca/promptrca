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
def get_s3_bucket_config(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get S3 bucket configuration and properties.
    
    Args:
        bucket_name: The S3 bucket name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with bucket configuration
    """
    import boto3
    
    try:
        client = boto3.client('s3', region_name=region)
        
        # Get bucket location
        location_response = client.get_bucket_location(Bucket=bucket_name)
        bucket_region = location_response.get('LocationConstraint', 'us-east-1')
        
        # Get bucket versioning
        try:
            versioning_response = client.get_bucket_versioning(Bucket=bucket_name)
            versioning_status = versioning_response.get('Status', 'Suspended')
        except:
            versioning_status = 'Unknown'
        
        # Get bucket encryption
        try:
            encryption_response = client.get_bucket_encryption(Bucket=bucket_name)
            encryption_rules = encryption_response.get('ServerSideEncryptionConfiguration', {}).get('Rules', [])
        except:
            encryption_rules = []
        
        # Get bucket lifecycle
        try:
            lifecycle_response = client.get_bucket_lifecycle_configuration(Bucket=bucket_name)
            lifecycle_rules = lifecycle_response.get('Rules', [])
        except:
            lifecycle_rules = []
        
        # Get bucket notification configuration
        try:
            notification_response = client.get_bucket_notification_configuration(Bucket=bucket_name)
            notifications = notification_response
        except:
            notifications = {}
        
        config = {
            "bucket_name": bucket_name,
            "region": bucket_region,
            "versioning_status": versioning_status,
            "encryption_rules": encryption_rules,
            "lifecycle_rules": lifecycle_rules,
            "notifications": notifications
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "bucket_name": bucket_name})


@tool
def get_s3_bucket_metrics(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch metrics for an S3 bucket.
    
    Args:
        bucket_name: The S3 bucket name
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with bucket metrics
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common S3 metrics
        metric_names = [
            'BucketSizeBytes', 'NumberOfObjects', 'AllRequests',
            'GetRequests', 'PutRequests', 'DeleteRequests', 'HeadRequests'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/S3',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'BucketName',
                        'Value': bucket_name
                    },
                    {
                        'Name': 'StorageType',
                        'Value': 'StandardStorage'
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "bucket_name": bucket_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "bucket_name": bucket_name})


@tool
def list_s3_bucket_objects(list: str, region: str = None) -> str:
    region = region or get_region()
    """
    List S3 bucket objects (for debugging purposes).
    
    Args:
        bucket_name: The S3 bucket name
        prefix: Object key prefix to filter by
        max_keys: Maximum number of objects to return (default: 100)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with object list
    """
    import boto3
    
    try:
        client = boto3.client('s3', region_name=region)
        
        kwargs = {
            'Bucket': bucket_name,
            'MaxKeys': max_keys
        }
        
        if prefix:
            kwargs['Prefix'] = prefix
        
        response = client.list_objects_v2(**kwargs)
        
        objects = response.get('Contents', [])
        
        config = {
            "bucket_name": bucket_name,
            "prefix": prefix,
            "object_count": len(objects),
            "is_truncated": response.get('IsTruncated', False),
            "objects": [
                {
                    "key": obj.get('Key'),
                    "size": obj.get('Size'),
                    "last_modified": str(obj.get('LastModified')),
                    "storage_class": obj.get('StorageClass'),
                    "etag": obj.get('ETag')
                }
                for obj in objects
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "bucket_name": bucket_name, "prefix": prefix})


@tool
def get_s3_bucket_policy(get: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get S3 bucket policy.
    
    Args:
        bucket_name: The S3 bucket name
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with bucket policy
    """
    import boto3
    
    try:
        client = boto3.client('s3', region_name=region)
        
        response = client.get_bucket_policy(Bucket=bucket_name)
        policy = response.get('Policy')
        
        # Parse policy if it's a string
        if isinstance(policy, str):
            policy_doc = json.loads(policy)
        else:
            policy_doc = policy
        
        config = {
            "bucket_name": bucket_name,
            "policy": policy_doc
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "bucket_name": bucket_name})
