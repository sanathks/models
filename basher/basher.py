#!/usr/bin/env python3
"""
Basher - Intelligent CLI Command Assistant

A comprehensive CLI command assistant that uses intelligent analysis techniques
to understand CLI tools and construct accurate commands from natural language queries.

Features:
- Multi-layered CLI analysis (completion data, framework detection, help parsing)
- Version-based caching for fast responses
- Natural language to command construction
- Safety warnings for risky operations
- Comprehensive command hierarchy analysis

Author: AI Assistant
License: MIT
"""

import json
import subprocess
import shutil
import re
import os
import time
import tempfile
import functools
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import ollama
except ImportError:
    print("Error: ollama package not found. Install with: pip install ollama")
    exit(1)

# =============================================================================
# PERFORMANCE MONITORING & PROGRESS
# =============================================================================

def timing_decorator(func):
    """Decorator to measure function execution time"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"⧖ {func.__name__} took {end-start:.2f}s")
        return result
    return wrapper

class ProgressIndicator:
    """Dynamic progress indicator that updates in place"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.current_message = ""
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_index = 0
        self.spinning = False
        self.spinner_thread = None
        self.stop_event = threading.Event()
    
    def update(self, message: str, clear_previous: bool = True):
        """Update progress message, optionally clearing previous line"""
        if not self.enabled:
            return
        
        if clear_previous and self.current_message:
            # Clear the current line
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
        
        self.current_message = message
        print(f"\r{message}", end='', flush=True)
    
    def start_spinner(self, message: str):
        """Start continuous spinner animation"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any existing spinner
        self.current_message = message
        self.spinning = True
        self.stop_event.clear()
        self.spinner_thread = threading.Thread(target=self._animate_spinner)
        self.spinner_thread.daemon = True
        self.spinner_thread.start()
    
    def stop_spinner(self):
        """Stop the spinner animation"""
        if self.spinner_thread and self.spinning:
            self.spinning = False
            self.stop_event.set()
            self.spinner_thread.join(timeout=0.5)
            self.spinner_thread = None
    
    def _animate_spinner(self):
        """Internal method to animate the spinner"""
        while self.spinning and not self.stop_event.is_set():
            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
            self.spinner_index += 1
            full_message = f"{spinner} {self.current_message}"
            
            # Clear and update the line
            print(f"\r{' ' * 80}\r{full_message}", end='', flush=True)
            
            if self.stop_event.wait(0.1):  # 100ms delay between frames
                break
    
    def update_with_spinner(self, message: str):
        """Update with animated spinner (legacy method for compatibility)"""
        if not self.enabled:
            return
        
        spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
        self.spinner_index += 1
        full_message = f"{spinner} {message}"
        
        if self.current_message:
            # Clear the current line
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
        
        self.current_message = full_message
        print(f"\r{full_message}", end='', flush=True)
    
    def complete(self, final_message: str = None):
        """Complete progress and optionally show final message"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any running spinner
        
        # Clear the current line more thoroughly
        print(f"\r{' ' * 80}\r", end='', flush=True)
        
        if final_message:
            print(final_message)
        
        self.current_message = ""
    
    def clear(self):
        """Clear current progress line"""
        if not self.enabled:
            return
        
        self.stop_spinner()  # Stop any running spinner
        
        if self.current_message:
            print(f"\r{' ' * len(self.current_message)}\r", end='', flush=True)
            self.current_message = ""

# =============================================================================
# CONSTANTS AND CONFIGURATION
# =============================================================================

# System commands that don't need deep analysis
SYSTEM_COMMANDS = {
    'ls', 'cd', 'cp', 'mv', 'rm', 'cat', 'grep', 'find', 'ps', 'top', 'df', 'du',
    'chmod', 'chown', 'mkdir', 'touch', 'head', 'tail', 'less', 'more', 'sort',
    'uniq', 'wc', 'awk', 'sed', 'tar', 'gzip', 'gunzip', 'zip', 'unzip', 'curl',
    'wget', 'ssh', 'scp', 'rsync', 'mount', 'umount', 'ping', 'traceroute',
    'netstat', 'ifconfig', 'ip', 'iptables', 'systemctl', 'service', 'crontab',
    'history', 'alias', 'which', 'whereis', 'locate', 'updatedb', 'man', 'info'
}

# Patterns for dangerous commands
DANGEROUS_PATTERNS = [
    r'\brm\s+.*-rf',
    r'\bdd\s+.*of=/dev/',
    r'\bmkfs\.',
    r'\bformat\s',
    r'\bfdisk\s',
    r'\biptables\s+.*-F'
]

# =============================================================================
# DATA CLASSES
# =============================================================================

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

# =============================================================================
# VERSION DETECTION
# =============================================================================

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

# =============================================================================
# CACHING SYSTEM
# =============================================================================

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

# =============================================================================
# CLI ANALYSIS ENGINE
# =============================================================================

class CLIAnalyzer:
    """Multi-layered CLI analysis engine"""
    
    def __init__(self):
        # Framework detection patterns
        self.framework_patterns = {
            'cobra': [
                r'Use\s+"[^"]+"\s+for\s+more\s+information\s+about\s+a\s+command',
                r'Available\s+Commands:',
                r'Global\s+Flags:',
                r'Additional\s+help\s+topics:'
            ],
            'click': [
                r'Usage:\s+[^\s]+\s+\[OPTIONS\]',
                r'Options:',
                r'Commands:',
                r'Show\s+this\s+message\s+and\s+exit'
            ],
            'argparse': [
                r'usage:\s+[^\s]+',
                r'positional\s+arguments:',
                r'optional\s+arguments:',
                r'show\s+this\s+help\s+message\s+and\s+exit'
            ],
            'clap': [
                r'USAGE:',
                r'FLAGS:',
                r'OPTIONS:',
                r'SUBCOMMANDS:'
            ]
        }
    
    def analyze(self, command: str) -> CommandAnalysis:
        """Perform comprehensive analysis of CLI tool"""
        if not shutil.which(command):
            return CommandAnalysis(
                command=command,
                available=False,
                error=f"Command '{command}' not found"
            )
        
        # Get version for cache
        version = VersionDetector.detect_version(command)
        
        # Try layered analysis approach
        analysis_result = None
        
        # Layer 1: Help parsing with framework detection (most reliable)
        try:
            analysis_result = self._analyze_help_with_framework(command)
            if analysis_result and analysis_result.subcommands:
                analysis_result.source_method = "help_framework"
                # Recursively analyze subcommands
                analysis_result = self._analyze_subcommands_recursively(analysis_result)
        except Exception:
            pass
        
        # Layer 2: Completion data (as enhancement)
        if analysis_result:
            try:
                completion_data = self._get_completion_enhancements(command, analysis_result.subcommands)
                if completion_data:
                    analysis_result.capabilities.update(completion_data)
            except Exception:
                pass
        
        # Layer 3: Basic help parsing fallback
        if not analysis_result:
            try:
                analysis_result = self._analyze_basic_help(command)
                if analysis_result:
                    analysis_result.source_method = "help_parsing"
            except Exception:
                pass
        
        # Final fallback
        if not analysis_result:
            analysis_result = CommandAnalysis(
                command=command,
                available=True,
                version=version,
                error="Could not analyze command structure"
            )
        
        # Set common fields
        analysis_result.command = command
        analysis_result.version = version
        analysis_result.available = True
        
        return analysis_result
    
    def _analyze_help_with_framework(self, command: str) -> Optional[CommandAnalysis]:
        """Analyze help text with framework detection"""
        help_text = self._get_help_text(command)
        if not help_text:
            return None
        
        # Detect framework
        framework = self._detect_framework(help_text)
        
        # Extract subcommands
        subcommands = self._extract_subcommands_from_help(help_text)
        
        if not subcommands:
            return None
        
        # Initialize capabilities structure
        capabilities = {}
        examples = []
        
        # Framework-specific optimization
        if framework == 'cobra':
            examples = self._generate_cobra_examples(command, subcommands)
        elif framework == 'click':
            examples = self._generate_click_examples(command, subcommands)
        
        return CommandAnalysis(
            command=command,
            available=True,
            framework=framework,
            subcommands=subcommands,
            capabilities=capabilities,
            examples=examples
        )
    
    def _analyze_subcommands_recursively(self, analysis: CommandAnalysis) -> CommandAnalysis:
        """Recursively analyze subcommands in parallel to build a complete hierarchy"""
        if not analysis.subcommands:
            return analysis

        if analysis.capabilities is None:
            analysis.capabilities = {}

        command = analysis.command
        
        # Function to analyze a single subcommand
        def analyze_subcommand(subcmd: str):
            try:
                full_subcmd = f"{command} {subcmd}"
                subcmd_help = self._get_help_text(full_subcmd)
                
                if subcmd_help:
                    subcmd_analysis = self._parse_subcommand_details(subcmd_help, full_subcmd)
                    
                    # Generate examples
                    if subcmd_analysis.get('syntax'):
                        analysis.examples.append(subcmd_analysis['syntax'])
                    else:
                        analysis.examples.append(f"{command} {subcmd}")
                        
                    return subcmd, subcmd_analysis
                
            except Exception:
                # Return basic info if detailed analysis fails
                return subcmd, {
                    "available": True,
                    "description": f"{subcmd} subcommand"
                }
            return subcmd, None

        # Use ThreadPoolExecutor to run analysis in parallel
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Limit to the first 8 subcommands to prevent excessive resource usage
            future_to_subcmd = {
                executor.submit(analyze_subcommand, subcmd): subcmd 
                for subcmd in analysis.subcommands[:8]
            }
            
            for future in as_completed(future_to_subcmd):
                subcmd, subcmd_analysis = future.result()
                if subcmd_analysis:
                    analysis.capabilities[subcmd] = subcmd_analysis
        
        return analysis
    
    def _parse_subcommand_details(self, help_text: str, full_command: str) -> Dict[str, Any]:
        """Parse detailed subcommand information including nested subcommands"""
        details = {
            "available": True,
            "description": "",
            "flags": [],
            "syntax": "",
            "examples": [],
            "subcommands": {}
        }
        
        lines = help_text.split('\n')
        
        # Extract description (usually first non-empty line)
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('Usage:') and not line.startswith(full_command):
                details["description"] = line
                break
        
        # Extract usage/syntax
        for line in lines:
            if line.strip().startswith('Usage:'):
                usage_line = line.strip()
                if full_command in usage_line:
                    details["syntax"] = usage_line.replace('Usage:', '').strip()
                break
        
        # Extract nested subcommands (important for hierarchy)
        nested_subcommands = self._extract_subcommands_from_help(help_text)
        if nested_subcommands:
            # Recursively analyze one level deeper
            for nested_cmd in nested_subcommands[:5]:  # Limit to prevent timeout
                try:
                    nested_full_cmd = f"{full_command} {nested_cmd}"
                    nested_help = self._get_help_text(nested_full_cmd)
                    if nested_help:
                        nested_details = self._parse_nested_command(nested_help, nested_full_cmd)
                        details["subcommands"][nested_cmd] = nested_details
                except Exception:
                    details["subcommands"][nested_cmd] = {
                        "available": True,
                        "description": f"{nested_cmd} command"
                    }
        
        # Extract flags/options
        in_flags_section = False
        for line in lines:
            line_stripped = line.strip()
            
            if re.search(r'(?i)(flags|options):', line_stripped):
                in_flags_section = True
                continue
            
            if in_flags_section:
                if not line_stripped or (not line.startswith(' ') and ':' in line_stripped):
                    break
                
                # Extract flag
                flag_match = re.match(r'\s+(-[a-zA-Z-]+|--[a-zA-Z-]+)', line)
                if flag_match:
                    details["flags"].append(flag_match.group(1))
        
        # Extract examples
        in_examples_section = False
        for line in lines:
            line_stripped = line.strip()
            
            if re.search(r'(?i)examples?:', line_stripped):
                in_examples_section = True
                continue
            
            if in_examples_section:
                if line_stripped and (line_stripped.startswith(full_command.split()[0]) or 
                                     line_stripped.startswith(full_command)):
                    details["examples"].append(line_stripped)
        
        return details
    
    def _parse_nested_command(self, help_text: str, full_command: str) -> Dict[str, Any]:
        """Parse nested command details (simpler version to avoid deep recursion)"""
        details = {
            "available": True,
            "description": "",
            "syntax": "",
            "flags": [],
            "examples": []
        }
        
        lines = help_text.split('\n')
        
        # Extract description
        for line in lines[:10]:
            line = line.strip()
            if line and not line.startswith('Usage:') and not line.startswith(full_command):
                details["description"] = line
                break
        
        # Extract usage/syntax
        for line in lines:
            if line.strip().startswith('Usage:'):
                usage_line = line.strip()
                if full_command in usage_line:
                    details["syntax"] = usage_line.replace('Usage:', '').strip()
                break
        
        # Extract key flags (required/important ones)
        required_flags = []
        optional_flags = []
        
        in_flags_section = False
        for line in lines:
            line_stripped = line.strip()
            
            if re.search(r'(?i)(flags|options):', line_stripped):
                in_flags_section = True
                continue
            
            if in_flags_section:
                if not line_stripped or (not line.startswith(' ') and ':' in line_stripped):
                    break
                
                # Extract flag with description
                flag_match = re.match(r'\s+(-[a-zA-Z-]+|--[a-zA-Z-]+)\s+(.+)', line)
                if flag_match:
                    flag_name = flag_match.group(1)
                    flag_desc = flag_match.group(2)
                    
                    if 'required' in flag_desc.lower():
                        required_flags.append(flag_name)
                    else:
                        optional_flags.append(flag_name)
        
        details["flags"] = {
            "required": required_flags,
            "optional": optional_flags
        }
        
        # Extract examples from help
        in_examples_section = False
        for line in lines:
            line_stripped = line.strip()
            
            if re.search(r'(?i)examples?:', line_stripped):
                in_examples_section = True
                continue
            
            if in_examples_section:
                if line_stripped and full_command.split()[0] in line_stripped:
                    details["examples"].append(line_stripped)
        
        return details
    
    def _get_completion_enhancements(self, command: str, subcommands: List[str]) -> Dict[str, Any]:
        """Get completion data to enhance analysis"""
        enhancements = {}
        
        # Try to get completion data for specific subcommands
        for subcmd in subcommands[:3]:  # Limit to prevent timeout
            try:
                result = subprocess.run(
                    [command, subcmd, "__complete", ""],
                    capture_output=True,
                    text=True,
                    timeout=3
                )
                
                if result.returncode == 0 and result.stdout:
                    # Parse completion output for additional details
                    completion_lines = result.stdout.strip().split('\n')
                    if completion_lines and not any(var in result.stdout.lower() 
                                                  for var in ['shellcomp', 'activehelp']):
                        enhancements[f"{subcmd}_completion"] = completion_lines[:5]
            except Exception:
                continue
        
        return enhancements
    
    def _analyze_basic_help(self, command: str) -> Optional[CommandAnalysis]:
        """Basic help parsing fallback"""
        help_text = self._get_help_text(command)
        if not help_text:
            return None
        
        subcommands = self._extract_subcommands_from_help(help_text)
        
        return CommandAnalysis(
            command=command,
            available=True,
            subcommands=subcommands,
            examples=[f"{command} --help"]
        )
    
    def _get_help_text(self, command: str) -> str:
        """Get help text using various methods with locale filtering"""
        # For subcommands, try different approaches
        if ' ' in command:
            # This is a subcommand like "can-cli app"
            parts = command.split()
            help_variations = [
                parts + ['--help'],
                parts + ['-h'],
                parts + ['help']
            ]
        else:
            # This is a main command
            help_variations = [
                [command, '--help'],
                [command, '-h'],
                [command, 'help'],
                ['man', command]
            ]
        
        for variation in help_variations:
            try:
                result = subprocess.run(
                    variation,
                    capture_output=True,
                    text=True,
                    timeout=8
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    # Filter out locale warnings
                    output = result.stdout
                    lines = output.split('\n')
                    filtered_lines = [line for line in lines 
                                    if not line.startswith('Unknown locale')]
                    return '\n'.join(filtered_lines)
                elif result.stderr.strip() and not result.stderr.startswith('Unknown locale'):
                    return result.stderr
            except Exception:
                continue
        
        return ""
    
    def _detect_framework(self, help_text: str) -> Optional[str]:
        """Detect CLI framework from help text patterns"""
        best_framework = None
        best_score = 0
        
        for framework, patterns in self.framework_patterns.items():
            score = sum(1 for pattern in patterns 
                       if re.search(pattern, help_text, re.IGNORECASE))
            
            if score > best_score:
                best_score = score
                best_framework = framework
        
        return best_framework if best_score >= 2 else None
    
    def _extract_subcommands_from_help(self, help_text: str) -> List[str]:
        """Extract subcommands from help text using intelligent parsing"""
        subcommands = []
        lines = help_text.split('\n')
        in_commands_section = False
        
        for line in lines:
            original_line = line
            line = line.strip()
            
            # Check for commands section
            if re.search(r'(?i)(?:available\s+)?commands?\s*:', line):
                in_commands_section = True
                continue
            
            if in_commands_section:
                # Stop at flags or empty section
                if not line or 'flags' in line.lower():
                    if 'flags' in line.lower() or not line:
                        in_commands_section = False
                        continue
                
                # Extract command names
                if original_line.startswith(' ') and line:
                    match = re.match(r'\s+([a-zA-Z0-9_-]+)', original_line)
                    if match:
                        cmd = match.group(1)
                        if cmd.lower() not in ['help', 'version']:
                            subcommands.append(cmd)
        
        return subcommands[:10]  # Limit results
    
    def _generate_cobra_examples(self, command: str, subcommands: List[str]) -> List[str]:
        """Generate examples for Cobra-based tools"""
        examples = []
        for subcmd in subcommands[:3]:
            examples.append(f"{command} {subcmd} --help")
        return examples
    
    def _generate_click_examples(self, command: str, subcommands: List[str]) -> List[str]:
        """Generate examples for Click-based tools"""
        examples = []
        for subcmd in subcommands[:3]:
            examples.append(f"{command} {subcmd}")
        return examples

# =============================================================================
# MAIN BASHER CLASS
# =============================================================================

class Basher:
    """Main Basher agent with intelligent CLI analysis and LLM integration"""
    
    def __init__(self, model: str = "basher", show_thinking: bool = False, show_progress: bool = True, show_debug: bool = False):
        self.cache = JSONCache()
        self.analyzer = CLIAnalyzer()
        self.model = model
        self.show_thinking = show_thinking
        self.show_progress = show_progress
        self.show_debug = show_debug
        self.progress = ProgressIndicator(enabled=show_progress)
        
        # Define tools for the LLM
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_command_analysis",
                    "description": "Get intelligent analysis of CLI tool capabilities and syntax",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The CLI command to analyze"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "assess_basic_risk",
                    "description": "Check command safety (LOW/MEDIUM/HIGH/CRITICAL)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The command to assess for risk"
                            }
                        },
                        "required": ["command"]
                    }
                }
            }
        ]
    
    def construct_command(self, user_query: str) -> str:
        """Main interface: construct command from natural language query"""
        try:
            start_time = time.time()
            
            self.progress.start_spinner("Analyzing query...")
            
            # Prepare messages for the chat
            messages = [
                {
                    "role": "user",
                    "content": user_query
                }
            ]
            
            # Call the LLM with tools using ollama package
            self.progress.start_spinner("Thinking...")
            ollama_start_time = time.time()
            response = ollama.chat(
                model=self.model,
                messages=messages,
                tools=self.tools
            )
            ollama_end_time = time.time()
            if self.show_debug:
                print(f"DEBUG: Initial Ollama call took {ollama_end_time - ollama_start_time:.2f}s")
            
            if self.show_thinking and response.message.content:
                self.progress.complete()
                print(f"\n◈ Thinking: {response.message.content}")
            
            # Handle tool calls if present
            if response.message.tool_calls:
                # Add assistant message with tool calls to conversation
                messages.append({
                    "role": "assistant",
                    "content": response.message.content,
                    "tool_calls": [
                        {
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
                        for i, tool_call in enumerate(response.message.tool_calls)
                    ]
                })
                
                # Process each tool call
                for i, tool_call in enumerate(response.message.tool_calls):
                    function_name = tool_call.function.name
                    arguments = tool_call.function.arguments
                    
                    tool_start_time = time.time()
                    if function_name == 'get_command_analysis':
                        command = arguments.get('command', 'unknown')
                        self.progress.start_spinner(f"Analyzing CLI tool: {command}")
                        analysis_result = self.get_command_analysis(command)
                        
                        # Add tool result back to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": f"call_{i}",
                            "content": analysis_result
                        })
                    
                    elif function_name == 'assess_basic_risk':
                        command = arguments.get('command', 'unknown')
                        self.progress.start_spinner(f"Assessing risk: {command}")
                        risk_result = self.assess_basic_risk(command)
                        
                        # Add tool result back to conversation
                        messages.append({
                            "role": "tool",
                            "tool_call_id": f"call_{i}",
                            "content": risk_result
                        })
                    tool_end_time = time.time()
                    if self.show_debug:
                        print(f"DEBUG: Tool call '{function_name}' took {tool_end_time - tool_start_time:.2f}s")

                self.progress.start_spinner("Constructing final command...")
                
                # Get final response after tool calls
                final_ollama_start_time = time.time()
                final_response = ollama.chat(
                    model=self.model,
                    messages=messages
                )
                final_ollama_end_time = time.time()
                if self.show_debug:
                    print(f"DEBUG: Final Ollama call took {final_ollama_end_time - final_ollama_start_time:.2f}s")
                
                result = final_response.message.content
                if not self.show_thinking:
                    result = self._filter_thinking_blocks(result)
                
                self.progress.complete()
                result = self._clean_command_output(result)
                end_time = time.time()
                if self.show_debug:
                    print(f"DEBUG: Total execution time: {end_time - start_time:.2f}s")
                return result
            
            else:
                # Direct response without tool calls
                result = response.message.content
                if not self.show_thinking:
                    result = self._filter_thinking_blocks(result)
                
                self.progress.complete()
                result = self._clean_command_output(result)
                end_time = time.time()
                if self.show_debug:
                    print(f"DEBUG: Total execution time: {end_time - start_time:.2f}s")
                return result
                
        except Exception as e:
            self.progress.complete(f"✗ Error: {str(e)}")
            return f"Error: {str(e)}"
    
    def _filter_thinking_blocks(self, content: str) -> str:
        """Remove thinking blocks from model output when thinking is disabled"""
        if not content:
            return content
        
        import re
        
        # Remove <thinking>...</thinking> blocks
        content = re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)
        
        # Remove <think>...</think> blocks  
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
        
        # Remove any other thinking-related tags
        content = re.sub(r'<thinking_mode>.*?</thinking_mode>', '', content, flags=re.DOTALL)
        
        # Clean up extra whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return content
    
    def _clean_command_output(self, content: str) -> str:
        """Clean up command output by removing backticks and extra formatting"""
        if not content:
            return content
        
        import re
        
        # Remove backticks around commands
        content = re.sub(r'```\w*\n?', '', content)
        content = re.sub(r'```', '', content)
        content = re.sub(r'`([^`]+)`', r'\1', content)
        
        # Clean up extra whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = content.strip()
        
        return content
    
    def get_command_analysis(self, command: str) -> str:
        """Get intelligent analysis with smart subcommand handling"""
        try:
            start_time = time.time()
            # Extract base command for analysis
            base_command = command.split()[0]
            
            # Skip analysis for system commands
            if base_command in SYSTEM_COMMANDS:
                return json.dumps({
                    "skip": "system_command",
                    "reason": f"{base_command} is a common system command"
                })
            
            # Check cache first for base command
            cache_check_start_time = time.time()
            cached_analysis = self.cache.get(base_command)
            cache_check_end_time = time.time()
            if self.show_debug:
                print(f"DEBUG: Cache check for '{base_command}' took {cache_check_end_time - cache_check_start_time:.2f}s")

            if cached_analysis:
                if self.show_debug:
                    print(f"DEBUG: Cache hit for '{base_command}'")
                result = asdict(cached_analysis)
                
                # If asking about a specific subcommand, extract relevant info
                if len(command.split()) > 1:
                    subcommand_path = command.split()[1:]
                    result = self._extract_subcommand_info(result, subcommand_path)
                
                end_time = time.time()
                if self.show_debug:
                    print(f"DEBUG: get_command_analysis for '{command}' (cached) took {end_time - start_time:.2f}s")
                return json.dumps(result, indent=2)
            
            if self.show_debug:
                print(f"DEBUG: Cache miss for '{base_command}', performing fresh analysis")
            # Perform fresh analysis on base command
            analysis_start_time = time.time()
            analysis = self.analyzer.analyze(base_command)
            analysis_end_time = time.time()
            if self.show_debug:
                print(f"DEBUG: Fresh analysis of '{base_command}' took {analysis_end_time - analysis_start_time:.2f}s")
            
            # Cache the result
            if analysis.available:
                self.cache.set(base_command, analysis)
            
            result = asdict(analysis)
            
            # If asking about a specific subcommand, extract relevant info
            if len(command.split()) > 1:
                subcommand_path = command.split()[1:]
                result = self._extract_subcommand_info(result, subcommand_path)
            
            end_time = time.time()
            if self.show_debug:
                print(f"DEBUG: get_command_analysis for '{command}' (uncached) took {end_time - start_time:.2f}s")
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Analysis failed: {str(e)}",
                "command": command,
                "available": False
            })
    
    def _extract_subcommand_info(self, analysis_data: Dict, subcommand_path: List[str]) -> Dict:
        """Extract specific subcommand information from full analysis"""
        current = analysis_data
        
        # Navigate through the subcommand path
        for subcmd in subcommand_path:
            if 'capabilities' in current and subcmd in current['capabilities']:
                capability = current['capabilities'][subcmd]
                
                # Create focused response for this subcommand
                return {
                    "command": f"{current['command']} {subcmd}",
                    "available": capability.get('available', True),
                    "description": capability.get('description', ''),
                    "syntax": capability.get('syntax', ''),
                    "flags": capability.get('flags', []),
                    "examples": capability.get('examples', []),
                    "subcommands": capability.get('subcommands', {}),
                    "parent_command": current['command']
                }
            else:
                # Subcommand not found, return the full analysis
                break
        
        return analysis_data
    
    def assess_basic_risk(self, command: str) -> str:
        """Assess command risk level with comprehensive checks"""
        try:
            risk_level = "LOW"
            warnings = []
            
            # Check for dangerous patterns
            for pattern in DANGEROUS_PATTERNS:
                if re.search(pattern, command, re.IGNORECASE):
                    risk_level = "CRITICAL"
                    warnings.append("Potentially destructive command")
                    break
            
            # Check for privilege escalation
            if re.search(r'\bsudo\b|\bsu\b', command):
                if risk_level == "LOW":
                    risk_level = "MEDIUM"
                warnings.append("Requires elevated privileges")
            
            # Check for network operations
            if re.search(r'\bcurl\b|\bwget\b|\bssh\b', command):
                if risk_level == "LOW":
                    risk_level = "MEDIUM"
                warnings.append("Network operation")
            
            # Check for production deployments
            if re.search(r'prod|production', command, re.IGNORECASE):
                if risk_level == "LOW":
                    risk_level = "HIGH"
                warnings.append("Production environment operation")
            
            return json.dumps({
                "risk_level": risk_level,
                "warnings": warnings,
                "command": command
            })
            
        except Exception as e:
            return json.dumps({
                "error": f"Risk assessment failed: {str(e)}",
                "risk_level": "UNKNOWN"
            })
    
    def verify_command_exists(self, command: str) -> str:
        """Verify if command exists and suggest alternatives"""
        try:
            base_command = command.split()[0]
            
            if shutil.which(base_command):
                return json.dumps({
                    "exists": True,
                    "command": base_command,
                    "path": shutil.which(base_command)
                })
            
            # Suggest alternatives
            suggestions = []
            common_alternatives = {
                'kubectl': ['k9s', 'kubectx', 'helm'],
                'docker': ['podman', 'buildah'],
                'git': ['gh', 'hub'],
                'npm': ['yarn', 'pnpm'],
                'pip': ['pipx', 'poetry'],
            }
            
            if base_command in common_alternatives:
                suggestions = common_alternatives[base_command]
            
            return json.dumps({
                "exists": False,
                "command": base_command,
                "suggestions": suggestions,
                "install_hint": f"Try: brew install {base_command} or apt-get install {base_command}"
            })
            
        except Exception as e:
            return json.dumps({
                "error": f"Verification failed: {str(e)}",
                "exists": False
            })

# =============================================================================
# TOOL FUNCTIONS FOR OLLAMA
# =============================================================================

# Global instance for tool calling
basher_instance = Basher()

def get_command_analysis(command: str) -> str:
    """Get intelligent analysis of CLI tool capabilities and syntax"""
    return basher_instance.get_command_analysis(command)

def assess_basic_risk(command: str) -> str:
    """Check command safety (LOW/MEDIUM/HIGH/CRITICAL)"""
    return basher_instance.assess_basic_risk(command)

def verify_command_exists(command: str) -> str:
    """Check if command exists, suggest alternatives or installation"""
    return basher_instance.verify_command_exists(command)

# =============================================================================
# COMMAND LINE INTERFACE
# =============================================================================

def main():
    """Main command line interface"""
    import sys
    
    if len(sys.argv) < 2:
        print("Basher - Intelligent CLI Command Assistant")
        print("\nUsage:")
        print("  python basher.py 'natural language query' [--thinking] [--no-progress] [--debug]")
        print("  python basher.py --analyze <command>")
        print("  python basher.py --risk <command>")
        print("\nOptions:")
        print("  --thinking      Show AI thinking process")
        print("  --no-progress   Disable progress indicators")
        print("  --debug         Show debug logging")
        print("\nExamples:")
        print("  python basher.py 'How to deploy to production with can-cli'")
        print("  python basher.py 'Check pod logs with can-cli' --thinking")
        print("  python basher.py --analyze can-cli")
        print("  python basher.py --risk 'rm -rf /tmp'")
        sys.exit(1)
    
    # Parse flags
    show_thinking = '--thinking' in sys.argv
    show_progress = '--no-progress' not in sys.argv
    show_debug = '--debug' in sys.argv
    
    # Remove flags from arguments
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    
    # Initialize basher with options
    basher = Basher(show_thinking=show_thinking, show_progress=show_progress, show_debug=show_debug)
    
    # Handle different modes
    if len(args) > 0 and args[0] == "--analyze":
        if len(args) < 2:
            print("Error: --analyze requires a command")
            sys.exit(1)
        
        command = args[1]
        print("=== Command Analysis ===")
        result = basher.get_command_analysis(command)
        print(result)
    
    elif len(args) > 0 and args[0] == "--risk":
        if len(args) < 2:
            print("Error: --risk requires a command")
            sys.exit(1)
        
        command = args[1]
        print("=== Risk Assessment ===")
        result = basher.assess_basic_risk(command)
        print(result)
    
    else:
        # Main mode: natural language to command construction
        if not args:
            print("Error: Please provide a query")
            sys.exit(1)
        
        user_query = " ".join(args)
        
        result = basher.construct_command(user_query)
        
        print(result)

if __name__ == "__main__":
    main()
