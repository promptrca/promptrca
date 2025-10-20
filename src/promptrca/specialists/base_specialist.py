#!/usr/bin/env python3
"""
Base Specialist Interface for PromptRCA

Defines the standard interface for all AWS service specialists.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from ..models import Fact
from ..utils import get_logger

logger = get_logger(__name__)


@dataclass
class InvestigationContext:
    """Context information passed to specialists during investigation."""
    trace_ids: List[str]
    region: str
    parsed_inputs: Any  # ParsedInputs object
    original_input: Optional[str] = None
    investigation_id: Optional[str] = None


class BaseSpecialist(ABC):
    """
    Abstract base class for all AWS service specialists.
    
    Each specialist is responsible for analyzing a specific AWS service
    and generating facts about its configuration, health, and potential issues.
    """
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.max_facts_per_resource = 10  # Configurable limit
    
    @abstractmethod
    async def analyze(self, resource: Dict[str, Any], context: InvestigationContext) -> List[Fact]:
        """
        Analyze a resource and generate facts about its state and potential issues.
        
        Args:
            resource: Resource information (type, name, metadata, etc.)
            context: Investigation context (trace IDs, region, etc.)
            
        Returns:
            List of facts discovered about the resource
        """
        pass
    
    @property
    @abstractmethod
    def supported_resource_types(self) -> List[str]:
        """Return list of resource types this specialist can handle."""
        pass
    
    def can_analyze(self, resource_type: str) -> bool:
        """Check if this specialist can analyze the given resource type."""
        return resource_type.lower() in [t.lower() for t in self.supported_resource_types]
    
    def _create_fact(self, source: str, content: str, confidence: float, 
                     metadata: Optional[Dict[str, Any]] = None) -> Fact:
        """Helper method to create facts with consistent formatting."""
        return Fact(
            source=source,
            content=content,
            confidence=confidence,
            metadata=metadata or {}
        )
    
    def _limit_facts(self, facts: List[Fact]) -> List[Fact]:
        """Limit the number of facts to prevent overwhelming the analysis."""
        return facts[:self.max_facts_per_resource]