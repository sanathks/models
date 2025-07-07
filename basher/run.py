#!/usr/bin/env python3
"""
Simple CLI for Command Helper Agent
Usage: python3 run.py "your query"
"""

import sys
import json
from agent import SimpleCommandHelper
try:
    import ollama
except ImportError:
    print("Ollama library not found. Install with: pip install ollama")
    exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 run.py \"your query\"")
        print("\nExamples:")
        print("  python3 run.py \"run nvim headless mode\"")
        print("  python3 run.py \"python script in background\"")
        print("  python3 run.py \"find large files\"")
        return
    
    query = " ".join(sys.argv[1:])
    helper = SimpleCommandHelper()
    
    # Get system context
    import platform
    import os
    context = f"""System Context:
OS: {platform.system()} {platform.release()}
Current Directory: {os.getcwd()}
User: {os.environ.get('USER', 'unknown')}
Shell: {os.environ.get('SHELL', 'unknown')}

User Query: {query}"""
    
    # Define tools for the model
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_command_help",
                "description": "Get help documentation for a command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to get help for"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function", 
            "function": {
                "name": "assess_basic_risk",
                "description": "Assess basic risk level of a command",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to assess"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "verify_command_exists",
                "description": "Verify if command exists and suggest alternatives or installation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to verify"}
                    },
                    "required": ["command"]
                }
            }
        }
    ]
    
    try:
        # Send query to model with context
        response = ollama.chat(
            model="command-helper",
            messages=[{"role": "user", "content": context}],
            tools=tools
        )
        
        # Handle tool calls
        if response.get('message', {}).get('tool_calls'):
            for tool_call in response['message']['tool_calls']:
                function_name = tool_call['function']['name']
                function_args = tool_call['function']['arguments']
                if isinstance(function_args, str):
                    function_args = json.loads(function_args)
                
                # Debug log
                print(f"[DEBUG] Calling: {function_name}({function_args})")
                
                # Execute the tool
                if function_name == "get_command_help":
                    result = helper.get_command_help(function_args['command'])
                elif function_name == "assess_basic_risk":
                    result = helper.assess_basic_risk(function_args['command'])
                elif function_name == "verify_command_exists":
                    result = helper.verify_command_exists(function_args['command'])
                else:
                    result = json.dumps({"error": f"Unknown function: {function_name}"})
                
                # Send result back to model
                response = ollama.chat(
                    model="command-helper",
                    messages=[
                        {"role": "user", "content": context},
                        response['message'],
                        {
                            "role": "tool",
                            "content": result,
                            "tool_call_id": tool_call.get('id', '')
                        }
                    ],
                    tools=tools
                )
        
        # Clean output - remove thinking tags and backticks
        assistant_response = response['message']['content']
        import re
        clean_response = re.sub(r'<think>.*?</think>', '', assistant_response, flags=re.DOTALL)
        clean_response = clean_response.strip()
        
        # Remove backticks
        clean_response = clean_response.replace('`', '')
        
        print(clean_response)
        
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()