#!/usr/bin/env python3
"""
Sherlock Core - Graph Builder
Copyright (C) 2025 Christian Gennaro Faraone

Extracts nodes and edges from investigation artifacts to build knowledge graph.
"""

import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from .models import GraphNode, GraphEdge, ObservabilityPointer, ConfigSnapshot
from ..utils import get_logger

logger = get_logger(__name__)


class GraphBuilder:
    """Builds knowledge graph from investigation artifacts."""
    
    def __init__(self, account_id: str, region: str):
        """Initialize graph builder.
        
        Args:
            account_id: AWS account ID
            region: AWS region
        """
        self.account_id = account_id
        self.region = region
    
    def extract_from_trace(self, trace_data: Dict[str, Any]) -> Tuple[List[GraphNode], List[GraphEdge], List[ObservabilityPointer]]:
        """Extract nodes and edges from X-Ray trace data.
        
        Args:
            trace_data: X-Ray trace response data
            
        Returns:
            Tuple of (nodes, edges, pointers)
        """
        nodes = []
        edges = []
        pointers = []
        
        try:
            segments = trace_data.get('Segments', [])
            discovered_arns = set()
            
            for segment in segments:
                segment_doc = segment.get('Document', {})
                
                # Parse JSON if needed
                if isinstance(segment_doc, str):
                    try:
                        segment_doc = json.loads(segment_doc)
                    except:
                        continue
                
                # Extract node from segment
                node = self._extract_node_from_segment(segment_doc)
                if node and node.arn not in discovered_arns:
                    nodes.append(node)
                    discovered_arns.add(node.arn)
                    
                    # Extract observability pointer
                    pointer = self._extract_pointer_from_segment(segment_doc, node.arn)
                    if pointer:
                        pointers.append(pointer)
                
                # Extract edges from subsegments
                subsegments = segment_doc.get('subsegments', [])
                for subsegment in subsegments:
                    edge = self._extract_edge_from_subsegment(segment_doc, subsegment)
                    if edge:
                        edges.append(edge)
            
            logger.info(f"Extracted {len(nodes)} nodes, {len(edges)} edges from trace")
            return nodes, edges, pointers
            
        except Exception as e:
            logger.error(f"Failed to extract from trace: {e}")
            return [], [], []
    
    def extract_from_logs(self, logs_data: List[Dict[str, Any]], source_arn: str) -> List[GraphEdge]:
        """Extract edges from log data using heuristic analysis.
        
        Args:
            logs_data: List of log entries
            source_arn: ARN of the source resource
            
        Returns:
            List of extracted edges
        """
        edges = []
        
        try:
            for log_entry in logs_data:
                message = log_entry.get('message', '')
                timestamp = log_entry.get('timestamp', '')
                
                # Heuristic patterns for different AWS services
                target_arn = self._extract_target_arn_from_log(message)
                if target_arn:
                    edge = GraphEdge(
                        from_arn=source_arn,
                        to_arn=target_arn,
                        rel=self._infer_relationship_from_log(message),
                        evidence_sources=["LOGS"],
                        confidence=self._calculate_log_confidence(message),
                        first_seen=timestamp,
                        last_seen=timestamp,
                        account_id=self.account_id,
                        region=self.region
                    )
                    edges.append(edge)
            
            logger.info(f"Extracted {len(edges)} edges from logs")
            return edges
            
        except Exception as e:
            logger.error(f"Failed to extract from logs: {e}")
            return []
    
    def extract_from_config(self, config_data: Dict[str, Any], arn: str) -> ConfigSnapshot:
        """Extract config snapshot from resource configuration.
        
        Args:
            config_data: Resource configuration data
            arn: Resource ARN
            
        Returns:
            ConfigSnapshot object
        """
        try:
            # Generate hash of config content
            config_str = json.dumps(config_data, sort_keys=True)
            config_hash = hashlib.sha256(config_str.encode()).hexdigest()
            
            # Determine resource type from ARN
            resource_type = self._extract_resource_type_from_arn(arn)
            
            snapshot = ConfigSnapshot(
                arn=arn,
                hash=config_hash,
                current=True,
                type=resource_type,
                attrs=config_data,
                collected_at=datetime.now(timezone.utc).isoformat(),
                account_id=self.account_id,
                region=self.region
            )
            
            logger.debug(f"Extracted config snapshot for {arn}")
            return snapshot
            
        except Exception as e:
            logger.error(f"Failed to extract config for {arn}: {e}")
            return None
    
    def _extract_node_from_segment(self, segment_doc: Dict[str, Any]) -> Optional[GraphNode]:
        """Extract GraphNode from X-Ray segment document."""
        try:
            name = segment_doc.get('name', '')
            origin = segment_doc.get('origin', '')
            resource_arn = segment_doc.get('resource_arn', '')
            
            # Determine resource type and name
            resource_type, resource_name = self._parse_resource_info(name, origin, resource_arn)
            
            if not resource_type or not resource_name:
                return None
            
            # Extract observability info
            observability = self._extract_observability_from_segment(segment_doc)
            
            # Extract tags (if available)
            tags = self._extract_tags_from_segment(segment_doc)
            
            node = GraphNode(
                arn=resource_arn or f"arn:aws:{resource_type}:{self.region}:{self.account_id}:{resource_name}",
                type=resource_type,
                name=resource_name,
                account_id=self.account_id,
                region=self.region,
                tags=tags,
                observability=observability,
                config_fingerprint={},
                versions={},
                staleness={
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                    "flag": False
                }
            )
            
            return node
            
        except Exception as e:
            logger.debug(f"Failed to extract node from segment: {e}")
            return None
    
    def _extract_edge_from_subsegment(self, parent_segment: Dict[str, Any], subsegment: Dict[str, Any]) -> Optional[GraphEdge]:
        """Extract GraphEdge from X-Ray subsegment."""
        try:
            parent_arn = parent_segment.get('resource_arn', '')
            subsegment_name = subsegment.get('name', '')
            subsegment_arn = subsegment.get('resource_arn', '')
            
            if not parent_arn or not subsegment_arn:
                return None
            
            # Infer relationship type
            rel = self._infer_relationship_from_subsegment(subsegment_name, subsegment)
            
            # Calculate confidence based on evidence
            confidence = self._calculate_xray_confidence(subsegment)
            
            edge = GraphEdge(
                from_arn=parent_arn,
                to_arn=subsegment_arn,
                rel=rel,
                evidence_sources=["X_RAY"],
                confidence=confidence,
                first_seen=subsegment.get('start_time', datetime.now(timezone.utc).isoformat()),
                last_seen=subsegment.get('end_time', datetime.now(timezone.utc).isoformat()),
                account_id=self.account_id,
                region=self.region
            )
            
            return edge
            
        except Exception as e:
            logger.debug(f"Failed to extract edge from subsegment: {e}")
            return None
    
    def _extract_pointer_from_segment(self, segment_doc: Dict[str, Any], arn: str) -> Optional[ObservabilityPointer]:
        """Extract ObservabilityPointer from X-Ray segment."""
        try:
            # Extract log group info
            log_group = self._extract_log_group_from_segment(segment_doc)
            
            # Extract X-Ray info
            xray_name = segment_doc.get('name', '')
            trace_id = segment_doc.get('trace_id', '')
            
            # Extract metrics info
            metrics = self._extract_metrics_from_segment(segment_doc)
            
            pointer = ObservabilityPointer(
                arn=arn,
                logs=log_group,
                traces={
                    "xray_name": xray_name,
                    "last_trace_ids": [trace_id] if trace_id else []
                },
                metrics=metrics,
                account_id=self.account_id,
                region=self.region,
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            
            return pointer
            
        except Exception as e:
            logger.debug(f"Failed to extract pointer from segment: {e}")
            return None
    
    def _parse_resource_info(self, name: str, origin: str, resource_arn: str) -> Tuple[str, str]:
        """Parse resource type and name from segment info."""
        # Lambda detection
        if 'AWS::Lambda' in origin or 'lambda' in name.lower():
            return 'lambda', name
        
        # Step Functions detection
        elif 'AWS::STEPFUNCTIONS' in origin or 'stepfunctions' in name.lower():
            return 'stepfunctions', name
        
        # API Gateway detection
        elif 'AWS::ApiGateway' in origin or 'apigateway' in name.lower():
            return 'apigateway', name
        
        # DynamoDB detection
        elif 'AWS::DynamoDB' in origin or 'dynamodb' in name.lower():
            return 'dynamodb', name
        
        # S3 detection
        elif 'AWS::S3' in origin or 's3' in name.lower():
            return 's3', name
        
        # SQS detection
        elif 'AWS::SQS' in origin or 'sqs' in name.lower():
            return 'sqs', name
        
        # SNS detection
        elif 'AWS::SNS' in origin or 'sns' in name.lower():
            return 'sns', name
        
        # EventBridge detection
        elif 'AWS::Events' in origin or 'events' in name.lower():
            return 'eventbridge', name
        
        # VPC detection
        elif 'AWS::EC2' in origin or 'ec2' in name.lower():
            return 'vpc', name
        
        # Default fallback
        else:
            return 'unknown', name
    
    def _infer_relationship_from_subsegment(self, subsegment_name: str, subsegment: Dict[str, Any]) -> str:
        """Infer relationship type from subsegment."""
        name_lower = subsegment_name.lower()
        
        if 'lambda' in name_lower:
            return 'CALLS'
        elif 'dynamodb' in name_lower:
            return 'READS' if 'get' in name_lower or 'query' in name_lower else 'WRITES'
        elif 's3' in name_lower:
            return 'WRITES' if 'put' in name_lower else 'READS'
        elif 'sqs' in name_lower:
            return 'PUBLISHES' if 'send' in name_lower else 'SUBSCRIBES'
        elif 'sns' in name_lower:
            return 'PUBLISHES'
        elif 'stepfunctions' in name_lower:
            return 'TRIGGERS'
        else:
            return 'CALLS'  # Default relationship
    
    def _infer_relationship_from_log(self, log_message: str) -> str:
        """Infer relationship type from log message."""
        message_lower = log_message.lower()
        
        if 'calling' in message_lower or 'invoking' in message_lower:
            return 'CALLS'
        elif 'reading' in message_lower or 'getting' in message_lower or 'querying' in message_lower:
            return 'READS'
        elif 'writing' in message_lower or 'putting' in message_lower or 'updating' in message_lower:
            return 'WRITES'
        elif 'publishing' in message_lower or 'sending' in message_lower:
            return 'PUBLISHES'
        elif 'subscribing' in message_lower or 'receiving' in message_lower:
            return 'SUBSCRIBES'
        elif 'triggering' in message_lower or 'starting' in message_lower:
            return 'TRIGGERS'
        else:
            return 'CALLS'  # Default relationship
    
    def _extract_target_arn_from_log(self, log_message: str) -> Optional[str]:
        """Extract target ARN from log message using regex patterns."""
        import re
        
        # Common ARN patterns in logs
        arn_patterns = [
            r'arn:aws:[^:\s]+:[^:\s]*:[^:\s]*:[^:\s]+',
            r'arn:aws:[^:\s]+::[^:\s]+',
        ]
        
        for pattern in arn_patterns:
            match = re.search(pattern, log_message)
            if match:
                return match.group(0)
        
        return None
    
    def _calculate_xray_confidence(self, subsegment: Dict[str, Any]) -> float:
        """Calculate confidence score for X-Ray evidence."""
        base_confidence = 0.8  # X-Ray is high confidence
        
        # Adjust based on subsegment properties
        if subsegment.get('fault', False):
            base_confidence += 0.1  # Faults are more reliable
        if subsegment.get('error', False):
            base_confidence += 0.05  # Errors are more reliable
        
        return min(base_confidence, 1.0)
    
    def _calculate_log_confidence(self, log_message: str) -> float:
        """Calculate confidence score for log evidence."""
        base_confidence = 0.4  # Logs are lower confidence
        
        # Adjust based on log content
        if 'error' in log_message.lower():
            base_confidence += 0.1
        if 'exception' in log_message.lower():
            base_confidence += 0.1
        if 'arn:' in log_message:
            base_confidence += 0.1  # Explicit ARN reference
        
        return min(base_confidence, 1.0)
    
    def _extract_observability_from_segment(self, segment_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract observability info from segment."""
        observability = {}
        
        # Extract log group
        log_group = self._extract_log_group_from_segment(segment_doc)
        if log_group:
            observability['log_group'] = log_group
        
        # Extract X-Ray name
        xray_name = segment_doc.get('name', '')
        if xray_name:
            observability['xray_name'] = xray_name
        
        # Extract metric namespace
        namespace = self._extract_metric_namespace_from_segment(segment_doc)
        if namespace:
            observability['metric_namespace'] = namespace
        
        return observability
    
    def _extract_log_group_from_segment(self, segment_doc: Dict[str, Any]) -> Optional[str]:
        """Extract log group from segment."""
        # Common patterns for log groups in X-Ray
        name = segment_doc.get('name', '')
        if '/aws/lambda/' in name:
            return f"/aws/lambda/{name}"
        elif '/aws/stepfunctions/' in name:
            return f"/aws/stepfunctions/{name}"
        
        return None
    
    def _extract_metric_namespace_from_segment(self, segment_doc: Dict[str, Any]) -> Optional[str]:
        """Extract metric namespace from segment."""
        origin = segment_doc.get('origin', '')
        
        if 'AWS::Lambda' in origin:
            return 'AWS/Lambda'
        elif 'AWS::StepFunctions' in origin:
            return 'AWS/States'
        elif 'AWS::ApiGateway' in origin:
            return 'AWS/ApiGateway'
        elif 'AWS::DynamoDB' in origin:
            return 'AWS/DynamoDB'
        elif 'AWS::S3' in origin:
            return 'AWS/S3'
        elif 'AWS::SQS' in origin:
            return 'AWS/SQS'
        elif 'AWS::SNS' in origin:
            return 'AWS/SNS'
        elif 'AWS::Events' in origin:
            return 'AWS/Events'
        
        return None
    
    def _extract_metrics_from_segment(self, segment_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metrics info from segment."""
        metrics = {}
        
        namespace = self._extract_metric_namespace_from_segment(segment_doc)
        if namespace:
            metrics['namespace'] = namespace
            
            # Common metric names by service
            if namespace == 'AWS/Lambda':
                metrics['names'] = ['Duration', 'Errors', 'Invocations', 'Throttles']
            elif namespace == 'AWS/States':
                metrics['names'] = ['Executions', 'ExecutionTime', 'ExecutionsFailed']
            elif namespace == 'AWS/ApiGateway':
                metrics['names'] = ['Count', 'Latency', '4XXError', '5XXError']
            elif namespace == 'AWS/DynamoDB':
                metrics['names'] = ['ConsumedReadCapacityUnits', 'ConsumedWriteCapacityUnits', 'ThrottledRequests']
        
        return metrics
    
    def _extract_tags_from_segment(self, segment_doc: Dict[str, Any]) -> Dict[str, str]:
        """Extract tags from segment (if available)."""
        # X-Ray segments don't typically contain tags
        # This would need to be enriched from other sources
        return {}
    
    def _extract_resource_type_from_arn(self, arn: str) -> str:
        """Extract resource type from ARN."""
        if not arn.startswith('arn:aws:'):
            return 'unknown'
        
        parts = arn.split(':')
        if len(parts) >= 3:
            return parts[2]  # Service name
        
        return 'unknown'
