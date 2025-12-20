# Model Testing Agent

Local agent defined using LangGraph. Environment using DGX Spark. 

## Overview
This tool uses LangGraph to orchestrate an AI agent workflow that:
1. Reads models from a CSV file
2. Uses an LLM to generate Docker serving commands
3. Executes bash tests to validate model serving
4. Automatically retries on failures (up to 3 attempts)
5. Updates CSV with results and moves to next model

## Workflow Architecture

```
START → READ_CSV → GENERATE_COMMAND → EXECUTE_TEST → CHECK_RESULT
           ↑            ↑                                   ↓
           │            └──────── RETRY (if fail) ─────────┤
           │                                                ↓
           └────────────────── UPDATE_CSV ←─────────────────
```

## Quick Start 

### 1. Spin up Local LLM (e.g. LLama3.1)
```bash
export HF_TOKEN="hf_xxx"

docker run --gpus all --shm-size 32g -p 30000:30000 -v ~/.cache/huggingface:/root/.cache/huggingface --env HF_TOKEN=""$HF_TOKEN"" --ipc=host --name test_container lmsysorg/sglang:nightly-dev-cu13-20251208-599686b8 python3 -m sglang.launch_server --model-path nvidia/Llama-3.1-8B-Instruct-FP4 --host 0.0.0.0 --port 30000 --quantization modelopt_fp4 --mem-fraction-static 0.7 --trust-remote-code 
```

### 2. Prepare Your CSV
The CSV should have columns: `Model`, `Support Status`, and `HF Handle`
- Example provided in `models_documentation.csv`

### 3. Run
```bash
pip install -r requirements.txt

python3 agent.py
```

## Next Steps 
Advanced agent: https://build.nvidia.com/spark/multi-agent-chatbot