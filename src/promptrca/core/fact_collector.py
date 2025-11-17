#!/usr/bin/env python3
"""
Fact Collection Service for PromptRCA

Coordinates the execution of specialists to collect facts about AWS resources
and system behavior during investigations.

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

import asyncio
from typing import Dict, Any, List
from ..models import Fact
from ..specialists import (
    BaseSpecialist, InvestigationContext,
    LambdaSpecialist, APIGatewaySpecialist,
    StepFunctionsSpecialist, TraceSpecialist,
    DynamoDBSpecialist, EventBridgeSpecialist,
    ECSSpecialist, RDSSpecialist
)
from ..utils import get_logger

logger = get_logger(__name__)


class FactCollector:
    """
    Coordinates specialist execution to collect facts about AWS resources.
    
    This service manages the parallel execution of specialists and ensures
    consistent fact collection across different resource types.
    """
    
    def __init__(self):
        self.specialists = {
            'lambda': LambdaSpecialist(),
            'apigateway': APIGatewaySpecialist(),
            'stepfunctions': StepFunctionsSpecialist(),
            'dynamodb': DynamoDBSpecialist(),
            'dynamodb_table': DynamoDBSpecialist(),
            'eventbridge': EventBridgeSpecialist(),
            'eventbridge_rule': EventBridgeSpecialist(),
            'events': EventBridgeSpecialist(),
            'events_rule': EventBridgeSpecialist(),
            'ecs': ECSSpecialist(),
            'ecs_cluster': ECSSpecialist(),
            'ecs_service': ECSSpecialist(),
            'ecs_task': ECSSpecialist(),
            'rds': RDSSpecialist(),
            'rds_instance': RDSSpecialist(),
            'aurora': RDSSpecialist(),
            'aurora_cluster': RDSSpecialist(),
            'database': RDSSpecialist()
        }
        self.trace_specialist = TraceSpecialist()
        self.max_facts_total = 50  # Global limit
    
    async def collect_facts(self, resources: List[Dict[str, Any]], 
                          context: InvestigationContext) -> List[Fact]:
        """
        Collect facts from all resources using appropriate specialists.
        
        Args:
            resources: List of discovered resources to analyze
            context: Investigation context with trace IDs, region, etc.
            
        Returns:
            List of facts collected from all specialists
        """
        facts = []
        
        # Collect facts from resource specialists
        resource_facts = await self._collect_resource_facts(resources, context)
        facts.extend(resource_facts)
        
        # Collect facts from trace analysis
        trace_facts = await self._collect_trace_facts(context)
        facts.extend(trace_facts)
        
        # Limit total facts to prevent overwhelming the AI
        return facts[:self.max_facts_total]
    
    async def _collect_resource_facts(self, resources: List[Dict[str, Any]], 
                                    context: InvestigationContext) -> List[Fact]:
        """Collect facts from resource-specific specialists."""
        tasks = []
        
        for resource in resources:
            resource_type = (resource.get('type') or '').lower()
            specialist = self.specialists.get(resource_type)
            
            if specialist:
                logger.info(f"   → Scheduling {resource_type} specialist for {resource.get('name')}")
                tasks.append(specialist.analyze(resource, context))
            else:
                logger.debug(f"No specialist available for resource type: {resource_type}")
        
        if not tasks:
            logger.info("   → No specialist tasks to execute")
            return []
        
        logger.info(f"   → Executing {len(tasks)} specialist tasks in parallel...")
        
        # Execute all specialists in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        facts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Specialist task {i} failed: {result}")
            elif isinstance(result, list):
                facts.extend(result)
            else:
                logger.warning(f"Unexpected result type from specialist {i}: {type(result)}")
        
        logger.info(f"   ✓ Collected {len(facts)} facts from resource specialists")
        return facts
    
    async def _collect_trace_facts(self, context: InvestigationContext) -> List[Fact]:
        """Collect facts from X-Ray trace analysis."""
        if not context.trace_ids:
            return []
        
        logger.info(f"   → Analyzing {len(context.trace_ids)} traces...")
        
        tasks = []
        for trace_id in context.trace_ids:
            tasks.append(self.trace_specialist.analyze_trace(trace_id, context))
        
        # Execute trace analysis in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        facts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Trace analysis {i} failed: {result}")
            elif isinstance(result, list):
                facts.extend(result)
        
        logger.info(f"   ✓ Collected {len(facts)} facts from trace analysis")
        return facts
    
    def add_specialist(self, resource_type: str, specialist: BaseSpecialist):
        """Add a new specialist for a resource type."""
        self.specialists[resource_type] = specialist
        logger.info(f"Added specialist for resource type: {resource_type}")
    
    def get_supported_resource_types(self) -> List[str]:
        """Get list of all supported resource types."""
        return list(self.specialists.keys())