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
from typing import Dict, Any, List, Optional
import json
from botocore.exceptions import ClientError
from ..models import Fact
from ..utils import get_logger
from .base_client import BaseAWSClient

logger = get_logger(__name__)


class StepFunctionsClient(BaseAWSClient):
    """Step Functions-specific AWS client."""

    def __init__(self, region: str = "eu-west-1", session: Optional[boto3.Session] = None):
        """Initialize Step Functions client with optional shared session."""
        super().__init__(region, session=session)
        self._stepfunctions_client = self.get_client('stepfunctions')

    def get_step_function_info(self, state_machine_name: str) -> List[Fact]:
        """Get Step Functions state machine information."""
        facts = []
        
        try:
            # Get state machine details
            response = self._stepfunctions_client.describe_state_machine(
                stateMachineArn=f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{state_machine_name}")
            
            facts.append(Fact(
                source="stepfunctions",
                content=f"State machine {state_machine_name} exists and is {response['status']}",
                confidence=1.0,
                metadata={
                    "state_machine_name": state_machine_name,
                    "state_machine_arn": f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{state_machine_name}",
                    "status": response['status'],
                    "role_arn": response['roleArn']
                }
            ))
            
            # Get recent executions
            executions = self._stepfunctions_client.list_executions(
                stateMachineArn=f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{state_machine_name}",
                maxResults=10
            )
            
            if executions['executions']:
                failed_executions = [ex for ex in executions['executions'] if ex['status'] == 'FAILED']
                if failed_executions:
                    facts.append(Fact(
                        source="stepfunctions",
                        content=f"State machine has {len(failed_executions)} failed executions",
                        confidence=0.9,
                        metadata={
                            "state_machine_name": state_machine_name,
                            "failed_count": len(failed_executions)
                        }
                    ))
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'StateMachineDoesNotExist':
                facts.append(Fact(
                    source="stepfunctions",
                    content=f"State machine '{state_machine_name}' not found",
                    confidence=1.0,
                    metadata={"state_machine_name": state_machine_name, "error": "not_found"}
                ))
            else:
                facts.append(Fact(
                    source="stepfunctions",
                    content=f"Failed to get Step Functions info: {str(e)}",
                    confidence=0.0,
                    metadata={"error": str(e), "state_machine_name": state_machine_name}
                ))
        except Exception as e:
            facts.append(Fact(
                source="stepfunctions",
                content=f"Unexpected error getting Step Functions info: {str(e)}",
                confidence=0.0,
                metadata={"error": str(e), "state_machine_name": state_machine_name}
            ))
        
        return facts

    def get_step_function_executions(self, state_machine_name: str) -> List[Dict[str, Any]]:
        """Get recent Step Functions executions with detailed error information."""
        try:
            state_machine_arn = f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{state_machine_name}"
            
            # List recent executions
            response = self._stepfunctions_client.list_executions(
                stateMachineArn=state_machine_arn,
                maxResults=10,
                statusFilter='FAILED'  # Focus on failed executions for error analysis
            )
            
            executions = []
            for execution in response.get('executions', []):
                # Get detailed execution information
                try:
                    exec_details = self._stepfunctions_client.describe_execution(
                        executionArn=execution['executionArn']
                    )
                    executions.append({
                        'executionArn': execution['executionArn'],
                        'name': execution['name'],
                        'status': execution['status'],
                        'startDate': execution['startDate'],
                        'stopDate': execution.get('stopDate'),
                        'error': exec_details.get('error'),
                        'cause': exec_details.get('cause'),
                        'duration': exec_details.get('duration', 0)
                    })
                except Exception as e:
                    # If we can't get details, use basic info
                    executions.append({
                        'executionArn': execution['executionArn'],
                        'name': execution['name'],
                        'status': execution['status'],
                        'startDate': execution['startDate'],
                        'stopDate': execution.get('stopDate'),
                        'error': 'Unknown',
                        'cause': f'Could not retrieve details: {str(e)}',
                        'duration': 0
                    })
            
            return executions
            
        except Exception as e:
            logger.error(f"Failed to get Step Functions executions: {e}")
            return []

    def get_step_function_definition(self, state_machine_name: str) -> Optional[Dict[str, Any]]:
        """Get Step Functions state machine definition and metadata."""
        try:
            state_machine_arn = f"arn:aws:states:{self.region}:{self.account_id}:stateMachine:{state_machine_name}"
            
            # Get state machine details including definition
            response = self._stepfunctions_client.describe_state_machine(
                stateMachineArn=state_machine_arn
            )
            
            # Parse the definition JSON
            definition_str = response.get('definition', '{}')
            try:
                definition = json.loads(definition_str)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Step Functions definition JSON: {e}")
                definition = {}
            
            return {
                'name': response.get('name'),
                'arn': response.get('stateMachineArn'),
                'status': response.get('status'),
                'roleArn': response.get('roleArn'),
                'definition': definition,
                'creationDate': response.get('creationDate'),
                'type': response.get('type'),
                'loggingConfiguration': response.get('loggingConfiguration', {}),
                'tracingConfiguration': response.get('tracingConfiguration', {})
            }
            
        except Exception as e:
            logger.error(f"Failed to get Step Functions definition: {e}")
            return None

    def resolve_state_machine_arn(self, name: str) -> Optional[str]:
        """Resolve a Step Functions state machine ARN from a name by listing state machines.

        Tries exact match (case-sensitive), then case-insensitive, then startswith/contains heuristics.
        """
        try:
            paginator = self._stepfunctions_client.get_paginator('list_state_machines')
            candidates = []
            for page in paginator.paginate():
                for sm in page.get('stateMachines', []):
                    candidates.append((sm.get('name'), sm.get('stateMachineArn')))

            if not candidates:
                return None

            # Exact match (case-sensitive)
            for n, arn in candidates:
                if n == name:
                    return arn

            # Case-insensitive match
            lname = name.lower()
            for n, arn in candidates:
                if n and n.lower() == lname:
                    return arn

            # Startswith heuristic
            for n, arn in candidates:
                if n and n.lower().startswith(lname):
                    return arn

            # Contains heuristic
            for n, arn in candidates:
                if n and lname in n.lower():
                    return arn

            return None
        except Exception as e:
            logger.error(f"Failed to resolve state machine ARN for {name}: {e}")
            return None
