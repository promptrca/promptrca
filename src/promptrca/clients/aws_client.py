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

import boto3
import os
from typing import Dict, Any, List, Optional
from ..models import Fact
from ..utils import get_logger
from ..utils.config import get_region
from .base_client import BaseAWSClient
from .lambda_client import LambdaClient
from .cloudwatch_client import CloudWatchClient
from .stepfunctions_client import StepFunctionsClient
from .xray_client import XRayClient
from .log_query_client import LogQueryClient

logger = get_logger(__name__)


class AWSClient:
    """Unified AWS client that delegates to specialized service clients."""

    def __init__(self, region: str = None, role_arn: Optional[str] = None, external_id: Optional[str] = None):
        """
        Initialize unified AWS client with optional role assumption.
        
        Args:
            region: AWS region
            role_arn: Optional IAM role ARN to assume for cross-account access
            external_id: Optional external ID for cross-account role assumption
        """
        self.region = region or get_region()
        self.role_arn = role_arn
        self.external_id = external_id
        
        # Debug logging for role assumption
        logger.info(f"🔍 [DEBUG] AWSClient.__init__ called with role_arn: {role_arn}, external_id: {external_id}")
        
        # Create ONE session for all clients
        self._session = self._create_session()
        
        # Initialize specialized clients with shared session
        self.lambda_client = LambdaClient(self.region, session=self._session)
        self.cloudwatch_client = CloudWatchClient(self.region, session=self._session)
        self.stepfunctions_client = StepFunctionsClient(self.region, session=self._session)
        self.xray_client = XRayClient(self.region, session=self._session)
        
        # Initialize log query client with shared session
        self.log_query_client = LogQueryClient(self.region, session=self._session)
        
        # Expose account info from base client
        self.account_id = self.lambda_client.account_id
        self.user_arn = self.lambda_client.user_arn

    def _create_session(self) -> boto3.Session:
        """Create boto3 session with optional role assumption."""
        logger.info(f"🔍 [DEBUG] _create_session called with role_arn: {self.role_arn}")
        if self.role_arn:
            logger.info(f"🔍 [DEBUG] Assuming role: {self.role_arn}")
            return self._assume_role(self.role_arn)
        logger.info(f"🔍 [DEBUG] Creating default session for region: {self.region}")
        return boto3.Session(region_name=self.region)

    def _assume_role(self, role_arn: str) -> boto3.Session:
        """Assume an IAM role and return a session with temporary credentials."""
        try:
            logger.info(f"🔍 [DEBUG] Starting role assumption for: {role_arn}")
            
            # Create a temporary session to assume the role
            temp_session = boto3.Session(region_name=self.region)
            sts_client = temp_session.client('sts', region_name=self.region)
            
            # Prepare assume role parameters
            assume_role_params = {
                'RoleArn': role_arn,
                'RoleSessionName': 'promptrca-investigation',
                'DurationSeconds': 3600  # 1 hour
            }
            
            # Add external ID if provided
            if self.external_id:
                assume_role_params['ExternalId'] = self.external_id
                logger.info(f"🔍 [DEBUG] Using external ID: {self.external_id}")
            
            logger.info(f"🔍 [DEBUG] Calling STS AssumeRole API...")
            response = sts_client.assume_role(**assume_role_params)
            
            credentials = response['Credentials']
            logger.info(f"🔍 [DEBUG] Successfully assumed role, creating new session...")
            
            # Create new session with assumed role credentials
            return boto3.Session(
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'],
                region_name=self.region
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to assume role {role_arn}: {e}")
            raise

    # Lambda methods
    def get_lambda_function_info(self, function_name: str) -> List[Fact]:
        """Get Lambda function information."""
        return self.lambda_client.get_lambda_function_info(function_name)

    def get_lambda_function(self, function_name: str) -> Dict[str, Any]:
        """Get raw Lambda function data."""
        return self.lambda_client.get_lambda_function(function_name)

    def get_lambda_failed_invocations_detailed(self, function_name: str, hours_back: int = 24) -> List[Fact]:
        """Get detailed Lambda failure information."""
        return self.lambda_client.get_lambda_failed_invocations_detailed(function_name, hours_back)

    def get_lambda_error_patterns(self, function_name: str, hours_back: int = 24) -> List[Fact]:
        """Analyze Lambda error patterns."""
        return self.lambda_client.get_lambda_error_patterns(function_name, hours_back)

    # CloudWatch methods
    def get_cloudwatch_metrics(self, function_name: str) -> List[Fact]:
        """Get CloudWatch metrics."""
        return self.cloudwatch_client.get_cloudwatch_metrics(function_name)

    def get_cloudwatch_logs(self, function_name: str) -> List[Fact]:
        """Get CloudWatch logs."""
        return self.cloudwatch_client.get_cloudwatch_logs(function_name)

    # Step Functions methods
    def get_step_function_info(self, state_machine_name: str) -> List[Fact]:
        """Get Step Functions information."""
        return self.stepfunctions_client.get_step_function_info(state_machine_name)

    def get_step_function_executions(self, state_machine_name: str) -> List[Dict[str, Any]]:
        """Get Step Functions executions."""
        return self.stepfunctions_client.get_step_function_executions(state_machine_name)

    def get_step_function_definition(self, state_machine_name: str) -> Optional[Dict[str, Any]]:
        """Get Step Functions definition."""
        return self.stepfunctions_client.get_step_function_definition(state_machine_name)

    # X-Ray methods
    def get_xray_trace(self, trace_id: str) -> List[Fact]:
        """Get X-Ray trace information."""
        return self.xray_client.get_xray_trace(trace_id)

    # IAM methods (keeping these in the main client for now)
    def get_resource_policy(self, resource_name: str, resource_type: str) -> Optional[Dict[str, Any]]:
        """Get IAM resource policy for a resource."""
        try:
            iam_client = self.lambda_client.get_client('iam')
            
            if resource_type == 'lambda':
                # Get Lambda function policy
                try:
                    response = iam_client.get_policy(PolicyArn=f"arn:aws:iam::{self.account_id}:policy/lambda-execution-policy")
                    return response.get('Policy')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            elif resource_type == 'stepfunctions':
                # Get Step Functions execution role
                try:
                    response = iam_client.get_role(RoleName=f"{resource_name}-role")
                    return response.get('Role')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            
        except Exception as e:
            logger.error(f"Failed to get resource policy: {e}")
            return None

    def get_execution_role(self, resource_name: str, resource_type: str) -> Optional[Dict[str, Any]]:
        """Get execution role for a resource."""
        try:
            iam_client = self.lambda_client.get_client('iam')
            
            if resource_type == 'lambda':
                # Get Lambda execution role
                try:
                    response = iam_client.get_role(RoleName=f"{resource_name}-execution-role")
                    return response.get('Role')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            elif resource_type == 'stepfunctions':
                # Get Step Functions execution role
                try:
                    response = iam_client.get_role(RoleName=f"{resource_name}-stepfunctions-role")
                    return response.get('Role')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            
        except Exception as e:
            logger.error(f"Failed to get execution role: {e}")
            return None

    def get_trust_policy(self, resource_name: str, resource_type: str) -> Optional[Dict[str, Any]]:
        """Get trust policy for a resource."""
        try:
            iam_client = self.lambda_client.get_client('iam')
            
            if resource_type == 'lambda':
                # Get Lambda trust policy
                try:
                    response = iam_client.get_role(RoleName=f"{resource_name}-execution-role")
                    return response.get('Role', {}).get('AssumeRolePolicyDocument')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            elif resource_type == 'stepfunctions':
                # Get Step Functions trust policy
                try:
                    response = iam_client.get_role(RoleName=f"{resource_name}-stepfunctions-role")
                    return response.get('Role', {}).get('AssumeRolePolicyDocument')
                except iam_client.exceptions.NoSuchEntityException:
                    return None
            
        except Exception as e:
            logger.error(f"Failed to get trust policy: {e}")
            return None

    def get_client(self, service_name: str):
        """Get a boto3 client for the specified service."""
        return self._session.client(service_name, region_name=self.region)
