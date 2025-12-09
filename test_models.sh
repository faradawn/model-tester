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
    
    (eval "$command"; echo "EOF") 2>&1 | tee "$log_file" | \
    timeout $TIMEOUT grep -m1 -E "EOF|ready to roll|Server is ready" | \
    while read -r line; do
        if [[ "$line" == "EOF" ]]; then
            echo "✗ FAILURE: Process exited"
            return 1
        elif echo "$line" | grep -iq "ready to roll\|Server is ready"; then
            echo "✓ SUCCESS"
            return 0
        fi
    done
    
    echo "⏱ TIMEOUT"
    
    # Stop container
    docker stop $(docker ps -q) 2>/dev/null || true
    sleep 5
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

