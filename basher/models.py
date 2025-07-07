#!/usr/bin/env python3
"""
Data models and classes for Basher.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class CommandAnalysis:
    """Result of CLI command analysis"""
    command: str
    available: bool
    version: Optional[str] = None
    framework: Optional[str] = None
    capabilities: Dict[str, Any] = None
    subcommands: List[str] = None
    examples: List[str] = None
    risks: List[str] = None
    source_method: str = "unknown"
    cached_at: str = None
    error: Optional[str] = None