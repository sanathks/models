#!/usr/bin/env python3
"""
Caching system for command analysis results.
"""

import json
import os
import time
import tempfile
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import asdict

from .models import CommandAnalysis
from .version import VersionDetector


class JSONCache:
    """Version-based JSON cache for command analysis results"""
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.basher")
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "command_cache.json"
        self._cache_data = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk with error recovery"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, PermissionError):
            # Cache corrupted or inaccessible, start fresh
            pass
        
        return {}
    
    def _save_cache(self) -> None:
        """Atomically save cache to disk"""
        try:
            # Write to temporary file first for atomic operation
            with tempfile.NamedTemporaryFile(
                mode='w', 
                dir=self.cache_dir, 
                delete=False,
                suffix='.tmp'
            ) as tmp_file:
                json.dump(self._cache_data, tmp_file, indent=2)
                tmp_file_path = tmp_file.name
            
            # Atomic move
            os.replace(tmp_file_path, self.cache_file)
        except Exception as e:
            # Clean up temp file if it exists
            try:
                if 'tmp_file_path' in locals():
                    os.unlink(tmp_file_path)
            except:
                pass
            raise e
    
    def get(self, command: str) -> Optional[CommandAnalysis]:
        """Get cached analysis if version matches current version"""
        if command not in self._cache_data:
            return None
        
        cached_entry = self._cache_data[command]
        current_version = VersionDetector.detect_version(command)
        cached_version = cached_entry.get('version')
        
        # Check if version matches
        if current_version == cached_version:
            try:
                return CommandAnalysis(**cached_entry)
            except Exception:
                # Cached data format changed, remove entry
                del self._cache_data[command]
                self._save_cache()
        else:
            # Version changed, remove stale entry
            del self._cache_data[command]
            self._save_cache()
        
        return None
    
    def set(self, command: str, analysis: CommandAnalysis) -> None:
        """Cache analysis result with current timestamp"""
        try:
            # Update timestamp
            analysis.cached_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            
            # Store in cache
            self._cache_data[command] = asdict(analysis)
            self._save_cache()
        except Exception:
            # Don't fail if caching fails
            pass
    
    def clear(self) -> None:
        """Clear entire cache"""
        self._cache_data = {}
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
        except Exception:
            pass