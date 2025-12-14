# model-tester
Test different models on DGX Spark using an autonomous LangGraph agent

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

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set OpenAI API Key
```bash
export OPENAI_API_KEY=your_key_here
# Or create a .env file (copy from env.example)
```

### 3. Prepare Your CSV
The CSV should have columns: `Model`, `status`, `command`, `note`
- Models with `status=Yes` are skipped (already tested)
- Example provided in `models_documentation.csv`

### 4. Make Scripts Executable
```bash
chmod +x test_models.sh agent_workflow.py
```

## Usage

### Run Full Workflow
```bash
./agent_workflow.py --csv models_documentation.csv
```

### Test Single Model (Manual)
```bash
./test_models.sh "meta-llama/Llama-2-7b-hf" "docker run --gpus all ..."
```

## Files

- `agent_workflow.py` - Main LangGraph agent orchestrator
- `test_models.sh` - Bash script for single model testing
- `models_documentation.csv` - List of models to test
- `requirements.txt` - Python dependencies
- `logs/` - Test execution logs (auto-created)

## Features

- ✅ **Autonomous Retry Logic**: LLM learns from failures and generates new commands
- ✅ **State Management**: Tracks progress through entire CSV
- ✅ **Timeout Handling**: 600s timeout per test
- ✅ **Detailed Logging**: All test outputs saved to `logs/`
- ✅ **CSV Auto-Update**: Results written back automatically

## Agent Workflow Details

The workflow uses LangGraph with the following nodes:

1. **read_next_model**: Finds next untested model in CSV
2. **generate_command**: LLM generates Docker command (with retry context)
3. **execute_test**: Runs bash script, captures result
4. **update_csv**: Writes results back to CSV

Conditional edges handle retry logic and completion detection.