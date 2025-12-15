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
    command_outcome: str
    retry_count: int  # Track number of consecutive failures

def generate_command(state: MyState):
    # Read CSV and find first unsupported model
    with open(state['csv_path'], 'r') as f:
        rows = list(csv.DictReader(f))
        
    for i in range(state['row_idx'], len(rows)):
        if rows[i]['Supported Status'].strip().lower() != 'yes':
            model_name = rows[i]['Model'].strip()
            break
    else:
        print("=== No more models! Go to end")
        return Command(goto=END)  # No unsupported models found
    
    # Check if this is a retry and read previous failure log
    previous_error = ""
    if state["retry_count"] > 0:
        log_file_path = f"logs/{model_name.replace('/', '_')}.log"
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r') as log_file:
                all_lines = log_file.readlines()
                last_100_lines = all_lines[-100:] if len(all_lines) > 100 else all_lines
                previous_error = ''.join(last_100_lines)
                print(f"=== Retry attempt {state['retry_count']}: Reading previous error log")
    
    # Build prompt based on whether this is a retry or not
    if state["retry_count"] > 0:
        prompt = f'''
The previous command for model {model_name} failed. Below is the error output from the last 100 lines:

--- Previous Error Log ---
{previous_error}
--- End of Error Log ---

Based on the error above, and SGLang inference engine docs, debug the issue and generate a corrected docker run command. 
Modify the --quantization flag (modelopt_fp8 or modelopt_fp4) or other parameters as needed to fix the error.
Output only the corrected command, without any additional text or punctuations.

Base command template:
docker run --gpus all --shm-size 32g -p 30000:30000 -v ~/.cache/huggingface:/root/.cache/huggingface --env HF_TOKEN=""$HF_TOKEN"" --ipc=host --name test_container lmsysorg/sglang:nightly-dev-cu13-20251208-599686b8 python3 -m sglang.launch_server --model-path {model_name} --host 0.0.0.0 --port 30000 --quantization modelopt_fp8 --mem-fraction-static 0.7 --trust-remote-code --disable-cuda-graph
    '''
    else:
        prompt = f'''
Modify the --quantization flag (modelopt_fp8 or modelopt_fp4) based on the model name. Output only the command, without any additional text or punctuations.

docker run --gpus all --shm-size 32g -p 30000:30000 -v ~/.cache/huggingface:/root/.cache/huggingface --env HF_TOKEN=""$HF_TOKEN"" --ipc=host --name test_container lmsysorg/sglang:nightly-dev-cu13-20251208-599686b8 python3 -m sglang.launch_server --model-path {model_name} --host 0.0.0.0 --port 30000 --quantization modelopt_fp8 --mem-fraction-static 0.7 --trust-remote-code --disable-cuda-graph
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
    
    command = "source .env && " + state["command_to_run"] +  " && echo MyEOF"  # Append MyEOF at the end so that if we reach this MyEOF, it means the command failed. If we don't see this, then the server is successfully launched and blocked the terminal, so this won't show
    process = subprocess.Popen(command, shell=True, executable='/bin/bash', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1) 

    command_outcome = "unknown"  # Initialize outcome
    # Stream the output line by line
    with open(f"logs/{model_name}.log", 'w') as log_file:
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output, end="")
                log_file.write(output)

                if "ready to roll" in output:  # This means the server is launched and will stay launched (block the terminal)
                    command_outcome = "success"
                    break
                    
                if "MyEOF" in output:  # This means the process exited and failed
                    command_outcome = "failed"
                    break

    # Clean up: stop and remove the docker container
    subprocess.run("docker stop test_container && docker rm -f test_container", shell=True, executable='/bin/bash')

    # Wait for the process to fully finish
    process.wait()

    if command_outcome == "success":
        # Update CSV: set Supported Status to "Yes" for current model
        with open(state['csv_path'], 'r') as f:
            rows = list(csv.DictReader(f))
        
        # Find and update the row for current model
        fieldnames = rows[0].keys() if rows else []
        for row in rows:
            if row['Model'].strip() == state['current_model_name']:
                row['Supported Status'] = 'Yes'
                break
        
        # Write back to CSV
        with open(state['csv_path'], 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"=== Updated CSV: {state['current_model_name']} -> Supported Status = Yes")
        
        # Reset retry count on success and go back to generate_command to process next model
        return Command(update={"command_outcome": command_outcome, "retry_count": 0}, goto="generate_command")
    elif command_outcome == "failed":
        # Increment retry count on failure
        new_retry_count = state.get('retry_count', 0) + 1
        print(f"=== Command failed. Retry count: {new_retry_count}")
        return Command(update={"command_outcome": command_outcome, "retry_count": new_retry_count}, goto="generate_command")
    else:
        print("=== Should not happen - unknown status")
        return
    


workflow = StateGraph(MyState)
workflow.add_node("generate_command", generate_command)
workflow.add_node("execute_command", execute_command)

workflow.add_edge(START, "generate_command")
workflow.add_edge("generate_command", "execute_command")
workflow.add_edge("execute_command", END)

agent = workflow.compile()

agent.invoke({"row_idx": 0, "csv_path": "models_documentation.csv", "retry_count": 1})


    