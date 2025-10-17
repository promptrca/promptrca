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

# Lambda tools
from .lambda_tools import (
    get_lambda_config,
    get_lambda_logs,
    get_lambda_metrics,
    get_lambda_layers
)

# API Gateway tools
from .apigateway_tools import (
    get_api_gateway_stage_config,
    get_apigateway_logs,
    resolve_api_gateway_id,
    get_api_gateway_metrics
)

# Step Functions tools
from .stepfunctions_tools import (
    get_stepfunctions_definition,
    get_stepfunctions_logs,
    get_stepfunctions_execution_details,
    get_stepfunctions_metrics
)

# IAM tools
from .iam_tools import (
    get_iam_role_config,
    get_iam_policy_document,
    simulate_iam_policy,
    get_iam_user_policies
)

# X-Ray tools
from .xray_tools import (
    get_xray_trace,
    get_all_resources_from_trace,
    get_xray_service_graph,
    get_xray_trace_summaries
)

# CloudWatch tools
from .cloudwatch_tools import (
    get_cloudwatch_logs,
    query_logs_by_trace_id,
    get_cloudwatch_metrics,
    get_cloudwatch_alarms,
    list_cloudwatch_dashboards
)

# DynamoDB tools
from .dynamodb_tools import (
    get_dynamodb_table_config,
    get_dynamodb_table_metrics,
    describe_dynamodb_streams,
    list_dynamodb_tables
)

# S3 tools
from .s3_tools import (
    get_s3_bucket_config,
    get_s3_bucket_metrics,
    list_s3_bucket_objects,
    get_s3_bucket_policy
)

# SQS tools
from .sqs_tools import (
    get_sqs_queue_config,
    get_sqs_queue_metrics,
    get_sqs_dead_letter_queue,
    list_sqs_queues
)

# SNS tools
from .sns_tools import (
    get_sns_topic_config,
    get_sns_topic_metrics,
    get_sns_subscriptions,
    list_sns_topics
)

# EventBridge tools
from .eventbridge_tools import (
    get_eventbridge_rule_config,
    get_eventbridge_targets,
    get_eventbridge_metrics,
    list_eventbridge_rules,
    get_eventbridge_bus_config
)

# VPC/Network tools
from .vpc_tools import (
    get_vpc_config,
    get_subnet_config,
    get_security_group_config,
    get_network_interface_config,
    get_nat_gateway_config,
    get_internet_gateway_config
)

# AWS Knowledge MCP tools (optional)
from .aws_knowledge_tools import (
    search_aws_documentation,
    read_aws_documentation,
    get_aws_documentation_recommendations,
    list_aws_regions,
    get_service_regional_availability
)

# AWS API MCP fallback tools (optional)
from .aws_mcp_tools import (
    aws_mcp_read,
    aws_mcp_suggest_commands
)

__all__ = [
    # Lambda tools
    'get_lambda_config',
    'get_lambda_logs',
    'get_lambda_metrics',
    'get_lambda_layers',
    
    # API Gateway tools
    'get_api_gateway_stage_config',
    'get_apigateway_logs',
    'resolve_api_gateway_id',
    'get_api_gateway_metrics',
    
    # Step Functions tools
    'get_stepfunctions_definition',
    'get_stepfunctions_logs',
    'get_stepfunctions_execution_details',
    'get_stepfunctions_metrics',
    
    # IAM tools
    'get_iam_role_config',
    'get_iam_policy_document',
    'simulate_iam_policy',
    'get_iam_user_policies',
    
    # X-Ray tools
    'get_xray_trace',
    'get_all_resources_from_trace',
    'get_xray_service_graph',
    'get_xray_trace_summaries',
    
    # CloudWatch tools
    'get_cloudwatch_logs',
    'query_logs_by_trace_id',
    'get_cloudwatch_metrics',
    'get_cloudwatch_alarms',
    'list_cloudwatch_dashboards',
    
    # DynamoDB tools
    'get_dynamodb_table_config',
    'get_dynamodb_table_metrics',
    'describe_dynamodb_streams',
    'list_dynamodb_tables',
    
    # S3 tools
    'get_s3_bucket_config',
    'get_s3_bucket_metrics',
    'list_s3_bucket_objects',
    'get_s3_bucket_policy',
    
    # SQS tools
    'get_sqs_queue_config',
    'get_sqs_queue_metrics',
    'get_sqs_dead_letter_queue',
    'list_sqs_queues',
    
    # SNS tools
    'get_sns_topic_config',
    'get_sns_topic_metrics',
    'get_sns_subscriptions',
    'list_sns_topics',
    
    # EventBridge tools
    'get_eventbridge_rule_config',
    'get_eventbridge_targets',
    'get_eventbridge_metrics',
    'list_eventbridge_rules',
    'get_eventbridge_bus_config',
    
    # VPC/Network tools
    'get_vpc_config',
    'get_subnet_config',
    'get_security_group_config',
    'get_network_interface_config',
    'get_nat_gateway_config',
    'get_internet_gateway_config',
    
    # AWS Knowledge MCP tools
    'search_aws_documentation',
    'read_aws_documentation',
    'get_aws_documentation_recommendations',
    'list_aws_regions',
    'get_service_regional_availability',
    
    # AWS API MCP fallback tools
    'aws_mcp_read',
    'aws_mcp_suggest_commands'
]

