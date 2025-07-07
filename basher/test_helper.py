#!/usr/bin/env python3
"""
Test wrapper for Command Helper agent
"""

import json
from agent import SimpleCommandHelper
try:
    import ollama
    print("Ollama library available")
except ImportError:
    print("Ollama library not found. Install with: pip install ollama")
    exit(1)


class CommandHelperAgent:
    """Simple wrapper to test command helper with ollama"""
    
    def __init__(self, model_name: str = "command-helper"):
        self.model_name = model_name
        self.helper = SimpleCommandHelper()
        print(f"Command Helper Agent initialized with model: {model_name}")
    
    def chat(self, user_query: str) -> str:
        """Chat with the command helper model"""
        print(f"\nUser: {user_query}")
        
        # Define available tools
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
                    "name": "suggest_command", 
                    "description": "Suggest command based on query and help",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "User query"},
                            "help_output": {"type": "string", "description": "Help documentation"}
                        },
                        "required": ["query", "help_output"]
                    }
                }
            }
        ]
        
        try:
            # Send message to model
            print("Analyzing query...")
            response = ollama.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": user_query}],
                tools=tools,
                stream=False
            )
            
            # Handle tool calls
            if response.get('message', {}).get('tool_calls'):
                print("Model is using tools...")
                
                for tool_call in response['message']['tool_calls']:
                    function_name = tool_call['function']['name']
                    function_args = json.loads(tool_call['function']['arguments'])
                    
                    print(f"   Calling: {function_name}({function_args})")
                    
                    # Execute the tool
                    if function_name == "get_command_help":
                        result = self.helper.get_command_help(function_args['command'])
                    elif function_name == "assess_basic_risk":
                        result = self.helper.assess_basic_risk(function_args['command'])
                    elif function_name == "suggest_command":
                        result = self.helper.suggest_command(
                            function_args['query'], 
                            function_args['help_output']
                        )
                    else:
                        result = json.dumps({"error": f"Unknown function: {function_name}"})
                    
                    # Send result back to model
                    print("Getting final response...")
                    response = ollama.chat(
                        model=self.model_name,
                        messages=[
                            {"role": "user", "content": user_query},
                            response['message'],
                            {
                                "role": "tool",
                                "content": result,
                                "tool_call_id": tool_call.get('id', '')
                            }
                        ],
                        tools=tools,
                        stream=False
                    )
            
            assistant_response = response['message']['content']
            
            # Filter out thinking tags
            import re
            filtered_response = re.sub(r'<think>.*?</think>', '', assistant_response, flags=re.DOTALL)
            filtered_response = filtered_response.strip()
            
            print(f"Assistant: {filtered_response}")
            return filtered_response
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"Error: {error_msg}")
            return error_msg


def test_command_helper():
    """Test the command helper with various queries"""
    print("=" * 60)
    print("TESTING COMMAND HELPER AGENT")
    print("=" * 60)
    
    agent = CommandHelperAgent()
    
    test_queries = [
        "run nvim in headless mode",
        "python script in background", 
        "find large files",
        "git commit with message",
        "docker run interactive container",
        "delete temporary files"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Test {i}/{len(test_queries)} ---")
        agent.chat(query)
        print("Test completed")
    
    print(f"\nAll {len(test_queries)} tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    test_command_helper()