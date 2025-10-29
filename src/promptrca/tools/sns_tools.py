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
from typing import Dict, Any, Optional
import json
from ..context import get_aws_client


@tool
def get_sns_topic_config(topic_arn: str) -> str:
    """
    Get SNS topic configuration and attributes.
    
    Args:
        topic_arn: The SNS topic ARN
    
    Returns:
        JSON string with topic configuration
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('sns')
        
        response = client.get_topic_attributes(TopicArn=topic_arn)
        attributes = response.get('Attributes', {})
        
        config = {
            "topic_arn": topic_arn,
            "topic_name": topic_arn.split(':')[-1],
            "display_name": attributes.get('DisplayName', ''),
            "owner": attributes.get('Owner', ''),
            "policy": json.loads(attributes.get('Policy', '{}')),
            "delivery_policy": json.loads(attributes.get('DeliveryPolicy', '{}')),
            "effective_delivery_policy": json.loads(attributes.get('EffectiveDeliveryPolicy', '{}')),
            "kms_master_key_id": attributes.get('KmsMasterKeyId', ''),
            "fifotopic": attributes.get('FifoTopic', 'false').lower() == 'true',
            "content_based_deduplication": attributes.get('ContentBasedDeduplication', 'false').lower() == 'true',
            "created_timestamp": attributes.get('CreatedTimestamp', ''),
            "subscriptions_confirmed": int(attributes.get('SubscriptionsConfirmed', 0)),
            "subscriptions_pending": int(attributes.get('SubscriptionsPending', 0)),
            "subscriptions_deleted": int(attributes.get('SubscriptionsDeleted', 0))
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "topic_arn": topic_arn})


@tool
def get_sns_topic_metrics(topic_name: str, hours_back: int = 24) -> str:
    """
    Get CloudWatch metrics for an SNS topic.
    
    Args:
        topic_name: The SNS topic name (without ARN)
        hours_back: Number of hours to look back (default: 24)
    
    Returns:
        JSON string with topic metrics
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
        
        # Common SNS metrics
        metric_names = [
            'NumberOfMessagesPublished', 'NumberOfMessagesDelivered',
            'NumberOfNotificationsFailed', 'NumberOfNotificationsDelivered',
            'NumberOfNotificationsFailedToRedriveToDlq', 'PublishSize'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/SNS',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'TopicName',
                        'Value': topic_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "topic_name": topic_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "topic_name": topic_name})


@tool
def get_sns_subscriptions(topic_arn: str) -> str:
    """
    Get SNS topic subscriptions.
    
    Args:
        topic_arn: The SNS topic ARN
    
    Returns:
        JSON string with subscription details
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('sns')
        
        response = client.list_subscriptions_by_topic(TopicArn=topic_arn)
        subscriptions = response.get('Subscriptions', [])
        
        config = {
            "topic_arn": topic_arn,
            "subscription_count": len(subscriptions),
            "subscriptions": [
                {
                    "subscription_arn": sub.get('SubscriptionArn'),
                    "protocol": sub.get('Protocol'),
                    "endpoint": sub.get('Endpoint'),
                    "owner": sub.get('Owner'),
                    "topic_arn": sub.get('TopicArn')
                }
                for sub in subscriptions
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "topic_arn": topic_arn})


@tool
def list_sns_topics(list: str) -> str:
    """
    List SNS topics in the region.
    
    Args:
    
    Returns:
        JSON string with topic list
    """
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('sns')
        
        response = client.list_topics()
        topics = response.get('Topics', [])
        
        config = {
            "region": region,
            "topic_count": len(topics),
            "topics": [
                {
                    "topic_arn": topic.get('TopicArn'),
                    "topic_name": topic.get('TopicArn', '').split(':')[-1]
                }
                for topic in topics
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "region": region})
