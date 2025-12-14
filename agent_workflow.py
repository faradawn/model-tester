#!/usr/bin/env python3
"""
LangGraph Agent Workflow for Model Testing
Orchestrates CSV reading, LLM command generation, bash execution, and result tracking
"""

import os
import csv
import subprocess
from typing import TypedDict, Literal, Optional
from datetime import datetime

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Load environment variables from .env file
load_dotenv()


# ============================================================================
# State Definition
# ============================================================================

class ModelTestState(TypedDict):
    """State that flows through the graph"""
    model_name: str
    docker_command: str
    test_result: Optional[Literal["SUCCESS", "FAILURE", "TIMEOUT"]]
    retry_count: int
    error_logs: str
    csv_path: str
    current_row_index: int
    all_models: list  # List of all CSV rows
    completed: bool


# ============================================================================
# Helper Functions
# ============================================================================

def read_csv_file(csv_path: str) -> list:
    """Read CSV and return list of model dictionaries"""
    models = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            row['_index'] = idx  # Track original row index
            models.append(row)
    return models


def update_csv_file(csv_path: str, row_index: int, status: str, notes: str = ""):
    """Update CSV file with test results"""
    models = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        models = list(reader)
    
    # Update the specific row
    if row_index < len(models):
        models[row_index]['status'] = status
        if notes:
            models[row_index]['note'] = notes
    
    # Write back to CSV
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(models)


def execute_bash_test(model_name: str, command: str) -> tuple[int, str]:
    """
    Execute test_models.sh script
    Returns: (exit_code, log_content)
    """
    bash_script = "./test_models.sh"
    
    try:
        # Run the bash script
        result = subprocess.run(
            [bash_script, model_name, command],
            capture_output=True,
            text=True,
            timeout=650  # Slightly longer than script timeout
        )
        
        # Read log file
        log_file = f"logs/{model_name.replace('/', '_')}.log"
        log_content = ""
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                log_content = f.read()
        
        return result.returncode, log_content
    
    except subprocess.TimeoutExpired:
        return 2, "Script execution timed out"
    except Exception as e:
        return 1, f"Error executing script: {str(e)}"


# ============================================================================
# Graph Nodes
# ============================================================================

def read_next_model_node(state: ModelTestState) -> ModelTestState:
    """Read next untested model from CSV"""
    print("\n" + "="*60)
    print("📖 Reading next model from CSV...")
    
    # Load all models if not already loaded
    if not state.get('all_models'):
        state['all_models'] = read_csv_file(state['csv_path'])
    
    # Find next untested model
    for idx, model_row in enumerate(state['all_models']):
        # Skip if already tested (status == "Yes")
        if model_row.get('status', '').strip().lower() != 'yes':
            state['model_name'] = model_row.get('model', model_row.get('Model', ''))
            state['current_row_index'] = model_row['_index']
            state['retry_count'] = 0
            state['error_logs'] = ""
            state['completed'] = False
            
            print(f"✓ Found model to test: {state['model_name']}")
            return state
    
    # No more models to test
    print("✓ All models tested!")
    state['completed'] = True
    return state


def generate_command_node(state: ModelTestState) -> ModelTestState:
    """Use LLM to generate docker serving command"""
    print(f"\n🤖 Generating command for: {state['model_name']}")
    print(f"   Retry count: {state['retry_count']}")
    
    # Initialize LLM - use model from environment or default to gpt-4o-mini (fast & cheap)
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm = ChatOpenAI(model=model_name, temperature=0)
    print(f"   Using LLM: {model_name}")
    
    # Create prompt with context
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an expert in deploying LLM models using Docker on DGX Spark systems.
Generate a docker command to serve the given model. The command should:
- Use appropriate container images for the model type
- Configure proper GPU settings
- Expose necessary ports
- Set up model serving correctly

Return ONLY the docker command, no explanations."""),
        ("user", """Model: {model_name}

{retry_context}

Generate the docker serving command:""")
    ])
    
    # Add retry context if this is a retry
    retry_context = ""
    if state['retry_count'] > 0:
        retry_context = f"""
PREVIOUS ATTEMPT FAILED. This is retry #{state['retry_count']}.

Previous error logs:
{state['error_logs'][:1000]}

Please generate a DIFFERENT command that addresses the issues above.
"""
    
    # Generate command
    chain = prompt_template | llm | StrOutputParser()
    command = chain.invoke({
        "model_name": state['model_name'],
        "retry_context": retry_context
    })
    
    state['docker_command'] = command.strip()
    print(f"✓ Generated command: {state['docker_command'][:100]}...")
    
    return state


def execute_test_node(state: ModelTestState) -> ModelTestState:
    """Execute bash script to test the model"""
    print(f"\n⚙️  Executing test for: {state['model_name']}")
    print(f"   Command: {state['docker_command'][:100]}...")
    
    exit_code, log_content = execute_bash_test(
        state['model_name'],
        state['docker_command']
    )
    
    # Map exit code to result
    result_map = {
        0: "SUCCESS",
        1: "FAILURE",
        2: "TIMEOUT"
    }
    state['test_result'] = result_map.get(exit_code, "FAILURE")
    state['error_logs'] = log_content
    
    print(f"✓ Test result: {state['test_result']}")
    
    return state


def update_csv_node(state: ModelTestState) -> ModelTestState:
    """Update CSV with test results"""
    print(f"\n📝 Updating CSV...")
    
    status = "Yes" if state['test_result'] == "SUCCESS" else "No"
    notes = ""
    
    if state['test_result'] == "FAILURE":
        notes = f"Failed after {state['retry_count'] + 1} attempts"
    elif state['test_result'] == "TIMEOUT":
        notes = "Test timed out"
    
    update_csv_file(
        state['csv_path'],
        state['current_row_index'],
        status,
        notes
    )
    
    print(f"✓ CSV updated: status={status}")
    
    return state


# ============================================================================
# Conditional Edge Functions
# ============================================================================

def should_retry(state: ModelTestState) -> str:
    """Decide whether to retry or move to next model"""
    
    # If success, update CSV and move to next
    if state['test_result'] == "SUCCESS":
        return "update_csv"
    
    # If failure/timeout and retries left, retry
    if state['retry_count'] < 3:
        state['retry_count'] += 1
        print(f"⚠️  Will retry (attempt {state['retry_count'] + 1}/3)")
        return "retry"
    
    # Max retries reached, update CSV and move to next
    print(f"❌ Max retries reached, moving to next model")
    return "update_csv"


def check_completion(state: ModelTestState) -> str:
    """Check if all models are tested"""
    if state.get('completed', False):
        return "end"
    return "read_next"


# ============================================================================
# Build Graph
# ============================================================================

def create_workflow() -> StateGraph:
    """Create and configure the LangGraph workflow"""
    
    # Initialize graph
    workflow = StateGraph(ModelTestState)
    
    # Add nodes
    workflow.add_node("read_next_model", read_next_model_node)
    workflow.add_node("generate_command", generate_command_node)
    workflow.add_node("execute_test", execute_test_node)
    workflow.add_node("update_csv", update_csv_node)
    
    # Set entry point
    workflow.set_entry_point("read_next_model")
    
    # Add edges
    workflow.add_conditional_edges(
        "read_next_model",
        check_completion,
        {
            "read_next": "generate_command",
            "end": END
        }
    )
    
    workflow.add_edge("generate_command", "execute_test")
    
    workflow.add_conditional_edges(
        "execute_test",
        should_retry,
        {
            "retry": "generate_command",
            "update_csv": "update_csv"
        }
    )
    
    workflow.add_edge("update_csv", "read_next_model")
    
    return workflow.compile()


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Model testing agent workflow")
    parser.add_argument(
        "--csv",
        default="models_documentation.csv",
        help="Path to CSV file with model list"
    )
    args = parser.parse_args()
    
    # Verify CSV exists
    if not os.path.exists(args.csv):
        print(f"❌ Error: CSV file not found: {args.csv}")
        return
    
    # Verify bash script exists
    if not os.path.exists("test_models.sh"):
        print("❌ Error: test_models.sh not found")
        return
    
    print("🚀 Starting Model Testing Agent Workflow")
    print(f"📄 CSV File: {args.csv}")
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create workflow
    app = create_workflow()
    
    # Initialize state
    initial_state = ModelTestState(
        model_name="",
        docker_command="",
        test_result=None,
        retry_count=0,
        error_logs="",
        csv_path=args.csv,
        current_row_index=0,
        all_models=[],
        completed=False
    )
    
    # Run workflow
    try:
        final_state = app.invoke(initial_state)
        print("\n" + "="*60)
        print("✅ Workflow completed successfully!")
        print(f"⏰ End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except KeyboardInterrupt:
        print("\n⚠️  Workflow interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()

