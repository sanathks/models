#!/usr/bin/env python3
"""
CLI analysis engine for understanding command structure and capabilities.
"""

import subprocess
import shutil
import re
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import CommandAnalysis
from .version import VersionDetector


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