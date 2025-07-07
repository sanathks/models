#!/usr/bin/env python3
"""
Basher - Intelligent CLI Command Assistant

A comprehensive CLI command assistant that uses intelligent analysis techniques
to understand CLI tools and construct accurate commands from natural language queries.
"""

import json
import shutil
import re
import time
from typing import Dict, List
from dataclasses import asdict

try:
    import ollama
except ImportError:
    print("Error: ollama package not found. Install with: pip install ollama")
    exit(1)

from .progress import ProgressIndicator
from .config import SYSTEM_COMMANDS, DANGEROUS_PATTERNS
from .models import CommandAnalysis
from .cache import JSONCache
from .analyzer import CLIAnalyzer
from . import tools


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
        
        # Set global instance for tool functions
        tools.set_basher_instance(self)
        
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

                self.progress.start_spinner("")
                
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