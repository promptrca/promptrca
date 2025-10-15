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


@tool
def get_eventbridge_rule_config(rule_name: str, region: str = "eu-west-1") -> str:
    """
    Get EventBridge rule configuration.
    
    Args:
        rule_name: The EventBridge rule name
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with rule configuration
    """
    import boto3
    
    try:
        client = boto3.client('events', region_name=region)
        
        response = client.describe_rule(Name=rule_name)
        rule = response
        
        config = {
            "rule_name": rule.get('Name'),
            "rule_arn": rule.get('Arn'),
            "description": rule.get('Description', ''),
            "event_pattern": rule.get('EventPattern'),
            "state": rule.get('State'),
            "schedule_expression": rule.get('ScheduleExpression'),
            "role_arn": rule.get('RoleArn'),
            "managed_by": rule.get('ManagedBy'),
            "created_by": rule.get('CreatedBy'),
            "event_bus_name": rule.get('EventBusName', 'default')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "rule_name": rule_name})


@tool
def get_eventbridge_targets(rule_name: str, region: str = "eu-west-1") -> str:
    """
    Get EventBridge rule targets.
    
    Args:
        rule_name: The EventBridge rule name
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with target details
    """
    import boto3
    
    try:
        client = boto3.client('events', region_name=region)
        
        response = client.list_targets_by_rule(Rule=rule_name)
        targets = response.get('Targets', [])
        
        config = {
            "rule_name": rule_name,
            "target_count": len(targets),
            "targets": [
                {
                    "id": target.get('Id'),
                    "arn": target.get('Arn'),
                    "role_arn": target.get('RoleArn'),
                    "input": target.get('Input'),
                    "input_path": target.get('InputPath'),
                    "input_transformer": target.get('InputTransformer'),
                    "kinesis_parameters": target.get('KinesisParameters'),
                    "run_command_parameters": target.get('RunCommandParameters'),
                    "ecs_parameters": target.get('EcsParameters'),
                    "batch_parameters": target.get('BatchParameters'),
                    "sqs_parameters": target.get('SqsParameters'),
                    "http_parameters": target.get('HttpParameters'),
                    "redshift_data_parameters": target.get('RedshiftDataParameters'),
                    "sage_maker_pipeline_parameters": target.get('SageMakerPipelineParameters'),
                    "dead_letter_config": target.get('DeadLetterConfig'),
                    "retry_policy": target.get('RetryPolicy')
                }
                for target in targets
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "rule_name": rule_name})


@tool
def get_eventbridge_metrics(rule_name: str, hours_back: int = 24, region: str = "eu-west-1") -> str:
    """
    Get CloudWatch metrics for an EventBridge rule.
    
    Args:
        rule_name: The EventBridge rule name
        hours_back: Number of hours to look back (default: 24)
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with rule metrics
    """
    import boto3
    from datetime import datetime, timedelta
    
    try:
        client = boto3.client('cloudwatch', region_name=region)
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours_back)
        
        metrics = {}
        
        # Common EventBridge metrics
        metric_names = [
            'SuccessfulInvocations', 'FailedInvocations', 'ThrottledRules',
            'MatchedEvents', 'TriggeredRules'
        ]
        
        for metric_name in metric_names:
            response = client.get_metric_statistics(
                Namespace='AWS/Events',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'RuleName',
                        'Value': rule_name
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour periods
                Statistics=['Sum', 'Average', 'Maximum']
            )
            
            metrics[metric_name] = response.get('Datapoints', [])
        
        config = {
            "rule_name": rule_name,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours_back": hours_back
            },
            "metrics": metrics
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "rule_name": rule_name})


@tool
def list_eventbridge_rules(region: str = "eu-west-1") -> str:
    """
    List EventBridge rules in the region.
    
    Args:
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with rule list
    """
    import boto3
    
    try:
        client = boto3.client('events', region_name=region)
        
        response = client.list_rules()
        rules = response.get('Rules', [])
        
        config = {
            "region": region,
            "rule_count": len(rules),
            "rules": [
                {
                    "rule_name": rule.get('Name'),
                    "rule_arn": rule.get('Arn'),
                    "state": rule.get('State'),
                    "description": rule.get('Description', ''),
                    "schedule_expression": rule.get('ScheduleExpression'),
                    "event_pattern": rule.get('EventPattern')
                }
                for rule in rules
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "region": region})


@tool
def get_eventbridge_bus_config(event_bus_name: str = "default", region: str = "eu-west-1") -> str:
    """
    Get EventBridge event bus configuration.
    
    Args:
        event_bus_name: The EventBridge event bus name (default: "default")
        region: AWS region (default: eu-west-1)
    
    Returns:
        JSON string with event bus configuration
    """
    import boto3
    
    try:
        client = boto3.client('events', region_name=region)
        
        response = client.describe_event_bus(Name=event_bus_name)
        
        config = {
            "event_bus_name": response.get('Name'),
            "event_bus_arn": response.get('Arn'),
            "policy": response.get('Policy'),
            "description": response.get('Description', ''),
            "created_by": response.get('CreatedBy', ''),
            "creation_time": str(response.get('CreationTime', ''))
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "event_bus_name": event_bus_name})
