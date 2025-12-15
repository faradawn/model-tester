from typing import Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command, RetryPolicy
from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage
import csv
import subprocess
import os

llm = ChatOpenAI(model="gpt-4o-mini")

class MyState(TypedDict):
    row_idx: int
    csv_path: str
    current_model_name: str
    command_to_run: str

def generate_command(state: MyState):
    # Read CSV and find first unsupported model
    with open(state['csv_path'], 'r') as f:
        rows = list(csv.DictReader(f))
        
    for i in range(state['row_idx'], len(rows)):
        if rows[i]['Supported Status'].strip().lower() != 'yes':
            model_name = rows[i]['Model'].strip()
            break
    else:
        print("=== No more models")
        return  # No unsupported models found
    
    prompt = f'''
Modify the --quantization flag (modelopt_fp8 or modelopt_fp4) based on the model name. Output only the command, without any additional text or punctuations.

source .env && docker run --gpus all --shm-size 32g -p 30000:30000 -v ~/.cache/huggingface:/root/.cache/huggingface --env HF_TOKEN=""$HF_TOKEN"" --ipc=host lmsysorg/sglang:nightly-dev-cu13-20251208-599686b8 python3 -m sglang.launch_server --model-path {model_name} --host 0.0.0.0 --port 30000 --quantization modelopt_fp8 --mem-fraction-static 0.7 --trust-remote-code --disable-cuda-graph
    '''

    llm_result = llm.invoke(prompt).content
    print("=== Model name", model_name)
    print("=== LLM result: ", llm_result)
    return {"command_to_run": llm_result, "current_model_name": model_name}

def execute_command(state: MyState):
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Get model name and replace slashes with underscores
    model_name = state['current_model_name'].replace('/', '_')
    
    command = state["command_to_run"]
    process = subprocess.Popen(command, shell=True, executable='/bin/bash', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1) 

    # Stream the output line by line
    with open(f"logs/{model_name}.log", 'w') as log_file:
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output, end="")
                log_file.write(output)

    # Wait for the process to fully finish
    process.wait()

    return {}
        



workflow = StateGraph(MyState)
workflow.add_node("generate_command", generate_command)
workflow.add_node("execute_command", execute_command)

workflow.add_edge(START, "generate_command")
workflow.add_edge("generate_command", "execute_command")
workflow.add_edge("execute_command", END)

agent = workflow.compile()

agent.invoke({"row_idx": 0, "csv_path": "models_documentation.csv"})


    