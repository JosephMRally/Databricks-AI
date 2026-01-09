#!/bin/bash
# docker compose down; docker compose up -d
# Start Ollama in the background.
/bin/ollama serve &
# Record Process ID.
pid=$!

# Pause for Ollama to start.
sleep 5

# hf.co/unsloth/Qwen3-4B-Thinking-2507-GGUF:Q4_K_M
# qwen3:4b
# qwen3:4b-instruct
echo "Retrieving model"
ollama pull qwen3:4b
echo "Done."

# Wait for Ollama process to finish.
wait $pid

# install qwen-agent python libraries
echo "Installing requirements"
pip install -r requirements.txt
echo "Done."

