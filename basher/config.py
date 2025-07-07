#!/usr/bin/env python3
"""
Configuration constants and patterns for Basher.
"""

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