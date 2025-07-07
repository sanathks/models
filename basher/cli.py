#!/usr/bin/env python3
"""
Command line interface for Basher.
"""

import sys
from .basher import Basher


def main():
    """Main command line interface"""
    if len(sys.argv) < 2:
        print("Basher - Intelligent CLI Command Assistant")
        print("\nUsage:")
        print("  python -m basher 'natural language query' [--thinking] [--no-progress] [--debug]")
        print("  python -m basher --analyze <command>")
        print("  python -m basher --risk <command>")
        print("\nOptions:")
        print("  --thinking      Show AI thinking process")
        print("  --no-progress   Disable progress indicators")
        print("  --debug         Show debug logging")
        print("\nExamples:")
        print("  python -m basher --risk 'rm -rf /tmp'")
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