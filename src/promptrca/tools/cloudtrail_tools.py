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

CloudTrail tools for tracking configuration changes and correlating with incidents.
"""

from strands import tool
import json
from datetime import datetime, timedelta
from ..context import get_aws_client
from ..utils import get_logger

logger = get_logger(__name__)


@tool
def get_recent_cloudtrail_events(
    resource_name: str,
    hours_back: int = 24,
    event_category: str = "Management"
) -> str:
    """
    Get recent CloudTrail events for a resource to identify configuration changes.
    Essential for "what changed?" analysis in RCA.
    
    Args:
        resource_name: Resource name (e.g., Lambda function name, API Gateway ID)
        hours_back: How many hours to look back (default: 24)
        event_category: Event category - 'Management' for config changes, 'Data' for data events
    
    Returns:
        JSON with recent CloudTrail events showing configuration changes
    
    Example:
        get_recent_cloudtrail_events('my-lambda-function', 24)
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        cloudtrail = aws_client.get_client('cloudtrail')
        
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        # Lookup events for the resource
        response = cloudtrail.lookup_events(
            LookupAttributes=[
                {
                    'AttributeKey': 'ResourceName',
                    'AttributeValue': resource_name
                }
            ],
            StartTime=start_time,
            MaxResults=50
        )
        
        events = response.get('Events', [])
        
        # Filter for write operations (configuration changes)
        write_events = [
            e for e in events 
            if e.get('ReadOnly') == 'false' or 'Delete' in e.get('EventName', '')
        ]
        
        logger.info(f"📋 CloudTrail: Found {len(write_events)} configuration changes for {resource_name}")
        
        return json.dumps({
            "resource_name": resource_name,
            "total_events": len(write_events),
            "time_range_hours": hours_back,
            "configuration_changes_detected": len(write_events) > 0,
            "events": [
                {
                    "event_time": str(e.get('EventTime')),
                    "event_name": e.get('EventName'),
                    "username": e.get('Username'),
                    "event_source": e.get('EventSource'),
                    "access_key_id": e.get('AccessKeyId', 'N/A'),
                    "resources": [
                        {
                            "type": r.get('ResourceType'),
                            "name": r.get('ResourceName')
                        }
                        for r in e.get('Resources', [])
                    ],
                    "request_parameters": json.loads(e.get('CloudTrailEvent', '{}')).get('requestParameters', {}),
                    "error_code": json.loads(e.get('CloudTrailEvent', '{}')).get('errorCode'),
                    "error_message": json.loads(e.get('CloudTrailEvent', '{}')).get('errorMessage')
                }
                for e in write_events[:15]  # Top 15 most recent
            ]
        }, indent=2)
        
    except Exception as e:
        logger.warning(f"Failed to get CloudTrail events for {resource_name}: {e}")
        return json.dumps({
            "error": str(e),
            "resource_name": resource_name,
            "note": "CloudTrail may not be enabled or resource name may not match"
        }, indent=2)


@tool
def find_correlated_changes(
    incident_time: str,
    window_minutes: int = 30,
    services: str = "lambda,apigateway,iam,dynamodb"
) -> str:
    """
    Find all AWS configuration changes around the incident time.
    Critical for identifying what changed before the incident started.
    
    Args:
        incident_time: ISO timestamp of incident (e.g., "2025-01-20T10:30:00Z")
        window_minutes: Time window BEFORE incident to check (default: 30)
        services: Comma-separated AWS services to check (default: lambda,apigateway,iam,dynamodb)
    
    Returns:
        JSON with correlated configuration changes grouped by service
    
    Example:
        find_correlated_changes("2025-01-20T10:30:00Z", 30, "lambda,iam")
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        cloudtrail = aws_client.get_client('cloudtrail')
        
        # Parse incident time
        incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        start_time = incident_dt - timedelta(minutes=window_minutes)
        
        # Get all write events in the time window
        response = cloudtrail.lookup_events(
            StartTime=start_time,
            EndTime=incident_dt,
            MaxResults=50
        )
        
        events = response.get('Events', [])
        
        # Filter for write operations only
        write_events = [
            e for e in events
            if e.get('ReadOnly') == 'false'
        ]
        
        # Group by service
        service_list = [s.strip().lower() for s in services.split(',')]
        service_events = {}
        
        for event in write_events:
            event_source = event.get('EventSource', '').split('.')[0]
            if event_source in service_list:
                if event_source not in service_events:
                    service_events[event_source] = []
                
                cloud_trail_event = json.loads(event.get('CloudTrailEvent', '{}'))
                
                service_events[event_source].append({
                    "event_time": str(event.get('EventTime')),
                    "event_name": event.get('EventName'),
                    "username": event.get('Username'),
                    "minutes_before_incident": int((incident_dt - event.get('EventTime')).total_seconds() / 60),
                    "resources": [
                        {
                            "type": r.get('ResourceType'),
                            "name": r.get('ResourceName')
                        }
                        for r in event.get('Resources', [])
                    ],
                    "request_parameters": cloud_trail_event.get('requestParameters', {}),
                    "error_code": cloud_trail_event.get('errorCode')
                })
        
        logger.info(f"🔍 CloudTrail: Found {len(write_events)} changes in {window_minutes}min before incident")
        
        return json.dumps({
            "incident_time": incident_time,
            "window_minutes": window_minutes,
            "total_changes": len(write_events),
            "services_with_changes": list(service_events.keys()),
            "correlation_detected": len(write_events) > 0,
            "changes_by_service": service_events,
            "analysis": {
                "high_risk_changes": [
                    event for events in service_events.values() 
                    for event in events 
                    if event['minutes_before_incident'] <= 10
                ],
                "deployment_detected": any(
                    'Update' in event['event_name'] or 'Put' in event['event_name']
                    for events in service_events.values()
                    for event in events
                )
            }
        }, indent=2)
        
    except Exception as e:
        logger.warning(f"Failed to find correlated changes: {e}")
        return json.dumps({
            "error": str(e),
            "incident_time": incident_time
        }, indent=2)


@tool
def get_iam_policy_changes(
    role_name: str,
    hours_back: int = 168
) -> str:
    """
    Get IAM policy changes for a role. Essential for permission-related RCA.
    
    Args:
        role_name: IAM role name
        hours_back: How many hours to look back (default: 168 = 7 days)
    
    Returns:
        JSON with IAM policy changes
    
    Example:
        get_iam_policy_changes('my-lambda-execution-role', 168)
    """
    try:
        # Get AWS client from context (singleton pattern)
        aws_client = get_aws_client()
        cloudtrail = aws_client.get_client('cloudtrail')
        
        start_time = datetime.now() - timedelta(hours=hours_back)
        
        # Look for IAM events related to this role
        response = cloudtrail.lookup_events(
            LookupAttributes=[
                {
                    'AttributeKey': 'ResourceName',
                    'AttributeValue': role_name
                }
            ],
            StartTime=start_time,
            MaxResults=50
        )
        
        events = response.get('Events', [])
        
        # Filter for IAM policy changes
        iam_events = [
            e for e in events
            if 'iam.amazonaws.com' in e.get('EventSource', '')
            and any(keyword in e.get('EventName', '') for keyword in [
                'AttachRolePolicy', 'DetachRolePolicy', 'PutRolePolicy',
                'DeleteRolePolicy', 'UpdateAssumeRolePolicy'
            ])
        ]
        
        logger.info(f"🔐 CloudTrail: Found {len(iam_events)} IAM policy changes for {role_name}")
        
        return json.dumps({
            "role_name": role_name,
            "total_policy_changes": len(iam_events),
            "time_range_hours": hours_back,
            "policy_changes": [
                {
                    "event_time": str(e.get('EventTime')),
                    "event_name": e.get('EventName'),
                    "username": e.get('Username'),
                    "policy_details": json.loads(e.get('CloudTrailEvent', '{}')).get('requestParameters', {}),
                    "error_code": json.loads(e.get('CloudTrailEvent', '{}')).get('errorCode')
                }
                for e in iam_events
            ]
        }, indent=2)
        
    except Exception as e:
        logger.warning(f"Failed to get IAM policy changes: {e}")
        return json.dumps({
            "error": str(e),
            "role_name": role_name
        }, indent=2)
