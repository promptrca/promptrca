#!/usr/bin/env python3
"""
PromptRCA Core - AI-powered root cause analysis for AWS infrastructure
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

Contact: christiangenn99+promptrca@gmail.com

"""

from typing import Any, Dict, List, Optional

from ..models import Fact


def clamp_confidence(value: Any, default: float = 0.7) -> float:
    """Clamp a confidence value to [0, 1]; on error, return default."""
    try:
        v = float(value)
        if v < 0.0:
            return 0.0
        if v > 1.0:
            return 1.0
        return v
    except Exception:
        return default


def normalize_fact_item(item: Any, source: str, default_confidence: float = 0.7) -> Optional[Fact]:
    """Normalize a single fact-like item into a Fact object.

    Accepts dict or string. Ensures non-empty content and clamps confidence.
    Returns None if content is empty after best effort.
    """
    if item is None:
        return None

    if isinstance(item, dict):
        content = str(item.get("content", "")).strip()
        conf = clamp_confidence(item.get("confidence", default_confidence), default_confidence)
        metadata = item.get("metadata", {}) or {}
        if not content:
            # Try to synthesize content from metadata if present
            if metadata:
                content = f"Fact from {source}: {str(metadata)[:160]}"
            else:
                content = "(no content)"
        return Fact(source=source, content=content, confidence=conf, metadata=metadata)

    # For raw strings or other types, coerce to string content
    content = str(item).strip()
    if not content:
        return None
    return Fact(source=source, content=content, confidence=default_confidence, metadata={})


def normalize_facts(items: Any, source: str, default_confidence: float = 0.7) -> List[Fact]:
    """Normalize a list/iterable of fact-like items to a list of Fact objects."""
    facts: List[Fact] = []
    if items is None:
        return facts
    # Accept a single dict or string
    if not isinstance(items, (list, tuple)):
        items = [items]
    for it in items:
        f = normalize_fact_item(it, source, default_confidence)
        if f is not None:
            facts.append(f)
    return facts

