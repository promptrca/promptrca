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
def get_sqs_queue_config(queue_url: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get SQS queue configuration and attributes.
    
    Args:
        queue_url: The SQS queue URL
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with queue configuration
    """
    import boto3
    
    try:
        client = boto3.client('sqs', region_name=region)
        
        response = client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['All']
        )
        
        attributes = response.get('Attributes', {})
        
        config = {
            "queue_url": queue_url,
            "queue_arn": attributes.get('QueueArn'),
            "visibility_timeout_seconds": int(attributes.get('VisibilityTimeoutSeconds', 0)),
            "message_retention_period": int(attributes.get('MessageRetentionPeriod', 0)),
            "max_receive_count": int(attributes.get('RedrivePolicy', {}).get('maxReceiveCount', 0)) if attributes.get('RedrivePolicy') else None,
            "dead_letter_queue_arn": attributes.get('RedrivePolicy', {}).get('deadLetterTargetArn') if attributes.get('RedrivePolicy') else None,
            "delay_seconds": int(attributes.get('DelaySeconds', 0)),
            "receive_message_wait_time_seconds": int(attributes.get('ReceiveMessageWaitTimeSeconds', 0)),
            "created_timestamp": int(attributes.get('CreatedTimestamp', 0)),
            "last_modified_timestamp": int(attributes.get('LastModifiedTimestamp', 0)),
            "approximate_number_of_messages": int(attributes.get('ApproximateNumberOfMessages', 0)),
            "approximate_number_of_messages_not_visible": int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0)),
            "approximate_number_of_messages_delayed": int(attributes.get('ApproximateNumberOfMessagesDelayed', 0))
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "queue_url": queue_url})


@tool
def get_sqs_queue_metrics(queue_name: str, hours_back: int = 24, region: str = None) -> str:
    region = region or get_region()
    """
    Get CloudWatch metrics for an SQS queue.
    
    Args:
        queue_name: The SQS queue name (without URL)
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with queue metrics
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common SQS metrics
        metric_names = [
            'NumberOfMessagesSent', 'NumberOfMessagesReceived', 'NumberOfMessagesDeleted',
            'NumberOfEmptyReceives', 'NumberOfMessagesVisible', 'NumberOfMessagesNotVisible',
            'ApproximateAgeOfOldestMessage', 'SentMessageSize'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/SQS',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'QueueName',
                        'Value': queue_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "queue_name": queue_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "queue_name": queue_name})


@tool
def get_sqs_dead_letter_queue(queue_url: str, region: str = None) -> str:
    region = region or get_region()
    """
    Get SQS dead letter queue configuration.
    
    Args:
        queue_url: The SQS queue URL
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with DLQ configuration
    """
    import boto3
    
    try:
        client = boto3.client('sqs', region_name=region)
        
        response = client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['RedrivePolicy']
        )
        
        redrive_policy = response.get('Attributes', {}).get('RedrivePolicy')
        
        if redrive_policy:
            # Parse redrive policy if it's a string
            if isinstance(redrive_policy, str):
                policy_doc = json.loads(redrive_policy)
            else:
                policy_doc = redrive_policy
            
            dlq_arn = policy_doc.get('deadLetterTargetArn', '')
            max_receive_count = policy_doc.get('maxReceiveCount', 0)
            
            # Get DLQ details if it exists
            dlq_config = {}
            if dlq_arn:
                try:
                    # Extract queue name from ARN
                    queue_name = dlq_arn.split(':')[-1]
                    dlq_response = client.get_queue_attributes(
                        QueueUrl=f"https://sqs.{region}.amazonaws.com/{dlq_arn.split(':')[4]}/{queue_name}",
                        AttributeNames=['All']
                    )
                    dlq_attributes = dlq_response.get('Attributes', {})
                    
                    dlq_config = {
                        "dlq_arn": dlq_arn,
                        "dlq_url": f"https://sqs.{region}.amazonaws.com/{dlq_arn.split(':')[4]}/{queue_name}",
                        "dlq_message_count": int(dlq_attributes.get('ApproximateNumberOfMessages', 0)),
                        "dlq_not_visible_count": int(dlq_attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
                    }
                except Exception as dlq_error:
                    dlq_config = {
                        "dlq_arn": dlq_arn,
                        "dlq_error": str(dlq_error)
                    }
            
            config = {
                "queue_url": queue_url,
                "has_dlq": True,
                "max_receive_count": max_receive_count,
                "dlq_config": dlq_config
            }
        else:
            config = {
                "queue_url": queue_url,
                "has_dlq": False,
                "message": "No dead letter queue configured"
            }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "queue_url": queue_url})


@tool
def list_sqs_queues(list: str, region: str = None) -> str:
    region = region or get_region()
    """
    List SQS queues in the region.
    
    Args:
        prefix: Optional prefix to filter queue names
        region: AWS region (default: from environment)
    
    Returns:
        JSON string with queue list
    """
    import boto3
    
    try:
        client = boto3.client('sqs', region_name=region)
        
        kwargs = {}
        if prefix:
            kwargs['QueueNamePrefix'] = prefix
        
        response = client.list_queues(**kwargs)
        
        queues = response.get('QueueUrls', [])
        
        config = {
            "region": region,
            "prefix": prefix,
            "queue_count": len(queues),
            "queues": queues
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "region": region, "prefix": prefix})
