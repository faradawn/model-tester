# Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies
```bash
cd model-tester
pip install -r requirements.txt
```

### Step 2: Set API Key
```bash
export OPENAI_API_KEY="sk-..."
```

Or create a `.env` file:
```bash
cp env.example .env
# Edit .env and add your key
```

### Step 3: Prepare CSV (optional)
Edit `models_documentation.csv` with your models:
```csv
Model,status,command,note
meta-llama/Llama-2-7b-hf,No,"","Not yet tested"
mistralai/Mistral-7B-v0.1,No,"","Not yet tested"
```

### Step 4: Run the Agent
```bash
./agent_workflow.py
```

That's it! The agent will:
1. 📖 Read the CSV
2. 🤖 Generate docker commands using GPT-4
3. ⚙️ Test each model
4. 🔄 Retry on failures (up to 3x)
5. 📝 Update CSV with results

---

## 📊 Example Output

```
🚀 Starting Model Testing Agent Workflow
📄 CSV File: models_documentation.csv
⏰ Start Time: 2024-12-14 10:30:00

============================================================
📖 Reading next model from CSV...
✓ Found model to test: meta-llama/Llama-2-7b-hf

🤖 Generating command for: meta-llama/Llama-2-7b-hf
   Retry count: 0
✓ Generated command: docker run --gpus all -p 8000:8000...

⚙️  Executing test for: meta-llama/Llama-2-7b-hf
   Command: docker run --gpus all -p 8000:8000...
Testing: meta-llama/Llama-2-7b-hf
Log: logs/meta-llama_Llama-2-7b-hf.log
✓ SUCCESS
✓ Test result: SUCCESS

📝 Updating CSV...
✓ CSV updated: status=Yes

============================================================
📖 Reading next model from CSV...
✓ Found model to test: mistralai/Mistral-7B-v0.1
...
```

---

## 🧪 Testing Single Model Manually

```bash
./test_models.sh "meta-llama/Llama-2-7b-hf" \
  "docker run --gpus all -p 8000:8000 nvcr.io/nvidia/pytorch:23.10-py3 \
   python -m vllm.entrypoints.openai.api_server \
   --model meta-llama/Llama-2-7b-hf"
```

**Exit Codes:**
- `0` = Success (model ready)
- `1` = Failure (crashed/error)
- `2` = Timeout (>600s)

---

## 📁 File Structure After Running

```
model-tester/
├── agent_workflow.py          # Main agent
├── test_models.sh             # Bash tester
├── models_documentation.csv   # Your models (UPDATED)
├── requirements.txt
├── logs/                      # Created automatically
│   ├── meta-llama_Llama-2-7b-hf.log
│   └── mistralai_Mistral-7B-v0.1.log
└── README.md
```

---

## ⚙️ Advanced Options

### Test Specific CSV File
```bash
./agent_workflow.py --csv my_models.csv
```

### Use Different LLM
Edit the code or set environment variable:
```python
# In agent_workflow.py, line ~105:
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
```

### Adjust Timeout
Edit `test_models.sh` line 11:
```bash
TIMEOUT=1200  # 20 minutes
```

### Resume After Interruption
Just run again! Models with `status=Yes` are automatically skipped.

---

## 🐛 Troubleshooting

### Problem: "OPENAI_API_KEY not found"
```bash
export OPENAI_API_KEY="sk-..."
# Or create .env file
```

### Problem: "test_models.sh: Permission denied"
```bash
chmod +x test_models.sh agent_workflow.py
```

### Problem: All tests timeout
- Check docker is running: `docker ps`
- Increase timeout in `test_models.sh`
- Check GPU availability: `nvidia-smi`

### Problem: LLM generates invalid commands
- Try GPT-4 instead of GPT-3.5
- Add examples to the prompt (edit `generate_command_node`)
- Manually test command first

---

## 💡 Tips

1. **Start Small**: Test with 1-2 models first
2. **Check Logs**: Look in `logs/` for detailed error messages
3. **Iterate Prompts**: Improve the LLM prompt based on failures
4. **Manual Override**: You can edit CSV `command` column to force specific commands

---

## 🎯 Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for deep dive
- Customize LLM prompt in `generate_command_node()`
- Add more models to CSV
- Set up parallel testing for faster runs

