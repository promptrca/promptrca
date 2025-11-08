#!/usr/bin/env python3
"""
SNS Specialist for PromptRCA

Analyzes AWS SNS topics for configuration issues, subscription problems,
and delivery failures.

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

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class SNSSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS SNS topics."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['sns', 'sns_topic']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze SNS topic configuration, metrics, and subscriptions."""
        facts = []
        topic_arn = resource.get('name') or resource.get('topic_arn')
        
        if not topic_arn:
            return facts
        
        topic_name = topic_arn.split(':')[-1] if ':' in topic_arn else topic_arn
        self.logger.info(f"   → Analyzing SNS topic: {topic_name}")
        
        # Get SNS topic configuration
        facts.extend(await self._analyze_configuration(topic_arn))
        
        # Get SNS topic metrics
        facts.extend(await self._analyze_metrics(topic_name))
        
        # Get SNS topic subscriptions
        facts.extend(await self._analyze_subscriptions(topic_arn))
        
        return self._limit_facts(facts)
    
    async def _analyze_configuration(self, topic_arn: str) -> List[Fact]:
        """Analyze SNS topic configuration."""
        facts = []
        topic_name = topic_arn.split(':')[-1] if ':' in topic_arn else topic_arn
        
        try:
            from ..tools.sns_tools import get_sns_topic_config
            config_json = get_sns_topic_config(topic_arn)
            config = json.loads(config_json)
            
            if 'error' not in config:
                facts.append(self._create_fact(
                    source='sns_topic_config',
                    content=f"SNS topic configuration loaded for {topic_name}",
                    confidence=0.9,
                    metadata={
                        "topic_arn": topic_arn,
                        "topic_name": topic_name,
                        "display_name": config.get('display_name'),
                        "is_fifo": config.get('fifotopic', False),
                        "subscriptions_confirmed": config.get('subscriptions_confirmed', 0),
                        "subscriptions_pending": config.get('subscriptions_pending', 0)
                    }
                ))
                
                # Check for FIFO topic configuration
                is_fifo = config.get('fifotopic', False)
                if is_fifo:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} is configured as FIFO topic",
                        confidence=0.8,
                        metadata={
                            "topic_name": topic_name,
                            "is_fifo": True,
                            "content_based_deduplication": config.get('content_based_deduplication', False)
                        }
                    ))
                
                # Check for pending subscriptions
                pending_subs = config.get('subscriptions_pending', 0)
                if pending_subs > 0:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} has {pending_subs} pending subscriptions",
                        confidence=0.8,
                        metadata={
                            "topic_name": topic_name,
                            "pending_subscriptions": pending_subs,
                            "subscription_issue": "pending_confirmations"
                        }
                    ))
                
                # Check for no confirmed subscriptions
                confirmed_subs = config.get('subscriptions_confirmed', 0)
                if confirmed_subs == 0:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} has no confirmed subscriptions",
                        confidence=0.7,
                        metadata={
                            "topic_name": topic_name,
                            "confirmed_subscriptions": 0,
                            "potential_issue": "no_subscribers",
                            "recommendation": "Verify subscription configuration"
                        }
                    ))
                
                # Check for KMS encryption
                kms_key_id = config.get('kms_master_key_id', '')
                if kms_key_id:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} has KMS encryption enabled",
                        confidence=0.8,
                        metadata={
                            "topic_name": topic_name,
                            "kms_key_id": kms_key_id,
                            "security_feature": "kms_encryption"
                        }
                    ))
                else:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} has no KMS encryption configured",
                        confidence=0.6,
                        metadata={
                            "topic_name": topic_name,
                            "security_consideration": "no_kms_encryption",
                            "recommendation": "Consider enabling KMS encryption for sensitive data"
                        }
                    ))
                
                # Check delivery policy
                delivery_policy = config.get('delivery_policy', {})
                if delivery_policy:
                    facts.append(self._create_fact(
                        source='sns_topic_config',
                        content=f"SNS topic {topic_name} has custom delivery policy configured",
                        confidence=0.7,
                        metadata={
                            "topic_name": topic_name,
                            "has_delivery_policy": True,
                            "delivery_policy": delivery_policy
                        }
                    ))
            else:
                facts.append(self._create_fact(
                    source='sns_topic_config',
                    content=f"Failed to retrieve SNS topic configuration for {topic_name}: {config.get('error')}",
                    confidence=0.9,
                    metadata={
                        "topic_arn": topic_arn,
                        "topic_name": topic_name,
                        "error": config.get('error'),
                        "analysis_issue": "config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to get SNS topic config for {topic_name}: {e}")
            facts.append(self._create_fact(
                source='sns_topic_config',
                content=f"Exception analyzing SNS topic configuration for {topic_name}: {str(e)}",
                confidence=0.8,
                metadata={
                    "topic_arn": topic_arn,
                    "topic_name": topic_name,
                    "exception": str(e),
                    "analysis_issue": "exception_during_analysis"
                }
            ))
        
        return facts
    
    async def _analyze_metrics(self, topic_name: str) -> List[Fact]:
        """Analyze SNS topic metrics."""
        facts = []
        
        try:
            from ..tools.sns_tools import get_sns_topic_metrics
            metrics_json = get_sns_topic_metrics(topic_name)
            metrics = json.loads(metrics_json)
            
            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})
                
                facts.append(self._create_fact(
                    source='sns_topic_metrics',
                    content=f"SNS topic metrics available for {topic_name}",
                    confidence=0.8,
                    metadata={
                        "topic_name": topic_name,
                        "metrics_available": list(metrics_data.keys()),
                        "time_range": metrics.get('time_range', {})
                    }
                ))
                
                # Check for failed notifications
                failed_notifications = metrics_data.get('NumberOfNotificationsFailed', [])
                if failed_notifications:
                    total_failed = sum([point.get('Sum', 0) for point in failed_notifications])
                    if total_failed > 0:
                        facts.append(self._create_fact(
                            source='sns_topic_metrics',
                            content=f"SNS topic {topic_name} has failed notifications: {total_failed}",
                            confidence=0.9,
                            metadata={
                                "topic_name": topic_name,
                                "failed_notifications": total_failed,
                                "delivery_issue": "failed_notifications"
                            }
                        ))
                
                # Check delivery success rate
                delivered_notifications = metrics_data.get('NumberOfNotificationsDelivered', [])
                if delivered_notifications and failed_notifications:
                    total_delivered = sum([point.get('Sum', 0) for point in delivered_notifications])
                    total_failed = sum([point.get('Sum', 0) for point in failed_notifications])
                    total_attempts = total_delivered + total_failed
                    
                    if total_attempts > 0:
                        success_rate = total_delivered / total_attempts
                        if success_rate < 0.95:  # Less than 95% success rate
                            facts.append(self._create_fact(
                                source='sns_topic_metrics',
                                content=f"SNS topic {topic_name} has low delivery success rate: {success_rate:.1%}",
                                confidence=0.8,
                                metadata={
                                    "topic_name": topic_name,
                                    "success_rate": success_rate,
                                    "total_delivered": total_delivered,
                                    "total_failed": total_failed,
                                    "delivery_issue": "low_success_rate"
                                }
                            ))
                
                # Check for DLQ failures
                dlq_failures = metrics_data.get('NumberOfNotificationsFailedToRedriveToDlq', [])
                if dlq_failures:
                    total_dlq_failures = sum([point.get('Sum', 0) for point in dlq_failures])
                    if total_dlq_failures > 0:
                        facts.append(self._create_fact(
                            source='sns_topic_metrics',
                            content=f"SNS topic {topic_name} has DLQ redrive failures: {total_dlq_failures}",
                            confidence=0.8,
                            metadata={
                                "topic_name": topic_name,
                                "dlq_failures": total_dlq_failures,
                                "delivery_issue": "dlq_redrive_failures"
                            }
                        ))
                
                # Check message size
                publish_size = metrics_data.get('PublishSize', [])
                if publish_size:
                    max_size = max([point.get('Maximum', 0) for point in publish_size])
                    avg_size = sum([point.get('Average', 0) for point in publish_size]) / len(publish_size)
                    
                    if max_size > 200000:  # Messages larger than 200KB
                        facts.append(self._create_fact(
                            source='sns_topic_metrics',
                            content=f"SNS topic {topic_name} has large messages: max {max_size/1024:.1f}KB",
                            confidence=0.7,
                            metadata={
                                "topic_name": topic_name,
                                "max_size_bytes": max_size,
                                "avg_size_bytes": avg_size,
                                "performance_consideration": "large_message_size"
                            }
                        ))
                        
        except Exception as e:
            self.logger.debug(f"Failed to get SNS topic metrics for {topic_name}: {e}")
        
        return facts
    
    async def _analyze_subscriptions(self, topic_arn: str) -> List[Fact]:
        """Analyze SNS topic subscriptions."""
        facts = []
        topic_name = topic_arn.split(':')[-1] if ':' in topic_arn else topic_arn
        
        try:
            from ..tools.sns_tools import get_sns_subscriptions
            subs_json = get_sns_subscriptions(topic_arn)
            subs_data = json.loads(subs_json)
            
            if 'error' not in subs_data:
                subscription_count = subs_data.get('subscription_count', 0)
                subscriptions = subs_data.get('subscriptions', [])
                
                facts.append(self._create_fact(
                    source='sns_subscriptions',
                    content=f"SNS topic {topic_name} has {subscription_count} subscriptions",
                    confidence=0.8,
                    metadata={
                        "topic_name": topic_name,
                        "subscription_count": subscription_count,
                        "protocols": list(set([sub.get('protocol') for sub in subscriptions]))
                    }
                ))
                
                # Analyze subscription protocols
                protocol_counts = {}
                for sub in subscriptions:
                    protocol = sub.get('protocol', 'unknown')
                    protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
                
                for protocol, count in protocol_counts.items():
                    facts.append(self._create_fact(
                        source='sns_subscriptions',
                        content=f"SNS topic {topic_name} has {count} {protocol} subscriptions",
                        confidence=0.7,
                        metadata={
                            "topic_name": topic_name,
                            "protocol": protocol,
                            "protocol_count": count
                        }
                    ))
                
                # Check for pending confirmations
                pending_subs = [sub for sub in subscriptions if sub.get('subscription_arn') == 'PendingConfirmation']
                if pending_subs:
                    facts.append(self._create_fact(
                        source='sns_subscriptions',
                        content=f"SNS topic {topic_name} has {len(pending_subs)} pending subscription confirmations",
                        confidence=0.8,
                        metadata={
                            "topic_name": topic_name,
                            "pending_confirmations": len(pending_subs),
                            "subscription_issue": "pending_confirmations",
                            "pending_endpoints": [sub.get('endpoint') for sub in pending_subs]
                        }
                    ))
                
                # Check for cross-account subscriptions
                cross_account_subs = []
                for sub in subscriptions:
                    sub_arn = sub.get('subscription_arn', '')
                    topic_account = topic_arn.split(':')[4] if ':' in topic_arn else ''
                    sub_account = sub_arn.split(':')[4] if ':' in sub_arn else ''
                    
                    if topic_account and sub_account and topic_account != sub_account:
                        cross_account_subs.append(sub)
                
                if cross_account_subs:
                    facts.append(self._create_fact(
                        source='sns_subscriptions',
                        content=f"SNS topic {topic_name} has {len(cross_account_subs)} cross-account subscriptions",
                        confidence=0.7,
                        metadata={
                            "topic_name": topic_name,
                            "cross_account_subscriptions": len(cross_account_subs),
                            "security_consideration": "cross_account_access"
                        }
                    ))
            else:
                facts.append(self._create_fact(
                    source='sns_subscriptions',
                    content=f"Failed to retrieve SNS subscriptions for {topic_name}: {subs_data.get('error')}",
                    confidence=0.8,
                    metadata={
                        "topic_arn": topic_arn,
                        "topic_name": topic_name,
                        "error": subs_data.get('error'),
                        "analysis_issue": "subscriptions_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to get SNS subscriptions for {topic_name}: {e}")
        
        return facts