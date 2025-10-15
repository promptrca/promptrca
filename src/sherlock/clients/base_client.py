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

import boto3
from typing import Dict, Any, Optional
# Cost tracking removed
from ..utils import get_logger

logger = get_logger(__name__)


class BaseAWSClient:
    """Base AWS client with common functionality."""

    def __init__(self, region: str = "eu-west-1"):
        """Initialize base AWS client with region."""
        self.region = region
        self._session = None
        self.account_id = None
        self.user_arn = None
        self._initialize_session()
    
    def _initialize_session(self):
        """Initialize AWS session using boto3's default credential chain."""
        try:
            # Use boto3's default credential chain (environment variables, IAM roles, etc.)
            self._session = boto3.Session(region_name=self.region)
            
            # Test credentials by getting caller identity
            sts_client = self._session.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            
            # Store account ID and user ARN
            self.account_id = identity['Account']
            self.user_arn = identity['Arn']
            
            logger.info(f"✅ AWS clients initialized for region: {self.region}")
            logger.info(f"🔐 Authenticated as: {self.user_arn}")
            logger.info(f"🏢 Account: {self.account_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS clients: {e}")
            raise

    def get_client(self, service_name: str):
        """Get a boto3 client for the specified service."""
        return self._session.client(service_name, region_name=self.region)
