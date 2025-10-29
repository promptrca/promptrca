#!/usr/bin/env python3
"""
IAM Specialist for PromptRCA

Analyzes AWS IAM roles, users, and policies for permission issues,
configuration problems, and security concerns.
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class IAMSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS IAM resources."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['iam', 'iam_role', 'iam_user', 'iam_policy']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze IAM resource configuration, policies, and permissions."""
        facts = []
        resource_name = resource.get('name')
        resource_type = resource.get('type', 'iam')
        
        if not resource_name:
            return facts
        
        self.logger.info(f"   → Analyzing IAM resource: {resource_name} (type: {resource_type})")
        
        # Analyze based on resource type
        if resource_type.lower() in ['iam_role', 'role']:
            facts.extend(await self._analyze_role(resource_name))
        elif resource_type.lower() in ['iam_user', 'user']:
            facts.extend(await self._analyze_user(resource_name))
        else:
            # Default to role analysis if type is unclear
            facts.extend(await self._analyze_role(resource_name))
        
        return self._limit_facts(facts)
    
    async def _analyze_role(self, role_name: str) -> List[Fact]:
        """Analyze IAM role configuration and policies."""
        facts = []
        
        try:
            from ..tools.iam_tools import get_iam_role_config
            config_json = get_iam_role_config(role_name)
            config = json.loads(config_json)
            
            if 'error' not in config:
                facts.append(self._create_fact(
                    source='iam_role_config',
                    content=f"IAM role configuration loaded for {role_name}",
                    confidence=0.9,
                    metadata={
                        "role_name": role_name,
                        "role_arn": config.get('role_arn'),
                        "attached_policies_count": len(config.get('attached_policies', [])),
                        "inline_policies_count": len(config.get('inline_policies', []))
                    }
                ))
                
                # Check for overly permissive assume role policy
                assume_role_policy = config.get('assume_role_policy', {})
                if assume_role_policy:
                    statements = assume_role_policy.get('Statement', [])
                    for statement in statements:
                        if statement.get('Effect') == 'Allow':
                            principal = statement.get('Principal', {})
                            if principal == '*' or (isinstance(principal, dict) and principal.get('AWS') == '*'):
                                facts.append(self._create_fact(
                                    source='iam_role_config',
                                    content=f"IAM role {role_name} has overly permissive assume role policy (Principal: *)",
                                    confidence=0.8,
                                    metadata={
                                        "role_name": role_name,
                                        "security_issue": "overly_permissive_assume_role",
                                        "principal": principal
                                    }
                                ))
                
                # Check for excessive permissions in attached policies
                attached_policies = config.get('attached_policies', [])
                for policy in attached_policies:
                    policy_name = policy.get('policy_name', '')
                    if 'admin' in policy_name.lower() or 'full' in policy_name.lower():
                        facts.append(self._create_fact(
                            source='iam_role_config',
                            content=f"IAM role {role_name} has potentially excessive permissions: {policy_name}",
                            confidence=0.7,
                            metadata={
                                "role_name": role_name,
                                "policy_name": policy_name,
                                "policy_arn": policy.get('policy_arn'),
                                "security_concern": "excessive_permissions"
                            }
                        ))
                
                # Check inline policies for overly broad permissions
                inline_policies = config.get('inline_policies', [])
                for policy in inline_policies:
                    policy_doc = policy.get('policy_document', {})
                    statements = policy_doc.get('Statement', []) if isinstance(policy_doc, dict) else []
                    
                    for statement in statements:
                        if statement.get('Effect') == 'Allow':
                            actions = statement.get('Action', [])
                            resources = statement.get('Resource', [])
                            
                            # Check for wildcard actions
                            if '*' in actions or (isinstance(actions, str) and actions == '*'):
                                facts.append(self._create_fact(
                                    source='iam_role_config',
                                    content=f"IAM role {role_name} has wildcard permissions in inline policy {policy.get('policy_name')}",
                                    confidence=0.8,
                                    metadata={
                                        "role_name": role_name,
                                        "policy_name": policy.get('policy_name'),
                                        "security_issue": "wildcard_permissions",
                                        "actions": actions,
                                        "resources": resources
                                    }
                                ))
            else:
                facts.append(self._create_fact(
                    source='iam_role_config',
                    content=f"Failed to retrieve IAM role configuration for {role_name}: {config.get('error')}",
                    confidence=0.9,
                    metadata={
                        "role_name": role_name,
                        "error": config.get('error'),
                        "analysis_issue": "config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to analyze IAM role {role_name}: {e}")
            facts.append(self._create_fact(
                source='iam_role_config',
                content=f"Exception analyzing IAM role {role_name}: {str(e)}",
                confidence=0.8,
                metadata={
                    "role_name": role_name,
                    "exception": str(e),
                    "analysis_issue": "exception_during_analysis"
                }
            ))
        
        return facts
    
    async def _analyze_user(self, user_name: str) -> List[Fact]:
        """Analyze IAM user configuration and policies."""
        facts = []
        
        try:
            from ..tools.iam_tools import get_iam_user_policies
            config_json = get_iam_user_policies(user_name)
            config = json.loads(config_json)
            
            if 'error' not in config:
                facts.append(self._create_fact(
                    source='iam_user_config',
                    content=f"IAM user configuration loaded for {user_name}",
                    confidence=0.9,
                    metadata={
                        "user_name": user_name,
                        "user_arn": config.get('user_arn'),
                        "attached_policies_count": len(config.get('attached_policies', [])),
                        "inline_policies_count": len(config.get('inline_policies', [])),
                        "groups_count": len(config.get('groups', []))
                    }
                ))
                
                # Check for excessive permissions in attached policies
                attached_policies = config.get('attached_policies', [])
                for policy in attached_policies:
                    policy_name = policy.get('policy_name', '')
                    if 'admin' in policy_name.lower() or 'full' in policy_name.lower():
                        facts.append(self._create_fact(
                            source='iam_user_config',
                            content=f"IAM user {user_name} has potentially excessive permissions: {policy_name}",
                            confidence=0.7,
                            metadata={
                                "user_name": user_name,
                                "policy_name": policy_name,
                                "policy_arn": policy.get('policy_arn'),
                                "security_concern": "excessive_permissions"
                            }
                        ))
                
                # Check if user has no groups (direct policy attachment)
                groups = config.get('groups', [])
                if not groups and (attached_policies or config.get('inline_policies')):
                    facts.append(self._create_fact(
                        source='iam_user_config',
                        content=f"IAM user {user_name} has direct policy attachments instead of group membership",
                        confidence=0.6,
                        metadata={
                            "user_name": user_name,
                            "best_practice_issue": "direct_policy_attachment",
                            "recommendation": "Use groups for policy management"
                        }
                    ))
            else:
                facts.append(self._create_fact(
                    source='iam_user_config',
                    content=f"Failed to retrieve IAM user configuration for {user_name}: {config.get('error')}",
                    confidence=0.9,
                    metadata={
                        "user_name": user_name,
                        "error": config.get('error'),
                        "analysis_issue": "config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to analyze IAM user {user_name}: {e}")
            facts.append(self._create_fact(
                source='iam_user_config',
                content=f"Exception analyzing IAM user {user_name}: {str(e)}",
                confidence=0.8,
                metadata={
                    "user_name": user_name,
                    "exception": str(e),
                    "analysis_issue": "exception_during_analysis"
                }
            ))
        
        return facts