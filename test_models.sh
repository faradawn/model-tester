#!/bin/bash

# Simple model testing script
# Usage: ./test_models.sh [model_name]
# If model_name provided, test only that model
# Logic: Run docker command with EOF marker
#   - If "ready to roll" appears = SUCCESS
#   - If "EOF" appears first = FAILURE
#   - If timeout = TIMEOUT

TIMEOUT=600
mkdir -p logs
TEST_MODEL="${1:-}"  # Optional: specific model to test

test_model() {
    local model=$1
    local command=$2
    # Replace slashes with underscores for log filename
    local log_file="logs/${model//\//_}.log"
    
    echo "Testing: $model"
    echo "Log: $log_file"
    
    # Run docker in background
    (eval "$command"; echo "EOF") > "$log_file" 2>&1 &
    local docker_pid=$!
    
    # Monitor log file for success/failure
    local start_time=$(date +%s)
    while true; do
        # Check timeout
        local current_time=$(date +%s)
        if (( current_time - start_time > TIMEOUT )); then
            echo "⏱ TIMEOUT"
            kill $docker_pid 2>/dev/null || true
            docker stop $(docker ps -q) 2>/dev/null || true
            return 2
        fi
        
        # Check if docker process exited (check for EOF in log)
        if grep -q "^EOF$" "$log_file" 2>/dev/null; then
            echo "✗ FAILURE: Process exited"
            docker stop $(docker ps -q) 2>/dev/null || true
            return 1
        fi
        
        # Check for success
        if grep -iq "ready to roll\|Server is ready" "$log_file" 2>/dev/null; then
            echo "✓ SUCCESS"
            kill $docker_pid 2>/dev/null || true
            docker stop $(docker ps -q) 2>/dev/null || true
            return 0
        fi
        
        sleep 2
    done
}

# Read CSV and test each model
while IFS=',' read -r model status command note; do
    # Skip header
    [[ "$model" == "Model" ]] && continue
    [[ -z "$model" ]] && continue
    
    # If specific model requested, skip others
    if [[ -n "$TEST_MODEL" ]]; then
        [[ "$model" != "$TEST_MODEL" ]] && continue
    else
        # If testing all, skip models already marked as "Yes" (already tested)
        [[ "$status" == "Yes" ]] && continue
    fi
    
    # Strip surrounding quotes from command
    command=$(echo "$command" | sed 's/^"//;s/"$//')
    
    test_model "$model" "$command"
    echo ""
done < models_documentation.csv
