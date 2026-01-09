# Run ollama qwen:4b on a mac locally
1. brew install --cask docker
1. brew install docker-compose
1. brew install --cask docker-desktop
1. run docker-desktop
1. python3 -m venv venv
1. source venv/bin/activate
1. pip install -i ollama_requirements.txt
1. docker compose down; docker compose up -d
1. python ollama_agentic_ai.py

