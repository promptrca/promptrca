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

Input Parser Agent for Multi-Input Sherlock
Parses free text and structured inputs to extract investigation targets
"""

import re
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from ..models import Fact
from ..utils import get_logger
from strands import Agent
from ..utils.config import create_bedrock_model

logger = get_logger(__name__)


@dataclass
class ParsedResource:
    """Represents a parsed AWS resource from input."""
    type: str
    name: str
    region: Optional[str] = None
    arn: Optional[str] = None
    confidence: float = 0.8
    source: str = "input_parser"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "name": self.name,
            "region": self.region,
            "arn": self.arn,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata
        }


@dataclass
class ParsedInputs:
    """Represents parsed investigation inputs."""
    primary_targets: List[ParsedResource] = field(default_factory=list)
    trace_ids: List[str] = field(default_factory=list)
    error_messages: List[str] = field(default_factory=list)
    business_context: Dict[str, Any] = field(default_factory=dict)
    time_range: Optional[Dict[str, str]] = None
    confidence: float = 0.8


class InputParserAgent:
    """Agent that parses various input formats to extract investigation targets."""
    
    def __init__(self):
        """Initialize the input parser agent."""
        # Initialize AI model for intelligent parsing
        self.model = create_bedrock_model()
        
        # X-Ray trace ID pattern (reliable regex)
        self.trace_id_pattern = r'1-[a-f0-9]{8}-[a-f0-9]{24}'
        
        # ARN pattern (reliable regex)
        self.arn_pattern = r'arn:aws:[a-z0-9-]+:[a-z0-9-]*:[0-9]*:[a-zA-Z0-9/_-]+'
        
        # Region patterns
        self.region_pattern = r'(us|eu|ap|ca|sa|af|me)-(east|west|central|north|south)-[0-9]+'
        
        # Resource name patterns for fallback parsing
        self.resource_patterns = {
            'lambda': [r'lambda[:\s]+([a-zA-Z0-9_-]+)', r'function[:\s]+([a-zA-Z0-9_-]+)'],
            'apigateway': [r'api[:\s]+([a-zA-Z0-9_-]+)', r'gateway[:\s]+([a-zA-Z0-9_-]+)'],
            'stepfunctions': [r'state\s*machine[:\s]+([a-zA-Z0-9_-]+)', r'step\s*functions?[:\s]+([a-zA-Z0-9_-]+)'],
            'dynamodb': [r'table[:\s]+([a-zA-Z0-9_-]+)', r'dynamodb[:\s]+([a-zA-Z0-9_-]+)'],
        }
    
    def parse_inputs(self, inputs: Union[str, Dict[str, Any]], region: str = "eu-west-1") -> ParsedInputs:
        """Parse various input formats to extract investigation targets."""
        if isinstance(inputs, str):
            return self._parse_free_text(inputs, region)
        elif isinstance(inputs, dict):
            return self._parse_structured_input(inputs, region)
        else:
            raise ValueError("Input must be string (free text) or dict (structured)")
    
    def _parse_free_text(self, text: str, region: str) -> ParsedInputs:
        """Parse free text input using AI-based extraction."""
        logger.info("🔍 Parsing free text input with AI...")
        
        # Extract X-Ray trace IDs and ARNs (reliable with regex)
        trace_ids = re.findall(self.trace_id_pattern, text)
        arns = re.findall(self.arn_pattern, text)
        
        # Use AI to intelligently extract AWS resources
        primary_targets = self._ai_extract_resources(text, region, arns)
        
        # Extract error messages and context with AI
        error_messages = self._ai_extract_errors(text)
        
        # Extract business context
        business_context = self._extract_business_context(text)
        
        # Extract time range if mentioned
        time_range = self._extract_time_range(text)
        
        return ParsedInputs(
            primary_targets=primary_targets,
            trace_ids=trace_ids,
            error_messages=error_messages,
            business_context=business_context,
            time_range=time_range,
            confidence=0.9  # Higher confidence with AI
        )
    
    def _extract_json(self, s: str):
        """Extract JSON from AI response, handling markdown code blocks."""
        try:
            text = s.strip()
            # Remove markdown code blocks if present
            if "```json" in text:
                text = text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in text:
                text = text.split("```", 1)[1].split("```", 1)[0]
            # Try to find JSON object/array
            text = text.strip()
            if text.startswith('[') or text.startswith('{'):
                return json.loads(text)
            # Try to find JSON in the text
            start_idx = text.find('[') if '[' in text else text.find('{')
            if start_idx != -1:
                # Find matching closing bracket
                if text[start_idx] == '[':
                    end_idx = text.rfind(']') + 1
                else:
                    end_idx = text.rfind('}') + 1
                if end_idx > start_idx:
                    return json.loads(text[start_idx:end_idx])
            return None
        except Exception as e:
            logger.error(f"JSON extraction failed: {e}")
            return None

    def _ai_extract_resources(self, text: str, region: str, arns: List[str]) -> List[ParsedResource]:
        """Use AI to extract AWS resource names and types from free text."""
        prompt = f"""Extract AWS resource identifiers from text: {text}

EXTRACT ONLY:
- Resource names (explicit mentions)
- ARNs
- Resource IDs

DO NOT extract generic service names without specific identifiers.

OUTPUT: JSON [{{"type": "service_type", "name": "resource_name", "arn": "arn_if_present"}}]
Return [] if no explicit resources found."""

        try:
            agent = Agent(model=self.model)
            response = agent(prompt)
            
            # Parse the AI response - extract content from AgentResult
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            resources_data = self._extract_json(response_text)
            
            resources = []
            if not resources_data:
                logger.info("No resources extracted by AI")
                resources_data = []
            for item in resources_data:
                resources.append(ParsedResource(
                    type=item.get('type', 'unknown'),
                    name=item.get('name', ''),
                    region=region,
                    arn=item.get('arn'),
                    confidence=0.85,
                    source="ai_extraction",
                    metadata={"original_text": text[:200]}
                ))
            
            logger.info(f"✅ AI extracted {len(resources)} resources")
            return resources
            
        except Exception as e:
            logger.error(f"❌ AI extraction failed: {e}")
            # Fallback: extract from ARNs if available
            resources = []
            for arn in arns:
                resource_type, resource_name = self._parse_arn(arn)
                if resource_type and resource_name:
                    resources.append(ParsedResource(
                        type=resource_type,
                        name=resource_name,
                        region=region,
                        arn=arn,
                        confidence=0.95,
                        source="arn_parsing",
                        metadata={"arn": arn}
                    ))
            return resources
    
    def _ai_extract_errors(self, text: str) -> List[str]:
        """Use AI to extract error messages and issue descriptions."""
        prompt = f"""Extract error messages from: {text}

OUTPUT: JSON array of error descriptions
Example: ["500 errors", "Permission denied"]"""

        try:
            agent = Agent(model=self.model)
            response = agent(prompt)
            
            # Extract content from AgentResult
            response_text = str(response.content) if hasattr(response, 'content') else str(response)
            errors = self._extract_json(response_text)
            if not errors:
                errors = [text] if any(keyword in text.lower() for keyword in ['error', 'fail', '500', '400', 'issue', 'problem']) else []
            return errors if isinstance(errors, list) else [text]
        except Exception as e:
            logger.error(f"❌ AI error extraction failed: {e}")
            # Fallback: return the whole text if it mentions errors
            if any(keyword in text.lower() for keyword in ['error', 'fail', '500', '400', 'issue', 'problem']):
                return [text]
            return []
    
    def _parse_arn(self, arn: str) -> tuple[Optional[str], Optional[str]]:
        """Parse an ARN to extract resource type and name."""
        try:
            parts = arn.split(':')
            service = parts[2] if len(parts) > 2 else None
            
            # Map AWS service names to our types
            service_map = {
                'lambda': 'lambda',
                'execute-api': 'apigateway',
                'states': 'stepfunctions',
                'dynamodb': 'dynamodb',
                's3': 's3',
                'sns': 'sns',
                'sqs': 'sqs'
            }
            
            resource_type = service_map.get(service)
            
            # Extract resource name (last part)
            if len(parts) >= 6:
                resource_part = parts[-1]
                # Handle table/function prefix
                resource_name = resource_part.split('/')[-1].split(':')[-1]
                return resource_type, resource_name
            
            return None, None
        except Exception:
            return None, None
    
    def _parse_structured_input(self, inputs: Dict[str, Any], region: str) -> ParsedInputs:
        """Parse structured input format."""
        logger.info("🔍 Parsing structured input...")
        
        primary_targets = []
        
        # Parse primary targets
        if 'primary_targets' in inputs:
            for target in inputs['primary_targets']:
                primary_targets.append(ParsedResource(
                    type=target.get('type', 'unknown'),
                    name=target.get('name', ''),
                    region=target.get('region', region),
                    arn=target.get('arn'),
                    confidence=0.9,
                    source="structured_input",
                    metadata=target.get('metadata', {})
                ))
        
        # Parse additional resources from other fields
        for field_name, field_value in inputs.items():
            if field_name in ['primary_targets', 'trace_ids', 'error_messages', 'time_range', 'context']:
                continue
                
            if isinstance(field_value, str):
                # Try to parse as resource
                for resource_type, patterns in self.resource_patterns.items():
                    for pattern in patterns:
                        match = re.search(pattern, field_value, re.IGNORECASE)
                        if match:
                            primary_targets.append(ParsedResource(
                                type=resource_type,
                                name=match.group(1),
                                region=region,
                                confidence=0.7,
                                source="structured_field_parsing",
                                metadata={"field": field_name, "value": field_value}
                            ))
                            break
        
        return ParsedInputs(
            primary_targets=primary_targets,
            trace_ids=inputs.get('trace_ids', []),
            error_messages=inputs.get('error_messages', []),
            business_context=inputs.get('context', {}),
            time_range=inputs.get('time_range'),
            confidence=0.9
        )
    
    def _extract_region_from_context(self, text: str, resource_name: str) -> Optional[str]:
        """Extract region from context around resource name."""
        # Look for region patterns near the resource name
        resource_pos = text.lower().find(resource_name.lower())
        if resource_pos == -1:
            return None
        
        # Check 100 characters before and after the resource name
        start = max(0, resource_pos - 100)
        end = min(len(text), resource_pos + len(resource_name) + 100)
        context = text[start:end]
        
        region_match = re.search(self.region_pattern, context, re.IGNORECASE)
        if region_match:
            return region_match.group(0)
        
        return None
    
    def _extract_business_context(self, text: str) -> Dict[str, Any]:
        """Extract business context from free text."""
        context = {}
        
        # Extract urgency/priority
        urgency_keywords = {
            'critical': ['critical', 'urgent', 'emergency', 'down', 'outage'],
            'high': ['high', 'important', 'severe', 'major'],
            'medium': ['medium', 'moderate', 'minor'],
            'low': ['low', 'minor', 'cosmetic']
        }
        
        text_lower = text.lower()
        for urgency, keywords in urgency_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                context['urgency'] = urgency
                break
        
        # Extract business impact
        impact_keywords = {
            'revenue': ['revenue', 'money', 'sales', 'payment', 'checkout', 'billing'],
            'users': ['users', 'customers', 'clients', 'subscribers'],
            'operations': ['operations', 'process', 'workflow', 'automation'],
            'compliance': ['compliance', 'security', 'audit', 'regulatory']
        }
        
        for impact_type, keywords in impact_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                context['business_impact'] = impact_type
                break
        
        # Extract service area
        service_keywords = {
            'payment': ['payment', 'billing', 'checkout', 'transaction'],
            'auth': ['authentication', 'login', 'auth', 'security'],
            'data': ['data', 'database', 'storage', 'analytics'],
            'api': ['api', 'service', 'microservice', 'endpoint']
        }
        
        for service_type, keywords in service_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                context['service_area'] = service_type
                break
        
        return context
    
    def _extract_time_range(self, text: str) -> Optional[Dict[str, str]]:
        """Extract time range from free text."""
        # Look for time patterns
        time_patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)',
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            r'(today|yesterday|this\s+week|last\s+week)',
            r'(\d+\s+(minutes?|hours?|days?)\s+ago)',
        ]
        
        # This is a simplified implementation
        # In a real system, you'd use a more sophisticated time parsing library
        return None
    
    def generate_facts(self, parsed_inputs: ParsedInputs) -> List[Fact]:
        """Generate facts from parsed inputs."""
        facts = []
        
        # Add facts for each discovered resource
        for resource in parsed_inputs.primary_targets:
            facts.append(Fact(
                source="input_parser",
                content=f"Discovered {resource.type}: {resource.name}",
                confidence=resource.confidence,
                metadata={
                    "resource_type": resource.type,
                    "resource_name": resource.name,
                    "region": resource.region,
                    "arn": resource.arn,
                    "source": resource.source,
                    "parsing_metadata": resource.metadata
                }
            ))
        
        # Add facts for trace IDs
        for trace_id in parsed_inputs.trace_ids:
            facts.append(Fact(
                source="input_parser",
                content=f"X-Ray trace ID provided: {trace_id}",
                confidence=0.9,
                metadata={"trace_id": trace_id, "source": "user_input"}
            ))
        
        # Add facts for error messages
        for error in parsed_inputs.error_messages:
            facts.append(Fact(
                source="input_parser",
                content=f"Error reported: {error}",
                confidence=0.8,
                metadata={"error_message": error, "source": "user_input"}
            ))
        
        # Add business context facts
        if parsed_inputs.business_context:
            facts.append(Fact(
                source="input_parser",
                content=f"Business context: {parsed_inputs.business_context}",
                confidence=0.7,
                metadata={"business_context": parsed_inputs.business_context, "source": "user_input"}
            ))
        
        return facts
