# Basher - Intelligent CLI Command Assistant

## Overview

Basher is an intelligent CLI command assistant that helps users discover and construct correct commands for various CLI tools. Built with Ollama and a Python agent, it uses advanced analysis techniques to understand CLI tool capabilities and provide accurate command suggestions with safety warnings.

### Key Features
- **Intelligent CLI Analysis**: Multi-layered approach using completion data, framework detection, and help parsing
- **Version-Based Caching**: Smart cache invalidation based on tool versions rather than time
- **Safety First**: Risk assessment and warnings for potentially dangerous commands
- **Context-Aware**: Understanding of different CLI tool types and their capabilities
- **Learning System**: Builds knowledge over time through intelligent caching

## Architecture Overview

```
User Query → Ollama Model → Python Agent → CLI Analysis → Cache → Response
                ↓                ↓           ↓         ↓
           System Prompt    Tool Calling   Layered   JSON File
                                          Analysis   (~/.basher/)
```

### Components
- **Ollama Model**: qwen3:4b with custom Modelfile for CLI command understanding
- **Python Agent**: Intelligent analysis engine with tool calling capabilities
- **JSON Cache**: Version-based persistent storage for analysis results
- **Analysis Layers**: Completion data, framework detection, help parsing

## Model Configuration

### Modelfile Settings
```dockerfile
FROM qwen3:4b
PARAMETER temperature 0.2    # Low temperature for precise command generation
PARAMETER top_p 0.8         # Focused token selection
PARAMETER num_ctx 4096      # Sufficient context for complex CLI analysis
```

### System Prompt Design
The system prompt is designed to:
- Detect CLI tool requests in natural language
- Make intelligent tool calls for analysis
- Construct accurate commands from analysis data
- Provide safety warnings for risky operations
- Filter out common system commands

## Agent Architecture

### Core Classes

#### `JSONCache`
- **Purpose**: Version-based caching of CLI analysis results
- **Location**: `~/.basher/command_cache.json`
- **Features**: Atomic writes, version checking, corruption recovery
- **Schema**:
```json
{
  "command_name": {
    "version": "1.2.3",
    "framework": "cobra|click|argparse",
    "capabilities": {...},
    "examples": [...],
    "cached_at": "2025-07-07T15:30:00",
    "source_method": "completion|framework|help"
  }
}
```

#### `VersionDetector`
- **Purpose**: Detect CLI tool versions for cache invalidation
- **Methods**: `--version`, `-v`, `version`, help parsing, file timestamps
- **Fallback**: Uses cached data if version detection fails

#### `CLIAnalyzer`
- **Purpose**: Multi-layered analysis of CLI tools
- **Layers**: Completion data → Framework detection → Help parsing
- **Output**: Structured analysis data for LLM consumption

### Analysis Layers

#### Layer 1: Completion Data (Primary)
- **Methods**: 
  - `command completion zsh`
  - `command __complete`
  - Existing completion files
- **Success Rate**: 66.7%
- **Best For**: Modern CLI tools (Cobra, Click-based)
- **Output**: Structured subcommand hierarchy, parameter information

#### Layer 2: Framework Detection (Secondary)
- **Patterns**: 
  - Cobra: "Available Commands:", "Use ... for more information"
  - Click: "Usage:", "Options:", "Commands:"
  - argparse: "usage:", "positional arguments:"
- **Success Rate**: 55.6%
- **Best For**: Optimizing analysis approach per framework
- **Output**: Framework type, confidence level

#### Layer 3: Enhanced Help Parsing (Fallback)
- **Methods**: Advanced regex patterns, section detection
- **Success Rate**: 66.7%
- **Best For**: Legacy tools, fallback when completion unavailable
- **Output**: Extracted subcommands, basic structure

### Command Flow

```
1. User Query: "How to deploy with can-cli"
2. LLM Detection: Identifies CLI tool request
3. Tool Call: get_command_analysis("can-cli")
4. Cache Check: Version-based lookup
5. Analysis: If cache miss, perform layered analysis
6. Response: Construct accurate command with safety check
```

## Intelligent Analysis System

### System Command Filtering
**Skip analysis for common commands:**
```python
SYSTEM_COMMANDS = {
    'ls', 'cd', 'cp', 'mv', 'rm', 'cat', 'grep', 'find', 
    'ps', 'top', 'df', 'du', 'chmod', 'chown', 'mkdir',
    'touch', 'head', 'tail', 'less', 'more', 'sort', 'uniq'
}
```

### Cache Strategy
- **Key**: Command name + version
- **Invalidation**: Version change detection
- **Persistence**: JSON file with atomic writes
- **Recovery**: Graceful handling of corrupted cache
- **Location**: `~/.basher/command_cache.json`

### Analysis Priority
1. **Check cache** with version validation
2. **Completion data** analysis (if modern tool)
3. **Framework detection** for optimization
4. **Help parsing** as fallback
5. **Cache results** for future use

## Safety and Risk Assessment

### Risk Classification
- **LOW**: Read-only operations, info commands
- **MEDIUM**: File operations, network requests
- **HIGH**: System modifications, privileged operations
- **CRITICAL**: Data destruction, security risks

### Dangerous Patterns
```python
DANGEROUS_PATTERNS = [
    r'\brm\s+.*-rf',           # rm -rf commands
    r'\bdd\s+.*of=/dev/',      # dd to devices
    r'\bmkfs\.',               # filesystem creation
    r'\bformat\s',             # format commands
    r'\bfdisk\s',              # disk partitioning
    r'\biptables\s+.*-F'       # firewall flush
]
```

### Warning Generation
- **Automatic detection** of risky patterns
- **Context-aware warnings** based on command analysis
- **User protection** without blocking functionality

## Usage Examples

### Successful Command Generation
```
User: "How to deploy to production with can-cli"
Response: `can-cli app deploy -n production`
```

### With Safety Warning
```
User: "Deploy to production with can-cli"
Response: ⚠️ Warning: This will deploy to production environment
`can-cli app deploy -n production`
```

### Tool Not Available
```
User: "Check pod logs with can-cli"
Response: can-cli does not support log checking. Use `kubectl logs <pod-name>` instead.
```

### Cache Hit Scenario
```
1. First request: Analyzes can-cli, caches results
2. Subsequent requests: Uses cached data (if version unchanged)
3. After update: Detects version change, re-analyzes
```

## Development Guidelines

### Code Structure
- **Separation of concerns**: Cache, analysis, and risk assessment
- **Error handling**: Graceful degradation when tools unavailable
- **Testing**: Unit tests for each analysis layer
- **Logging**: Debug information for troubleshooting

### Best Practices
- **Atomic operations** for cache writes
- **Version validation** before using cached data
- **Fallback chains** for robust analysis
- **Resource limits** to prevent analysis timeout

### Performance Considerations
- **Cache first**: Always check cache before analysis
- **Parallel analysis**: Non-blocking completion data extraction
- **Timeout limits**: Prevent hanging on unresponsive tools
- **Memory management**: Efficient JSON handling

## Technical Implementation

### JSON Cache Format
```json
{
  "can-cli": {
    "version": "1.2.3",
    "framework": "cobra",
    "capabilities": {
      "app": {
        "deploy": {
          "syntax": "can-cli app deploy -n <env> [-m <msg>] [-d <dir>]",
          "required": ["-n"],
          "optional": ["-m", "-d"],
          "examples": ["can-cli app deploy -n dev"]
        }
      }
    },
    "subcommands": ["app", "aws", "k8s", "terraform"],
    "examples": ["can-cli app deploy -n dev", "can-cli app dp -n prod"],
    "risks": ["deployment"],
    "cached_at": "2025-07-07T15:30:00",
    "source_method": "completion"
  }
}
```

### Version Detection Strategies
```python
def detect_version(command):
    strategies = [
        f"{command} --version",
        f"{command} -v", 
        f"{command} version",
        lambda: parse_help_for_version(command),
        lambda: get_file_modification_time(command)
    ]
    
    for strategy in strategies:
        try:
            return extract_version(strategy)
        except:
            continue
    return "unknown"
```

### Completion Data Parsing
```python
def parse_completion_data(command):
    # Try modern completion generation
    completion_methods = [
        f"{command} completion zsh",
        f"{command} __complete \"\"",
        lambda: find_existing_completion_file(command)
    ]
    
    for method in completion_methods:
        try:
            return extract_subcommands(method)
        except:
            continue
    return None
```

## Troubleshooting

### Common Issues

#### Cache Corruption
- **Symptoms**: JSON parse errors, missing fields
- **Solution**: Delete cache file, rebuilds automatically
- **Prevention**: Atomic writes with temp files

#### Version Detection Failures
- **Symptoms**: Constant re-analysis of same tool
- **Solution**: Fallback to file timestamps
- **Prevention**: Multiple detection strategies

#### Analysis Timeouts
- **Symptoms**: Slow responses, hanging operations
- **Solution**: Increase timeout limits, check tool responsiveness
- **Prevention**: Reasonable timeout defaults (5-8 seconds)

#### Missing Completions
- **Symptoms**: Poor analysis quality for modern tools
- **Solution**: Manual completion generation, framework detection
- **Prevention**: Robust fallback to help parsing

### Debug Information
- **Cache location**: `~/.basher/command_cache.json`
- **Log analysis**: Check tool call responses
- **Manual testing**: Use POC scripts for layer testing
- **Version checking**: Verify version detection accuracy

### Performance Optimization
- **Cache hits**: Monitor cache effectiveness
- **Analysis speed**: Profile each layer performance
- **Memory usage**: Monitor JSON cache size
- **Tool responsiveness**: Track analysis timeouts

## Future Enhancements

### Potential Improvements
- **Interactive mode**: Real-time command construction
- **Shell integration**: Direct shell completion
- **Advanced caching**: Distributed cache for teams
- **Machine learning**: Pattern recognition for command construction
- **API integration**: Direct tool API access when available

### Extensibility
- **Plugin system**: Custom analysis layers
- **Configuration**: User-customizable risk levels
- **Tool-specific handlers**: Specialized analyzers for popular tools
- **Export capabilities**: Share analysis data between instances

---

*This documentation serves as the comprehensive guide for understanding, maintaining, and extending the Basher intelligent CLI command assistant.*