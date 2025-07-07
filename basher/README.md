# Basher - Intelligent CLI Command Assistant

## Setup

1. **Install Ollama**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Create the Model**
   ```bash
   ollama create basher -f Modelfile
   ```

3. **Install Dependencies**
   ```bash
   pip install ollama
   ```

## Usage

```bash
python basher.py "list pods with kubectl"
```

## Examples

```bash
$ python basher.py "scale deployment to 5 replicas"
kubectl scale deployment/myapp --replicas=5

$ python basher.py "delete all files recursively"
⚠️ Warning: This will permanently delete all files recursively
rm -rf *
```
