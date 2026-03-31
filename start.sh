#!/bin/bash
# Start the LLM Prompt Evaluator FastAPI Backend

echo "Starting LLM Prompt Evaluator API Server..."
echo ""
echo "Make sure Ollama is running before starting."
echo ""
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""

# Stable by default for sharing; use --reload manually during development
uvicorn main:app --host 0.0.0.0 --port 8000
