#!/usr/bin/env python3
"""
Sherlock Core - Memory System
Copyright (C) 2025 Christian Gennaro Faraone

Memory system for querying external investigation storage.
Provides read-only access to historical investigations for RAG enhancement.
"""

from .client import MemoryClient
from .models import MemoryResult

__all__ = ["MemoryClient", "MemoryResult"]
