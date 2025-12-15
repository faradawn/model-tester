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

### 4. Run
```bash
source .env && python3 agent.py
```
