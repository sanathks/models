#!/usr/bin/env python3
"""
Version detection utilities for CLI tools.
"""

import subprocess
import shutil
import os
import re
from typing import Optional


class VersionDetector:
    """Detects CLI tool versions for intelligent cache invalidation"""
    
    @staticmethod
    def detect_version(command: str) -> Optional[str]:
        """Try multiple strategies to detect command version with optimized timeouts"""
        strategies = [
            lambda: VersionDetector._try_version_flag(command, "--version"),
            lambda: VersionDetector._try_version_flag(command, "-v"),
            lambda: VersionDetector._try_version_flag(command, "version"),
            lambda: VersionDetector._get_file_modification_time(command)  # Skip help parsing for speed
        ]
        
        for strategy in strategies:
            try:
                version = strategy()
                if version:
                    return version
            except Exception:
                continue
        
        return "unknown"
    
    @staticmethod
    def _try_version_flag(command: str, flag: str) -> Optional[str]:
        """Try a specific version flag with reduced timeout"""
        try:
            result = subprocess.run(
                [command, flag],
                capture_output=True,
                text=True,
                timeout=2  # Reduced from 5 to 2 seconds
            )
            
            if result.returncode == 0:
                return VersionDetector._extract_version(result.stdout)
            elif result.stderr:
                return VersionDetector._extract_version(result.stderr)
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def _get_file_modification_time(command: str) -> str:
        """Use file modification time as version fallback"""
        try:
            cmd_path = shutil.which(command)
            if cmd_path:
                stat = os.stat(cmd_path)
                return f"mtime-{int(stat.st_mtime)}"
        except Exception:
            pass
        
        return "unknown"
    
    @staticmethod
    def _extract_version(text: str) -> Optional[str]:
        """Extract version number from text using common patterns"""
        patterns = [
            r'version\s+([0-9]+\.[0-9]+\.[0-9]+)',
            r'v?([0-9]+\.[0-9]+\.[0-9]+)',
            r'([0-9]+\.[0-9]+)',
            r'Version:\s*([^\s\n]+)',
            r'version\s+([^\s\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None