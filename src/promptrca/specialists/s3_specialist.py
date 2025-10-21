#!/usr/bin/env python3
"""
S3 Specialist for PromptRCA

Analyzes AWS S3 buckets for configuration issues, access problems,
and performance concerns.
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class S3Specialist(BaseSpecialist):
    """Specialist for analyzing AWS S3 buckets."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['s3', 's3_bucket']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze S3 bucket configuration, metrics, and policies."""
        facts = []
        bucket_name = resource.get('name')
        
        if not bucket_name:
            return facts
        
        self.logger.info(f"   → Analyzing S3 bucket: {bucket_name}")
        
        # Get S3 bucket configuration
        facts.extend(await self._analyze_configuration(bucket_name))
        
        # Get S3 bucket metrics
        facts.extend(await self._analyze_metrics(bucket_name))
        
        # Get S3 bucket policy
        facts.extend(await self._analyze_policy(bucket_name))
        
        return self._limit_facts(facts)
    
    async def _analyze_configuration(self, bucket_name: str) -> List[Fact]:
        """Analyze S3 bucket configuration."""
        facts = []
        
        try:
            from ..tools.s3_tools import get_s3_bucket_config
            config_json = get_s3_bucket_config(bucket_name)
            config = json.loads(config_json)
            
            if 'error' not in config:
                facts.append(self._create_fact(
                    source='s3_bucket_config',
                    content=f"S3 bucket configuration loaded for {bucket_name}",
                    confidence=0.9,
                    metadata={
                        "bucket_name": bucket_name,
                        "region": config.get('region'),
                        "versioning_status": config.get('versioning_status'),
                        "encryption_rules_count": len(config.get('encryption_rules', [])),
                        "lifecycle_rules_count": len(config.get('lifecycle_rules', []))
                    }
                ))
                
                # Check for versioning disabled
                versioning_status = config.get('versioning_status', 'Suspended')
                if versioning_status != 'Enabled':
                    facts.append(self._create_fact(
                        source='s3_bucket_config',
                        content=f"S3 bucket {bucket_name} has versioning disabled",
                        confidence=0.7,
                        metadata={
                            "bucket_name": bucket_name,
                            "versioning_status": versioning_status,
                            "best_practice_issue": "versioning_disabled",
                            "recommendation": "Enable versioning for data protection"
                        }
                    ))
                
                # Check for missing encryption
                encryption_rules = config.get('encryption_rules', [])
                if not encryption_rules:
                    facts.append(self._create_fact(
                        source='s3_bucket_config',
                        content=f"S3 bucket {bucket_name} has no server-side encryption configured",
                        confidence=0.8,
                        metadata={
                            "bucket_name": bucket_name,
                            "security_issue": "no_encryption",
                            "recommendation": "Configure server-side encryption"
                        }
                    ))
                
                # Check for lifecycle rules
                lifecycle_rules = config.get('lifecycle_rules', [])
                if not lifecycle_rules:
                    facts.append(self._create_fact(
                        source='s3_bucket_config',
                        content=f"S3 bucket {bucket_name} has no lifecycle rules configured",
                        confidence=0.6,
                        metadata={
                            "bucket_name": bucket_name,
                            "cost_optimization_issue": "no_lifecycle_rules",
                            "recommendation": "Configure lifecycle rules for cost optimization"
                        }
                    ))
                
                # Check for event notifications
                notifications = config.get('notifications', {})
                has_notifications = bool(
                    notifications.get('TopicConfigurations') or 
                    notifications.get('QueueConfigurations') or 
                    notifications.get('LambdaConfigurations')
                )
                
                if has_notifications:
                    facts.append(self._create_fact(
                        source='s3_bucket_config',
                        content=f"S3 bucket {bucket_name} has event notifications configured",
                        confidence=0.8,
                        metadata={
                            "bucket_name": bucket_name,
                            "has_topic_notifications": bool(notifications.get('TopicConfigurations')),
                            "has_queue_notifications": bool(notifications.get('QueueConfigurations')),
                            "has_lambda_notifications": bool(notifications.get('LambdaConfigurations'))
                        }
                    ))
            else:
                facts.append(self._create_fact(
                    source='s3_bucket_config',
                    content=f"Failed to retrieve S3 bucket configuration for {bucket_name}: {config.get('error')}",
                    confidence=0.9,
                    metadata={
                        "bucket_name": bucket_name,
                        "error": config.get('error'),
                        "analysis_issue": "config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to get S3 bucket config for {bucket_name}: {e}")
            facts.append(self._create_fact(
                source='s3_bucket_config',
                content=f"Exception analyzing S3 bucket configuration for {bucket_name}: {str(e)}",
                confidence=0.8,
                metadata={
                    "bucket_name": bucket_name,
                    "exception": str(e),
                    "analysis_issue": "exception_during_analysis"
                }
            ))
        
        return facts
    
    async def _analyze_metrics(self, bucket_name: str) -> List[Fact]:
        """Analyze S3 bucket metrics."""
        facts = []
        
        try:
            from ..tools.s3_tools import get_s3_bucket_metrics
            metrics_json = get_s3_bucket_metrics(bucket_name)
            metrics = json.loads(metrics_json)
            
            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})
                
                facts.append(self._create_fact(
                    source='s3_bucket_metrics',
                    content=f"S3 bucket metrics available for {bucket_name}",
                    confidence=0.8,
                    metadata={
                        "bucket_name": bucket_name,
                        "metrics_available": list(metrics_data.keys()),
                        "time_range": metrics.get('time_range', {})
                    }
                ))
                
                # Check for high request rates
                all_requests = metrics_data.get('AllRequests', [])
                if all_requests:
                    max_requests = max([point.get('Sum', 0) for point in all_requests])
                    if max_requests > 1000:  # High request rate threshold
                        facts.append(self._create_fact(
                            source='s3_bucket_metrics',
                            content=f"S3 bucket {bucket_name} has high request rate: {max_requests} requests/hour",
                            confidence=0.7,
                            metadata={
                                "bucket_name": bucket_name,
                                "max_requests_per_hour": max_requests,
                                "performance_concern": "high_request_rate"
                            }
                        ))
                
                # Check bucket size
                bucket_size_bytes = metrics_data.get('BucketSizeBytes', [])
                if bucket_size_bytes:
                    latest_size = max([point.get('Average', 0) for point in bucket_size_bytes])
                    size_gb = latest_size / (1024**3)  # Convert to GB
                    
                    facts.append(self._create_fact(
                        source='s3_bucket_metrics',
                        content=f"S3 bucket {bucket_name} size: {size_gb:.2f} GB",
                        confidence=0.8,
                        metadata={
                            "bucket_name": bucket_name,
                            "size_bytes": latest_size,
                            "size_gb": size_gb
                        }
                    ))
                    
                    if size_gb > 100:  # Large bucket threshold
                        facts.append(self._create_fact(
                            source='s3_bucket_metrics',
                            content=f"S3 bucket {bucket_name} is large ({size_gb:.2f} GB) - consider lifecycle policies",
                            confidence=0.6,
                            metadata={
                                "bucket_name": bucket_name,
                                "size_gb": size_gb,
                                "cost_optimization_issue": "large_bucket_size"
                            }
                        ))
                        
        except Exception as e:
            self.logger.debug(f"Failed to get S3 bucket metrics for {bucket_name}: {e}")
        
        return facts
    
    async def _analyze_policy(self, bucket_name: str) -> List[Fact]:
        """Analyze S3 bucket policy."""
        facts = []
        
        try:
            from ..tools.s3_tools import get_s3_bucket_policy
            policy_json = get_s3_bucket_policy(bucket_name)
            policy_data = json.loads(policy_json)
            
            if 'error' not in policy_data:
                policy = policy_data.get('policy', {})
                
                if policy:
                    facts.append(self._create_fact(
                        source='s3_bucket_policy',
                        content=f"S3 bucket {bucket_name} has bucket policy configured",
                        confidence=0.8,
                        metadata={
                            "bucket_name": bucket_name,
                            "has_bucket_policy": True,
                            "policy_statements_count": len(policy.get('Statement', []))
                        }
                    ))
                    
                    # Check for overly permissive policies
                    statements = policy.get('Statement', [])
                    for i, statement in enumerate(statements):
                        if statement.get('Effect') == 'Allow':
                            principal = statement.get('Principal', {})
                            actions = statement.get('Action', [])
                            
                            # Check for public access
                            if principal == '*' or (isinstance(principal, dict) and principal.get('AWS') == '*'):
                                facts.append(self._create_fact(
                                    source='s3_bucket_policy',
                                    content=f"S3 bucket {bucket_name} has public access policy (Principal: *)",
                                    confidence=0.9,
                                    metadata={
                                        "bucket_name": bucket_name,
                                        "security_issue": "public_access_policy",
                                        "statement_index": i,
                                        "principal": principal,
                                        "actions": actions
                                    }
                                ))
                            
                            # Check for wildcard actions
                            if '*' in actions or (isinstance(actions, str) and actions == '*'):
                                facts.append(self._create_fact(
                                    source='s3_bucket_policy',
                                    content=f"S3 bucket {bucket_name} has wildcard permissions in bucket policy",
                                    confidence=0.8,
                                    metadata={
                                        "bucket_name": bucket_name,
                                        "security_issue": "wildcard_permissions",
                                        "statement_index": i,
                                        "actions": actions
                                    }
                                ))
                else:
                    facts.append(self._create_fact(
                        source='s3_bucket_policy',
                        content=f"S3 bucket {bucket_name} has no bucket policy configured",
                        confidence=0.6,
                        metadata={
                            "bucket_name": bucket_name,
                            "has_bucket_policy": False,
                            "recommendation": "Consider bucket policy for access control"
                        }
                    ))
            else:
                # Policy retrieval failed - might be no policy or access denied
                error_msg = policy_data.get('error', '')
                if 'NoSuchBucketPolicy' in error_msg:
                    facts.append(self._create_fact(
                        source='s3_bucket_policy',
                        content=f"S3 bucket {bucket_name} has no bucket policy configured",
                        confidence=0.8,
                        metadata={
                            "bucket_name": bucket_name,
                            "has_bucket_policy": False
                        }
                    ))
                else:
                    facts.append(self._create_fact(
                        source='s3_bucket_policy',
                        content=f"Failed to retrieve S3 bucket policy for {bucket_name}: {error_msg}",
                        confidence=0.7,
                        metadata={
                            "bucket_name": bucket_name,
                            "error": error_msg,
                            "analysis_issue": "policy_retrieval_failed"
                        }
                    ))
                    
        except Exception as e:
            self.logger.debug(f"Failed to get S3 bucket policy for {bucket_name}: {e}")
        
        return facts