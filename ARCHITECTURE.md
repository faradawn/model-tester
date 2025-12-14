# LangGraph Agent Workflow Architecture

## State Machine Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        START                                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
                  ┌────────────────┐
                  │ read_next_model│
                  │                │
                  │ • Read CSV     │
                  │ • Find untested│
                  │ • Load state   │
                  └────────┬───────┘
                           │
                     ┌─────┴─────┐
                     │ Completed?│
                     └─────┬─────┘
                           │
              ┌────────────┼────────────┐
              │ YES        │ NO         │
              ▼            ▼            │
            ┌───┐   ┌──────────────┐   │
            │END│   │generate_cmd  │   │
            └───┘   │              │   │
                    │ • LLM prompt │   │
                    │ • Retry ctx  │   │
                    │ • Generate   │   │
                    └──────┬───────┘   │
                           │           │
                           ▼           │
                    ┌──────────────┐   │
                    │execute_test  │   │
                    │              │   │
                    │ • Run bash   │   │
                    │ • Capture    │   │
                    │ • Parse logs │   │
                    └──────┬───────┘   │
                           │           │
                           ▼           │
                    ┌──────────────┐   │
                    │ Check Result │   │
                    └──────┬───────┘   │
                           │           │
              ┌────────────┼────────────┐
              │            │            │
         SUCCESS      FAILURE       TIMEOUT
              │      (retry<3)    (retry<3)
              │            │            │
              ▼            └────┬───────┘
       ┌──────────┐            │
       │update_csv│            │ Increment
       │          │◄───────────┘ retry_count
       │ • Write  │                   │
       │ • Status │                   │
       │ • Notes  │                   │
       └────┬─────┘                   │
            │                         │
            └─────────────────────────┘
                           │
                           └─────────► LOOP BACK
```

## State Object Structure

```python
ModelTestState = {
    'model_name': str,           # Current model being tested
    'docker_command': str,       # Generated docker command
    'test_result': str | None,   # "SUCCESS"|"FAILURE"|"TIMEOUT"
    'retry_count': int,          # Current retry attempt (0-3)
    'error_logs': str,           # Logs from failed attempts
    'csv_path': str,             # Path to CSV file
    'current_row_index': int,    # Current CSV row index
    'all_models': list,          # All CSV rows in memory
    'completed': bool            # All models tested?
}
```

## Node Functions

### 1. `read_next_model_node`
**Purpose**: Find next untested model from CSV

**Logic**:
- Load CSV if not in state
- Iterate through rows
- Skip if `status == "Yes"`
- Return first untested model
- Set `completed=True` if none found

**State Updates**:
- `model_name`
- `current_row_index`
- `retry_count = 0`
- `completed`

---

### 2. `generate_command_node`
**Purpose**: Use LLM to generate docker command

**Logic**:
- Initialize ChatOpenAI
- Build prompt with model name
- If retry > 0, include error logs in context
- Generate command via LLM
- Strip and clean output

**State Updates**:
- `docker_command`

**LLM Prompt Structure**:
```
System: You are expert in deploying LLMs on DGX...
User: Model: {model_name}
      {retry_context with previous errors}
      Generate docker command:
```

---

### 3. `execute_test_node`
**Purpose**: Run bash script to test model

**Logic**:
- Call `subprocess.run(["./test_models.sh", model, cmd])`
- Capture exit code: 0=SUCCESS, 1=FAILURE, 2=TIMEOUT
- Read log file from `logs/`
- Store in state

**State Updates**:
- `test_result`
- `error_logs`

---

### 4. `update_csv_node`
**Purpose**: Write results back to CSV

**Logic**:
- Read entire CSV
- Update specific row:
  - `status = "Yes"` if SUCCESS
  - `status = "No"` if FAILURE/TIMEOUT
  - `note = error description`
- Write back to file

**State Updates**: None (writes to disk)

---

## Conditional Edges

### `check_completion(state) -> str`
After `read_next_model`:
- If `completed == True` → `"end"` (END graph)
- Else → `"read_next"` (continue to generate_command)

### `should_retry(state) -> str`
After `execute_test`:
- If `test_result == "SUCCESS"` → `"update_csv"`
- If `retry_count < 3` → `"retry"` (back to generate_command)
- If `retry_count >= 3` → `"update_csv"` (give up, move to next)

---

## Execution Flow Example

### Happy Path (Success on first try)
```
START
  → read_next_model (finds "llama-2-7b")
  → generate_command (LLM generates "docker run...")
  → execute_test (exit code 0)
  → should_retry → "update_csv"
  → update_csv (writes "Yes" to CSV)
  → read_next_model (finds next model)
  ...
```

### Retry Path (Failure → Success)
```
START
  → read_next_model (finds "mistral-7b")
  → generate_command (attempt 1)
  → execute_test (exit code 1, FAILURE)
  → should_retry → "retry" (retry_count=1)
  → generate_command (attempt 2, with error context)
  → execute_test (exit code 0, SUCCESS)
  → should_retry → "update_csv"
  → update_csv (writes "Yes")
  ...
```

### Max Retries Path
```
START
  → read_next_model
  → generate_command (attempt 1)
  → execute_test (FAILURE)
  → retry → generate_command (attempt 2)
  → execute_test (FAILURE)
  → retry → generate_command (attempt 3)
  → execute_test (FAILURE)
  → should_retry → "update_csv" (retry_count=3, give up)
  → update_csv (writes "No" with note)
  ...
```

---

## Key Design Decisions

### Why LangGraph over Simple Agent?
- **Better control flow**: Explicit state machine vs implicit tool calling
- **State persistence**: Easy to see/debug current state
- **Conditional routing**: Clean retry logic without prompt hacks
- **Resumability**: Could add checkpointing for long-running jobs

### Retry Strategy
- Max 3 attempts per model
- LLM gets error logs as context on retry
- Allows model to learn from failures
- Prevents infinite loops

### CSV as Single Source of Truth
- All progress tracked in CSV
- Can stop/resume workflow
- Status field prevents re-testing
- Notes field captures failure reasons

### Bash Script Separation
- Docker operations isolated from Python
- Easier to test independently
- Timeout handling at system level
- Log files persisted on disk

---

## Extension Ideas

### 1. Parallel Testing
Use LangGraph's parallel nodes to test multiple models simultaneously:
```python
workflow.add_node("parallel_tests", lambda: [test1, test2, test3])
```

### 2. Checkpointing
Add LangGraph persistence to resume from crashes:
```python
from langgraph.checkpoint import MemorySaver
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### 3. Human-in-the-Loop
Add interruption point for manual approval:
```python
workflow.add_node("human_review", interrupt("Review command?"))
```

### 4. Advanced LLM Context
- Pass DGX hardware specs to LLM
- Include model card metadata
- Reference successful commands from other models

### 5. Metrics & Monitoring
- Track total runtime per model
- Log LLM token usage
- Dashboard for live progress

