#!/usr/bin/env python3
"""
SQS Specialist for PromptRCA

Analyzes AWS SQS queues for configuration issues, message processing problems,
and dead letter queue concerns.
"""

import json
from typing import Dict, Any, List
from .base_specialist import BaseSpecialist, InvestigationContext
from ..models import Fact


class SQSSpecialist(BaseSpecialist):
    """Specialist for analyzing AWS SQS queues."""
    
    @property
    def supported_resource_types(self) -> List[str]:
        return ['sqs', 'sqs_queue']
    
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """Analyze SQS queue configuration, metrics, and dead letter queue setup."""
        facts = []
        queue_url = resource.get('name') or resource.get('queue_url')
        
        if not queue_url:
            return facts
        
        self.logger.info(f"   → Analyzing SQS queue: {queue_url}")
        
        # Get SQS queue configuration
        facts.extend(await self._analyze_configuration(queue_url))
        
        # Get SQS queue metrics
        facts.extend(await self._analyze_metrics(queue_url))
        
        # Get dead letter queue configuration
        facts.extend(await self._analyze_dead_letter_queue(queue_url))
        
        return self._limit_facts(facts)
    
    async def _analyze_configuration(self, queue_url: str) -> List[Fact]:
        """Analyze SQS queue configuration."""
        facts = []
        
        try:
            from ..tools.sqs_tools import get_sqs_queue_config
            config_json = get_sqs_queue_config(queue_url)
            config = json.loads(config_json)
            
            if 'error' not in config:
                queue_name = queue_url.split('/')[-1]
                
                facts.append(self._create_fact(
                    source='sqs_queue_config',
                    content=f"SQS queue configuration loaded for {queue_name}",
                    confidence=0.9,
                    metadata={
                        "queue_url": queue_url,
                        "queue_name": queue_name,
                        "queue_arn": config.get('queue_arn'),
                        "visibility_timeout": config.get('visibility_timeout_seconds'),
                        "message_retention_period": config.get('message_retention_period'),
                        "approximate_messages": config.get('approximate_number_of_messages')
                    }
                ))
                
                # Check for short visibility timeout
                visibility_timeout = config.get('visibility_timeout_seconds', 0)
                if visibility_timeout < 30:
                    facts.append(self._create_fact(
                        source='sqs_queue_config',
                        content=f"SQS queue {queue_name} has short visibility timeout: {visibility_timeout}s",
                        confidence=0.7,
                        metadata={
                            "queue_name": queue_name,
                            "visibility_timeout": visibility_timeout,
                            "potential_issue": "short_visibility_timeout",
                            "recommendation": "Consider increasing visibility timeout for processing time"
                        }
                    ))
                
                # Check for message backlog
                approx_messages = config.get('approximate_number_of_messages', 0)
                if approx_messages > 100:
                    facts.append(self._create_fact(
                        source='sqs_queue_config',
                        content=f"SQS queue {queue_name} has message backlog: {approx_messages} messages",
                        confidence=0.8,
                        metadata={
                            "queue_name": queue_name,
                            "message_count": approx_messages,
                            "performance_issue": "message_backlog"
                        }
                    ))
                
                # Check for messages not visible (being processed)
                not_visible = config.get('approximate_number_of_messages_not_visible', 0)
                if not_visible > 50:
                    facts.append(self._create_fact(
                        source='sqs_queue_config',
                        content=f"SQS queue {queue_name} has many messages being processed: {not_visible}",
                        confidence=0.7,
                        metadata={
                            "queue_name": queue_name,
                            "not_visible_count": not_visible,
                            "processing_status": "high_processing_volume"
                        }
                    ))
                
                # Check for delayed messages
                delayed_messages = config.get('approximate_number_of_messages_delayed', 0)
                if delayed_messages > 0:
                    facts.append(self._create_fact(
                        source='sqs_queue_config',
                        content=f"SQS queue {queue_name} has delayed messages: {delayed_messages}",
                        confidence=0.8,
                        metadata={
                            "queue_name": queue_name,
                            "delayed_count": delayed_messages,
                            "queue_feature": "delayed_messages"
                        }
                    ))
                
                # Check message retention period
                retention_period = config.get('message_retention_period', 0)
                retention_days = retention_period / 86400  # Convert seconds to days
                if retention_days < 1:
                    facts.append(self._create_fact(
                        source='sqs_queue_config',
                        content=f"SQS queue {queue_name} has short message retention: {retention_days:.1f} days",
                        confidence=0.6,
                        metadata={
                            "queue_name": queue_name,
                            "retention_days": retention_days,
                            "potential_issue": "short_retention_period"
                        }
                    ))
            else:
                queue_name = queue_url.split('/')[-1]
                facts.append(self._create_fact(
                    source='sqs_queue_config',
                    content=f"Failed to retrieve SQS queue configuration for {queue_name}: {config.get('error')}",
                    confidence=0.9,
                    metadata={
                        "queue_url": queue_url,
                        "queue_name": queue_name,
                        "error": config.get('error'),
                        "analysis_issue": "config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            queue_name = queue_url.split('/')[-1]
            self.logger.debug(f"Failed to get SQS queue config for {queue_name}: {e}")
            facts.append(self._create_fact(
                source='sqs_queue_config',
                content=f"Exception analyzing SQS queue configuration for {queue_name}: {str(e)}",
                confidence=0.8,
                metadata={
                    "queue_url": queue_url,
                    "queue_name": queue_name,
                    "exception": str(e),
                    "analysis_issue": "exception_during_analysis"
                }
            ))
        
        return facts
    
    async def _analyze_metrics(self, queue_url: str) -> List[Fact]:
        """Analyze SQS queue metrics."""
        facts = []
        queue_name = queue_url.split('/')[-1]
        
        try:
            from ..tools.sqs_tools import get_sqs_queue_metrics
            metrics_json = get_sqs_queue_metrics(queue_name)
            metrics = json.loads(metrics_json)
            
            if 'error' not in metrics:
                metrics_data = metrics.get('metrics', {})
                
                facts.append(self._create_fact(
                    source='sqs_queue_metrics',
                    content=f"SQS queue metrics available for {queue_name}",
                    confidence=0.8,
                    metadata={
                        "queue_name": queue_name,
                        "metrics_available": list(metrics_data.keys()),
                        "time_range": metrics.get('time_range', {})
                    }
                ))
                
                # Check for high message age
                age_metrics = metrics_data.get('ApproximateAgeOfOldestMessage', [])
                if age_metrics:
                    max_age = max([point.get('Maximum', 0) for point in age_metrics])
                    if max_age > 3600:  # Messages older than 1 hour
                        facts.append(self._create_fact(
                            source='sqs_queue_metrics',
                            content=f"SQS queue {queue_name} has old messages: {max_age/3600:.1f} hours",
                            confidence=0.8,
                            metadata={
                                "queue_name": queue_name,
                                "max_age_seconds": max_age,
                                "max_age_hours": max_age/3600,
                                "performance_issue": "old_messages"
                            }
                        ))
                
                # Check for empty receives (polling without messages)
                empty_receives = metrics_data.get('NumberOfEmptyReceives', [])
                if empty_receives:
                    total_empty = sum([point.get('Sum', 0) for point in empty_receives])
                    if total_empty > 1000:  # High number of empty receives
                        facts.append(self._create_fact(
                            source='sqs_queue_metrics',
                            content=f"SQS queue {queue_name} has high empty receives: {total_empty}",
                            confidence=0.7,
                            metadata={
                                "queue_name": queue_name,
                                "empty_receives": total_empty,
                                "efficiency_issue": "high_empty_receives",
                                "recommendation": "Consider adjusting polling strategy"
                            }
                        ))
                
                # Check message processing rates
                sent_messages = metrics_data.get('NumberOfMessagesSent', [])
                received_messages = metrics_data.get('NumberOfMessagesReceived', [])
                deleted_messages = metrics_data.get('NumberOfMessagesDeleted', [])
                
                if sent_messages and received_messages and deleted_messages:
                    total_sent = sum([point.get('Sum', 0) for point in sent_messages])
                    total_received = sum([point.get('Sum', 0) for point in received_messages])
                    total_deleted = sum([point.get('Sum', 0) for point in deleted_messages])
                    
                    # Check for processing issues
                    if total_received > 0 and total_deleted / total_received < 0.8:
                        facts.append(self._create_fact(
                            source='sqs_queue_metrics',
                            content=f"SQS queue {queue_name} has low message deletion rate: {total_deleted/total_received:.1%}",
                            confidence=0.7,
                            metadata={
                                "queue_name": queue_name,
                                "deletion_rate": total_deleted/total_received,
                                "total_received": total_received,
                                "total_deleted": total_deleted,
                                "processing_issue": "low_deletion_rate"
                            }
                        ))
                        
        except Exception as e:
            self.logger.debug(f"Failed to get SQS queue metrics for {queue_name}: {e}")
        
        return facts
    
    async def _analyze_dead_letter_queue(self, queue_url: str) -> List[Fact]:
        """Analyze SQS dead letter queue configuration."""
        facts = []
        queue_name = queue_url.split('/')[-1]
        
        try:
            from ..tools.sqs_tools import get_sqs_dead_letter_queue
            dlq_json = get_sqs_dead_letter_queue(queue_url)
            dlq_data = json.loads(dlq_json)
            
            if 'error' not in dlq_data:
                has_dlq = dlq_data.get('has_dlq', False)
                
                if has_dlq:
                    max_receive_count = dlq_data.get('max_receive_count', 0)
                    dlq_config = dlq_data.get('dlq_config', {})
                    
                    facts.append(self._create_fact(
                        source='sqs_dlq_config',
                        content=f"SQS queue {queue_name} has dead letter queue configured",
                        confidence=0.8,
                        metadata={
                            "queue_name": queue_name,
                            "has_dlq": True,
                            "max_receive_count": max_receive_count,
                            "dlq_arn": dlq_config.get('dlq_arn')
                        }
                    ))
                    
                    # Check for messages in DLQ
                    dlq_message_count = dlq_config.get('dlq_message_count', 0)
                    if dlq_message_count > 0:
                        facts.append(self._create_fact(
                            source='sqs_dlq_config',
                            content=f"SQS dead letter queue has {dlq_message_count} failed messages",
                            confidence=0.9,
                            metadata={
                                "queue_name": queue_name,
                                "dlq_message_count": dlq_message_count,
                                "processing_issue": "messages_in_dlq",
                                "dlq_arn": dlq_config.get('dlq_arn')
                            }
                        ))
                    
                    # Check max receive count
                    if max_receive_count < 3:
                        facts.append(self._create_fact(
                            source='sqs_dlq_config',
                            content=f"SQS queue {queue_name} has low max receive count: {max_receive_count}",
                            confidence=0.6,
                            metadata={
                                "queue_name": queue_name,
                                "max_receive_count": max_receive_count,
                                "potential_issue": "low_max_receive_count",
                                "recommendation": "Consider increasing max receive count for transient errors"
                            }
                        ))
                else:
                    facts.append(self._create_fact(
                        source='sqs_dlq_config',
                        content=f"SQS queue {queue_name} has no dead letter queue configured",
                        confidence=0.7,
                        metadata={
                            "queue_name": queue_name,
                            "has_dlq": False,
                            "best_practice_issue": "no_dlq_configured",
                            "recommendation": "Consider configuring DLQ for failed message handling"
                        }
                    ))
            else:
                facts.append(self._create_fact(
                    source='sqs_dlq_config',
                    content=f"Failed to retrieve DLQ configuration for {queue_name}: {dlq_data.get('error')}",
                    confidence=0.8,
                    metadata={
                        "queue_name": queue_name,
                        "error": dlq_data.get('error'),
                        "analysis_issue": "dlq_config_retrieval_failed"
                    }
                ))
                
        except Exception as e:
            self.logger.debug(f"Failed to get SQS DLQ config for {queue_name}: {e}")
        
        return facts