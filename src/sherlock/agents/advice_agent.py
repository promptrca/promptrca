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

from typing import List, Optional
from ..models import Fact, Hypothesis, Advice
from ..memory import MemoryResult


class AdviceAgent:
    """Agent responsible for generating actionable advice."""
    
    def __init__(self):
        """Initialize the advice agent."""
        pass
    
    def generate_advice(self, facts: List[Fact], hypotheses: List[Hypothesis], memory_results: Optional[List[MemoryResult]] = None) -> List[Advice]:
        """Generate actionable advice based on facts and hypotheses, with optional memory enhancement."""
        # Cost tracking removed
        
        advice = []
        advice_given = set()  # Track which advice we've already given
        
        for hyp in hypotheses:
            if hyp.type == "timeout" and "timeout" not in advice_given:
                advice.append(Advice(
                    title="Optimize Function Performance",
                    description="Increase memory allocation or optimize code to reduce execution time",
                    priority="high",
                    category="performance"
                ))
                advice_given.add("timeout")
            
            elif hyp.type == "error_rate" and "error_rate" not in advice_given:
                advice.append(Advice(
                    title="Investigate Error Sources",
                    description="Check logs and metrics to identify the root cause of increased errors",
                    priority="high",
                    category="reliability"
                ))
                advice_given.add("error_rate")
            
            elif hyp.type == "resource_constraint" and "resource_constraint" not in advice_given:
                advice.append(Advice(
                    title="Increase Resource Allocation",
                    description="Consider increasing Lambda memory or other resources to improve performance",
                    priority="high",
                    category="performance"
                ))
                advice_given.add("resource_constraint")
            
            elif hyp.type == "code_bug":
                if "division by zero" in hyp.description.lower() and "division_by_zero" not in advice_given:
                    advice.append(Advice(
                        title="Fix Division by Zero Bug",
                        description="Add proper validation to check for empty lists before division operations. Use conditional checks like 'if len(data) > 0' before calculating averages.",
                        priority="critical",
                        category="bug_fix"
                    ))
                    advice_given.add("division_by_zero")
                elif "empty list" in hyp.description.lower() and "empty_list_validation" not in advice_given:
                    advice.append(Advice(
                        title="Add Empty List Validation",
                        description="Add proper input validation to handle empty lists gracefully. Check list length before operations like max(), min(), or division.",
                        priority="high",
                        category="bug_fix"
                    ))
                    advice_given.add("empty_list_validation")
                elif "error handling" in hyp.description.lower() and "error_handling" not in advice_given:
                    advice.append(Advice(
                        title="Add Error Handling",
                        description="Wrap critical operations in try-catch blocks to handle potential exceptions gracefully and provide meaningful error messages.",
                        priority="high",
                        category="code_quality"
                    ))
                    advice_given.add("error_handling")
                elif "code_bug" not in advice_given:
                    advice.append(Advice(
                        title="Review Code Logic",
                        description="Review the identified code issues and implement proper validation and error handling to prevent runtime errors.",
                        priority="high",
                        category="code_quality"
                    ))
                    advice_given.add("code_bug")
        
        # Add generic advice if no specific advice was generated
        if not advice:
            advice.append(Advice(
                title="Monitor System Health",
                description="Continue monitoring metrics and logs for any anomalies",
                priority="medium",
                category="monitoring"
            ))
        
        # Enhance advice with memory if available
        if memory_results:
            advice = self._prioritize_advice_with_memory(advice, memory_results)
        
        return advice
    
    def _prioritize_advice_with_memory(self, advice: List[Advice], memory_results: List[MemoryResult]) -> List[Advice]:
        """Reorder advice based on historical effectiveness"""
        if not memory_results:
            return advice
        
        # Track which advice worked in similar cases
        advice_effectiveness = {}
        for mem in memory_results:
            if mem.outcome == "resolved":
                advice_effectiveness[mem.advice_summary] = advice_effectiveness.get(mem.advice_summary, 0) + 1
        
        # Boost priority for proven advice
        for adv in advice:
            for proven_advice, count in advice_effectiveness.items():
                if self._is_similar_advice(adv.description, proven_advice):
                    # Upgrade priority if it worked multiple times
                    if count >= 3 and adv.priority != "critical":
                        adv.priority = "high"
                    adv.description += f"\n\n✓ This approach resolved {count} similar issues in the past."
        
        return advice
    
    def _is_similar_advice(self, adv1: str, adv2: str) -> bool:
        """Check if two pieces of advice are similar (simple keyword matching)"""
        keywords1 = set(adv1.lower().split())
        keywords2 = set(adv2.lower().split())
        overlap = len(keywords1 & keywords2)
        return overlap > max(len(keywords1), len(keywords2)) * 0.5
