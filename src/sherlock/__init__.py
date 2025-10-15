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

Sherlock - AI Root-Cause Investigator for AWS Serverless
"""

from .models import Fact, Hypothesis, Advice, InvestigationReport, InvestigationTarget
from .clients.aws_client import AWSClient
from .agents.hypothesis_agent import HypothesisAgent
from .agents.advice_agent import AdviceAgent
from .core.investigator import SherlockInvestigator

__version__ = "1.0.0"
__author__ = "Sherlock Team"

__all__ = [
    "Fact",
    "Hypothesis", 
    "Advice",
    "InvestigationReport",
    "InvestigationTarget",
    "AWSClient",
    "HypothesisAgent",
    "AdviceAgent",
    "SherlockInvestigator"
]
