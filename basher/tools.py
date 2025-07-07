#!/usr/bin/env python3
"""
Tool functions for Ollama integration.
"""

# Global instance will be set by the main module
basher_instance = None


def get_command_analysis(command: str) -> str:
    """Get intelligent analysis of CLI tool capabilities and syntax"""
    if basher_instance is None:
        raise RuntimeError("Basher instance not initialized")
    return basher_instance.get_command_analysis(command)


def assess_basic_risk(command: str) -> str:
    """Check command safety (LOW/MEDIUM/HIGH/CRITICAL)"""
    if basher_instance is None:
        raise RuntimeError("Basher instance not initialized")
    return basher_instance.assess_basic_risk(command)


def verify_command_exists(command: str) -> str:
    """Check if command exists, suggest alternatives or installation"""
    if basher_instance is None:
        raise RuntimeError("Basher instance not initialized")
    return basher_instance.verify_command_exists(command)


def set_basher_instance(instance):
    """Set the global basher instance for tool functions"""
    global basher_instance
    basher_instance = instance