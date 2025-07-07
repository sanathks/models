# Custom Ollama Models with Modelfiles

This project contains custom local Ollama models created using Modelfiles.

## Process for Creating Custom Models

### 1. Model Structure
Each custom model should be organized in its own folder:
```
models/
├── model-name/
│   └── Modelfile
├── another-model/
│   └── Modelfile
└── CLAUDE.md
```

### 2. Creating a New Model
When creating a new custom model:
1. Create a dedicated folder for the model
2. Add a Modelfile inside that folder
3. Configure the Modelfile with appropriate settings

### 3. Modelfile Format
A basic Modelfile structure:
```
FROM base-model

PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM "Your system prompt here"

TEMPLATE """{{ if .System }}<|system|>
{{ .System }}<|end|>
{{ end }}{{ if .Prompt }}<|user|>
{{ .Prompt }}<|end|>
{{ end }}<|assistant|>
{{ .Response }}<|end|>
"""
```

### 4. Building the Model
To build and use a custom model:
```bash
cd model-name/
ollama create model-name -f Modelfile
ollama run model-name
```

## Common Commands

- `ollama list` - List available models
- `ollama create <name> -f <Modelfile>` - Create model from Modelfile
- `ollama run <name>` - Run a specific model
- `ollama rm <name>` - Remove a model