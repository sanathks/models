#!/usr/bin/env python3
"""
Basher - Intelligent CLI Command Assistant

A comprehensive CLI command assistant that uses intelligent analysis techniques
to understand CLI tools and construct accurate commands from natural language queries.
"""

from .basher import Basher
from .models import CommandAnalysis
from .analyzer import CLIAnalyzer
from .cache import JSONCache
from .version import VersionDetector
from .progress import ProgressIndicator, timing_decorator
from .config import SYSTEM_COMMANDS, DANGEROUS_PATTERNS

__version__ = "0.2.0"
__author__ = "Sanath"

# Main exports
__all__ = [
    "Basher",
    "CommandAnalysis", 
    "CLIAnalyzer",
    "JSONCache",
    "VersionDetector",
    "ProgressIndicator",
    "timing_decorator",
    "SYSTEM_COMMANDS",
    "DANGEROUS_PATTERNS"
]
