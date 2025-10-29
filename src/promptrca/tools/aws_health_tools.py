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

AWS Health API tools for checking service status and account-specific events.
"""

from strands import tool
import json
from datetime import datetime, timedelta
from ..context import get_aws_client
from ..utils import get_logger

logger = get_logger(__name__)


@tool
def check_aws_service_health(service_name: str, region: str = None) -> str:
    """
    Check AWS Service Health Dashboard for known issues.
    This should be called FIRST in any investigation to rule out AWS-side issues.
    
    Args:
        service_name: AWS service code (e.g., 'LAMBDA', 'APIGATEWAY', 'DYNAMODB', 'STATES')
        region: AWS region (e.g., 'us-east-1'). If None, checks all regions.
    
    Returns:
        JSON with active service events affecting the service
    
    Example:
        check_aws_service_health('LAMBDA', 'us-east-1')
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        # AWS Health API is only available in us-east-1
        health_client = aws_client.get_client('health', region_name='us-east-1')
        
        # Build filter
        event_filter = {
            'services': [service_name],
            'eventStatusCodes': ['open', 'upcoming']
        }
        
        if region:
            event_filter['regions'] = [region]
        
        # Get active events for the service
        response = health_client.describe_events(filter=event_filter)
        
        events = response.get('events', [])
        
        if events:
            logger.info(f"⚠️ AWS Service Health: {len(events)} active events for {service_name}")
            return json.dumps({
                "aws_service_issue_detected": True,
                "service": service_name,
                "region": region or "all_regions",
                "active_events_count": len(events),
                "active_events": [
                    {
                        "arn": e.get('arn'),
                        "event_type": e.get('eventTypeCode'),
                        "status": e.get('statusCode'),
                        "start_time": str(e.get('startTime')),
                        "region": e.get('region'),
                        "description": e.get('eventTypeCategory'),
                        "affected_scope": e.get('eventScopeCode')
                    }
                    for e in events
                ]
            }, indent=2)
        
        logger.info(f"✅ AWS Service Health: No active events for {service_name}")
        return json.dumps({
            "aws_service_issue_detected": False,
            "service": service_name,
            "region": region or "all_regions",
            "message": "No active AWS service events detected"
        }, indent=2)
        
    except Exception as e:
        logger.warning(f"Failed to check AWS Health for {service_name}: {e}")
        return json.dumps({
            "error": str(e),
            "service": service_name,
            "note": "AWS Health API requires Business or Enterprise support plan"
        }, indent=2)


@tool
def get_account_health_events(hours_back: int = 24) -> str:
    """
    Get all AWS Health events affecting this account in the last N hours.
    Useful for identifying account-wide issues or multiple service problems.
    
    Args:
        hours_back: How many hours to look back (default: 24)
    
    Returns:
        JSON with account-specific health events
    
    Example:
        get_account_health_events(24)
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        health_client = aws_client.get_client('health', region_name='us-east-1')
        
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        response = health_client.describe_events(
            filter={
                'eventStatusCodes': ['open', 'closed'],
                'startTimes': [{'from': start_time}]
            }
        )
        
        events = response.get('events', [])
        
        # Group by service
        events_by_service = {}
        for event in events:
            service = event.get('service', 'unknown')
            if service not in events_by_service:
                events_by_service[service] = []
            events_by_service[service].append(event)
        
        logger.info(f"📊 AWS Health: Found {len(events)} events in last {hours_back} hours")
        
        return json.dumps({
            "total_events": len(events),
            "time_range_hours": hours_back,
            "services_affected": list(events_by_service.keys()),
            "events_by_service": {
                service: len(event_list)
                for service, event_list in events_by_service.items()
            },
            "events": [
                {
                    "arn": e.get('arn'),
                    "service": e.get('service'),
                    "event_type": e.get('eventTypeCode'),
                    "region": e.get('region'),
                    "status": e.get('statusCode'),
                    "start_time": str(e.get('startTime')),
                    "end_time": str(e.get('endTime')) if e.get('endTime') else None,
                    "category": e.get('eventTypeCategory')
                }
                for e in events
            ]
        }, indent=2)
        
    except Exception as e:
        logger.warning(f"Failed to get account health events: {e}")
        return json.dumps({
            "error": str(e),
            "note": "AWS Health API requires Business or Enterprise support plan"
        }, indent=2)


@tool
def check_service_quota_status(service_code: str, quota_code: str = None) -> str:
    """
    Check Service Quotas to identify if limits are being hit.
    Common cause of AWS issues is hitting service quotas.
    
    Args:
        service_code: AWS service code (e.g., 'lambda', 'apigateway', 'dynamodb')
        quota_code: Specific quota code (optional). If None, returns all quotas.
    
    Returns:
        JSON with quota information and usage
    
    Example:
        check_service_quota_status('lambda', 'L-B99A9384')  # Concurrent executions
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        quotas_client = aws_client.get_client('service-quotas')
        
        if quota_code:
            # Get specific quota
            response = quotas_client.get_service_quota(
                ServiceCode=service_code,
                QuotaCode=quota_code
            )
            quota = response.get('Quota', {})
            
            return json.dumps({
                "service": service_code,
                "quota_name": quota.get('QuotaName'),
                "quota_code": quota_code,
                "value": quota.get('Value'),
                "unit": quota.get('Unit'),
                "adjustable": quota.get('Adjustable'),
                "global_quota": quota.get('GlobalQuota')
            }, indent=2)
        else:
            # List common quotas for the service
            response = quotas_client.list_service_quotas(
                ServiceCode=service_code,
                MaxResults=20
            )
            
            quotas = response.get('Quotas', [])
            
            return json.dumps({
                "service": service_code,
                "total_quotas": len(quotas),
                "quotas": [
                    {
                        "name": q.get('QuotaName'),
                        "code": q.get('QuotaCode'),
                        "value": q.get('Value'),
                        "unit": q.get('Unit'),
                        "adjustable": q.get('Adjustable')
                    }
                    for q in quotas[:10]  # Top 10
                ]
            }, indent=2)
            
    except Exception as e:
        logger.warning(f"Failed to check service quotas: {e}")
        return json.dumps({
            "error": str(e),
            "service": service_code
        }, indent=2)
