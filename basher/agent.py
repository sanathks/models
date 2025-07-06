#!/usr/bin/env python3
"""
Simple Command Helper Agent
Helps users construct correct commands by reading help documentation
"""

import json
import subprocess
import shutil
import re
import platform
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class CommandSuggestion:
    """Result of command suggestion"""
    query: str
    suggested_command: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    warning: Optional[str]
    explanation: str


class SimpleCommandHelper:
    """Simple agent that helps construct commands using help documentation"""
    
    def __init__(self):
        self.dangerous_patterns = [
            r'\brm\s+.*-rf',
            r'\bdd\s+.*of=/dev/',
            r'\bmkfs\.',
            r'\bformat\s',
            r'\bfdisk\s',
            r'\biptables\s+.*-F'
        ]
    
    def get_command_help(self, command: str) -> str:
        """Get help documentation for a command"""
        try:
            base_command = command.split()[0]
            
            # Check if command exists
            if not shutil.which(base_command):
                return json.dumps({
                    "error": f"Command '{base_command}' not found",
                    "suggestion": "Check if the command is installed"
                })
            
            # Try different help options
            help_variations = [
                [base_command, '--help'],
                [base_command, '-h'],
                [base_command, 'help'],
                ['man', base_command]
            ]
            
            help_output = ""
            for variation in help_variations:
                try:
                    result = subprocess.run(
                        variation,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        help_output = result.stdout
                        break
                    elif result.stderr.strip():
                        help_output = result.stderr
                        break
                        
                except subprocess.TimeoutExpired:
                    continue
                except:
                    continue
            
            if not help_output:
                help_output = f"No help available for {base_command}"
            
            return json.dumps({
                "command": base_command,
                "help_output": help_output[:2000],  # Limit size
                "truncated": len(help_output) > 2000
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to get help: {str(e)}"
            })
    
    def assess_basic_risk(self, command: str) -> str:
        """Simple risk assessment for commands"""
        try:
            command_lower = command.lower()
            
            # Check for dangerous patterns
            for pattern in self.dangerous_patterns:
                if re.search(pattern, command, re.IGNORECASE):
                    return json.dumps({
                        "risk_level": "CRITICAL",
                        "warning": "This command can cause data loss or system damage",
                        "recommendation": "Use with extreme caution and verify targets"
                    })
            
            # Check for sudo usage
            if command_lower.startswith('sudo'):
                return json.dumps({
                    "risk_level": "MEDIUM",
                    "warning": "Command requires administrative privileges",
                    "recommendation": "Ensure you understand what this command does"
                })
            
            # Check for file modifications
            modification_commands = ['rm', 'mv', 'cp', 'chmod', 'chown']
            if any(cmd in command_lower.split() for cmd in modification_commands):
                return json.dumps({
                    "risk_level": "LOW",
                    "warning": "Command modifies files or permissions",
                    "recommendation": "Verify file paths before execution"
                })
            
            # Default to safe
            return json.dumps({
                "risk_level": "LOW",
                "warning": None,
                "recommendation": "Command appears safe to execute"
            })
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to assess risk: {str(e)}"
            })
    
    def suggest_command(self, query: str, help_output: str) -> str:
        """Suggest a command based on user query and help documentation"""
        try:
            # This is a simplified version - in practice, the model will do this analysis
            # But we can provide some basic suggestions for common patterns
            
            query_lower = query.lower()
            
            # Extract command name from query
            command_name = self._extract_command_name(query_lower)
            
            if not command_name:
                return json.dumps({
                    "error": "Could not identify command from query",
                    "suggestion": "Please specify the command you want to use"
                })
            
            # Basic pattern matching for common use cases
            suggested_command = self._match_common_patterns(query_lower, command_name, help_output)
            
            return json.dumps({
                "query": query,
                "suggested_command": suggested_command,
                "explanation": f"Based on your query '{query}' and help documentation"
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to suggest command: {str(e)}"
            })
    
    def _extract_command_name(self, query: str) -> Optional[str]:
        """Extract command name from user query"""
        # Look for common command names in the query
        common_commands = [
            'nvim', 'vim', 'nano', 'emacs',
            'python', 'python3', 'node', 'npm',
            'git', 'docker', 'kubectl',
            'ls', 'find', 'grep', 'sed', 'awk',
            'curl', 'wget', 'ssh', 'scp',
            'tar', 'zip', 'unzip'
        ]
        
        words = query.split()
        for word in words:
            if word in common_commands:
                return word
        
        return None
    
    def _match_common_patterns(self, query: str, command: str, help_output: str) -> str:
        """Match common usage patterns"""
        
        # nvim patterns
        if command == 'nvim':
            if 'headless' in query:
                return 'nvim --headless'
            elif 'diff' in query:
                return 'nvim -d file1 file2'
            elif 'readonly' in query or 'read only' in query:
                return 'nvim -R filename'
            else:
                return 'nvim filename'
        
        # python patterns
        elif command in ['python', 'python3']:
            if 'background' in query:
                return f'{command} script.py &'
            elif 'module' in query:
                return f'{command} -m module_name'
            elif 'interactive' in query:
                return f'{command} -i'
            else:
                return f'{command} script.py'
        
        # git patterns
        elif command == 'git':
            if 'clone' in query:
                return 'git clone <repository_url>'
            elif 'status' in query:
                return 'git status'
            elif 'commit' in query:
                return 'git commit -m "message"'
            elif 'push' in query:
                return 'git push origin main'
            else:
                return 'git status'
        
        # docker patterns
        elif command == 'docker':
            if 'run' in query:
                if 'interactive' in query:
                    return 'docker run -it image_name'
                elif 'detach' in query or 'background' in query:
                    return 'docker run -d image_name'
                else:
                    return 'docker run image_name'
            elif 'ps' in query or 'list' in query:
                return 'docker ps'
            elif 'images' in query:
                return 'docker images'
            else:
                return 'docker ps'
        
        # Default fallback
        return f'{command} --help'
    
    def verify_command_exists(self, command: str) -> str:
        """Verify if command exists and suggest alternatives or installation"""
        try:
            base_command = command.split()[0]
            
            # Check if command exists
            if shutil.which(base_command):
                return json.dumps({
                    "command": base_command,
                    "exists": True,
                    "status": "Command is available",
                    "path": shutil.which(base_command)
                })
            
            # Command doesn't exist - find alternatives and installation options
            alternatives = self._find_alternatives(base_command)
            install_options = self._get_install_options(base_command)
            
            return json.dumps({
                "command": base_command,
                "exists": False,
                "status": "Command not found",
                "alternatives": alternatives,
                "install_options": install_options,
                "recommendation": self._get_recommendation(base_command, alternatives, install_options)
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to verify command: {str(e)}"
            })
    
    def _find_alternatives(self, command: str) -> List[Dict]:
        """Find alternative commands that are available"""
        alternatives = []
        
        # Common alternatives mapping
        alt_map = {
            'vim': ['nvim', 'nano', 'emacs'],
            'nvim': ['vim', 'nano', 'emacs'],
            'python': ['python3', 'python2'],
            'python3': ['python'],
            'node': ['nodejs'],
            'nodejs': ['node'],
            'docker': ['podman'],
            'podman': ['docker'],
            'cat': ['bat', 'less', 'more'],
            'ls': ['exa', 'lsd', 'dir'],
            'find': ['fd', 'locate'],
            'grep': ['rg', 'ag', 'ack'],
            'curl': ['wget'],
            'wget': ['curl'],
            'tar': ['7z', 'zip'],
            'zip': ['tar', '7z']
        }
        
        if command in alt_map:
            for alt in alt_map[command]:
                if shutil.which(alt):
                    alternatives.append({
                        "command": alt,
                        "available": True,
                        "path": shutil.which(alt)
                    })
                else:
                    alternatives.append({
                        "command": alt,
                        "available": False
                    })
        
        return alternatives
    
    def _get_install_options(self, command: str) -> List[Dict]:
        """Get installation options based on available package managers"""
        options = []
        
        # Detect OS and available package managers
        os_type = platform.system().lower()
        
        # Check for package managers
        managers = {
            'apt': {'cmd': 'apt', 'install': f'sudo apt update && sudo apt install {command}'},
            'yum': {'cmd': 'yum', 'install': f'sudo yum install {command}'},
            'dnf': {'cmd': 'dnf', 'install': f'sudo dnf install {command}'},
            'pacman': {'cmd': 'pacman', 'install': f'sudo pacman -S {command}'},
            'brew': {'cmd': 'brew', 'install': f'brew install {command}'},
            'snap': {'cmd': 'snap', 'install': f'sudo snap install {command}'},
            'flatpak': {'cmd': 'flatpak', 'install': f'flatpak install {command}'},
            'pip': {'cmd': 'pip', 'install': f'pip install {command}'},
            'pip3': {'cmd': 'pip3', 'install': f'pip3 install {command}'},
            'npm': {'cmd': 'npm', 'install': f'npm install -g {command}'}
        }
        
        # Check which package managers are available
        for name, info in managers.items():
            if shutil.which(info['cmd']):
                options.append({
                    "package_manager": name,
                    "available": True,
                    "command": info['install']
                })
        
        # Add special cases for specific commands
        special_cases = self._get_special_install_cases(command)
        if special_cases:
            options.extend(special_cases)
        
        return options
    
    def _get_special_install_cases(self, command: str) -> List[Dict]:
        """Handle special installation cases for specific commands"""
        special = []
        
        if command == 'nvim':
            if shutil.which('apt'):
                special.append({
                    "package_manager": "apt",
                    "available": True,
                    "command": "sudo apt update && sudo apt install neovim"
                })
            if shutil.which('snap'):
                special.append({
                    "package_manager": "snap",
                    "available": True,
                    "command": "sudo snap install nvim --classic"
                })
        
        elif command == 'docker':
            if shutil.which('apt'):
                special.append({
                    "package_manager": "apt",
                    "available": True,
                    "command": "curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh"
                })
        
        elif command in ['node', 'nodejs']:
            if shutil.which('apt'):
                special.append({
                    "package_manager": "apt",
                    "available": True,
                    "command": "curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt install -y nodejs"
                })
        
        return special
    
    def _get_recommendation(self, command: str, alternatives: List[Dict], install_options: List[Dict]) -> str:
        """Generate recommendation based on alternatives and install options"""
        available_alts = [alt for alt in alternatives if alt.get('available', False)]
        
        if available_alts:
            return f"Use alternative: {available_alts[0]['command']}"
        elif install_options:
            primary_option = install_options[0]
            return f"Install with {primary_option['package_manager']}: {primary_option['command']}"
        else:
            return f"Command '{command}' not found and no installation options detected"


# Tool functions for the model
def get_command_help(command: str) -> str:
    """Get help for a command - Tool function for model"""
    helper = SimpleCommandHelper()
    return helper.get_command_help(command)


def assess_basic_risk(command: str) -> str:
    """Assess basic risk of a command - Tool function for model"""
    helper = SimpleCommandHelper()
    return helper.assess_basic_risk(command)


def suggest_command(query: str, help_output: str) -> str:
    """Suggest command based on query and help - Tool function for model"""
    helper = SimpleCommandHelper()
    return helper.suggest_command(query, help_output)


def verify_command_exists(command: str) -> str:
    """Verify if command exists and suggest alternatives - Tool function for model"""
    helper = SimpleCommandHelper()
    return helper.verify_command_exists(command)


if __name__ == "__main__":
    # Test the command helper
    print("Testing Simple Command Helper...")
    
    helper = SimpleCommandHelper()
    
    # Test help retrieval
    print("\n1. Testing help retrieval:")
    help_result = helper.get_command_help("ls")
    print(help_result[:200] + "...")
    
    # Test risk assessment
    print("\n2. Testing risk assessment:")
    risk_result = helper.assess_basic_risk("rm -rf /tmp/test")
    print(risk_result)
    
    # Test command suggestion
    print("\n3. Testing command suggestion:")
    suggestion_result = helper.suggest_command("run nvim in headless mode", "nvim help output...")
    print(suggestion_result)