#!/bin/bash

# Single model testing script
# Usage: ./test_models.sh <model_name> <docker_command>
# Returns: exit code 0 (SUCCESS), 1 (FAILURE), 2 (TIMEOUT)

TIMEOUT=600
mkdir -p logs

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <model_name> <docker_command>"
    exit 1
fi

MODEL=$1
COMMAND=$2

# Replace slashes with underscores for log filename
LOG_FILE="logs/${MODEL//\//_}.log"

echo "Testing: $MODEL"
echo "Log: $LOG_FILE"

# Run docker in background
(eval "$COMMAND"; echo "EOF") > "$LOG_FILE" 2>&1 &
DOCKER_PID=$!

# Monitor log file for success/failure
START_TIME=$(date +%s)
while true; do
    # Check timeout
    CURRENT_TIME=$(date +%s)
    if (( CURRENT_TIME - START_TIME > TIMEOUT )); then
        echo "⏱ TIMEOUT"
        kill $DOCKER_PID 2>/dev/null || true
        docker stop $(docker ps -q) 2>/dev/null || true
        exit 2
    fi
    
    # Check if docker process exited (check for EOF in log)
    if grep -q "^EOF$" "$LOG_FILE" 2>/dev/null; then
        echo "✗ FAILURE: Process exited"
        docker stop $(docker ps -q) 2>/dev/null || true
        exit 1
    fi
    
    # Check for success
    if grep -iq "ready to roll\|Server is ready" "$LOG_FILE" 2>/dev/null; then
        echo "✓ SUCCESS"
        kill $DOCKER_PID 2>/dev/null || true
        docker stop $(docker ps -q) 2>/dev/null || true
        exit 0
    fi
    
    sleep 2
done

