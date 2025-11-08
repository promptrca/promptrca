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
from typing import Dict, Any, Optional
import json
from ..context import get_aws_client


@tool
def get_iam_role_config(role_name: str) -> str:
    """
    Get IAM role configuration including trust policy and attached policies.
    
    Args:
        role_name: The IAM role name
    
    Returns:
        JSON string with role configuration
    """
    from urllib.parse import unquote
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('iam')
        
        # Get role details
        role_response = client.get_role(RoleName=role_name)
        role = role_response['Role']
        
        # Get attached policies
        attached_policies_response = client.list_attached_role_policies(RoleName=role_name)
        attached_policies = attached_policies_response.get('AttachedPolicies', [])
        
        # Get inline policies
        inline_policies_response = client.list_role_policies(RoleName=role_name)
        inline_policy_names = inline_policies_response.get('PolicyNames', [])
        
        inline_policies = []
        for policy_name in inline_policy_names:
            policy_response = client.get_role_policy(RoleName=role_name, PolicyName=policy_name)
            inline_policies.append({
                "policy_name": policy_name,
                "policy_document": policy_response.get('PolicyDocument')
            })
        
        config = {
            "role_name": role['RoleName'],
            "role_arn": role['Arn'],
            "assume_role_policy": role.get('AssumeRolePolicyDocument'),
            "attached_policies": [
                {
                    "policy_name": p['PolicyName'],
                    "policy_arn": p['PolicyArn']
                } for p in attached_policies
            ],
            "inline_policies": inline_policies,
            "created_date": str(role.get('CreateDate')),
            "max_session_duration": role.get('MaxSessionDuration')
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "role_name": role_name})


@tool
def get_iam_policy_document(policy_arn: str) -> str:
    """
    Get IAM policy document details.
    
    Args:
        policy_arn: The IAM policy ARN
    
    Returns:
        JSON string with policy document details
    """
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('iam')
        
        # Get policy details
        policy_response = client.get_policy(PolicyArn=policy_arn)
        policy = policy_response['Policy']
        
        # Get policy version (default version)
        policy_version_response = client.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=policy['DefaultVersionId']
        )
        
        config = {
            "policy_arn": policy['Arn'],
            "policy_name": policy['PolicyName'],
            "policy_id": policy['PolicyId'],
            "description": policy.get('Description', ''),
            "create_date": str(policy.get('CreateDate')),
            "update_date": str(policy.get('UpdateDate')),
            "default_version_id": policy['DefaultVersionId'],
            "policy_document": policy_version_response['PolicyVersion']['Document'],
            "is_attachable": policy['IsAttachable'],
            "attachment_count": policy['AttachmentCount']
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "policy_arn": policy_arn})


@tool
def simulate_iam_policy(policy_document: str, action: str, resource: str = "*") -> str:
    """
    Simulate IAM policy to check if an action is allowed.
    
    Args:
        policy_document: The IAM policy document (JSON string)
        action: The action to test (e.g., "lambda:InvokeFunction")
        resource: The resource ARN to test (default: "*")
    
    Returns:
        JSON string with simulation results
    """
    import json as json_lib
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('iam')
        
        # Parse policy document if it's a string
        if isinstance(policy_document, str):
            policy_doc = json_lib.loads(policy_document)
        else:
            policy_doc = policy_document
        
        # Simulate the policy
        response = client.simulate_principal_policy(
            PolicySourceArn="arn:aws:iam::123456789012:role/TestRole",  # Dummy ARN for simulation
            ActionNames=[action],
            ResourceArns=[resource],
            PolicyInputList=[policy_doc]
        )
        
        results = response.get('EvaluationResults', [])
        
        config = {
            "action": action,
            "resource": resource,
            "policy_document": policy_doc,
            "simulation_results": [
                {
                    "action": result.get('EvalActionName'),
                    "decision": result.get('EvalDecision'),
                    "matched_statements": result.get('MatchedStatements', []),
                    "missing_context_keys": result.get('MissingContextKeys', [])
                }
                for result in results
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "action": action, "resource": resource})


@tool
def get_iam_user_policies(user_name: str) -> str:
    """
    Get IAM user policies and permissions.
    
    Args:
        user_name: The IAM user name
    
    Returns:
        JSON string with user policies
    """
    
    try:
        # Get AWS client from context
        aws_client = get_aws_client()
        region = aws_client.region
        client = aws_client.get_client('iam')
        
        # Get user details
        user_response = client.get_user(UserName=user_name)
        user = user_response['User']
        
        # Get attached policies
        attached_policies_response = client.list_attached_user_policies(UserName=user_name)
        attached_policies = attached_policies_response.get('AttachedPolicies', [])
        
        # Get inline policies
        inline_policies_response = client.list_user_policies(UserName=user_name)
        inline_policy_names = inline_policies_response.get('PolicyNames', [])
        
        inline_policies = []
        for policy_name in inline_policy_names:
            policy_response = client.get_user_policy(UserName=user_name, PolicyName=policy_name)
            inline_policies.append({
                "policy_name": policy_name,
                "policy_document": policy_response.get('PolicyDocument')
            })
        
        # Get groups
        groups_response = client.get_groups_for_user(UserName=user_name)
        groups = groups_response.get('Groups', [])
        
        config = {
            "user_name": user['UserName'],
            "user_arn": user['Arn'],
            "user_id": user['UserId'],
            "create_date": str(user.get('CreateDate')),
            "attached_policies": [
                {
                    "policy_name": p['PolicyName'],
                    "policy_arn": p['PolicyArn']
                } for p in attached_policies
            ],
            "inline_policies": inline_policies,
            "groups": [
                {
                    "group_name": g['GroupName'],
                    "group_arn": g['Arn']
                } for g in groups
            ]
        }
        
        return json.dumps(config, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e), "user_name": user_name})
