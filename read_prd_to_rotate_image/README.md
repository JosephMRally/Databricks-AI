# Run ollama qwen:4b on a mac locally
1. brew install --cask docker
1. brew install docker-compose
1. brew install --cask docker-desktop
1. run docker-desktop
1. python3 -m venv venv
1. source venv/bin/activate
1. pip install --upgrade pip
1. pip install -r ollama_requirements.txt
1. docker compose down; docker compose up -d
1. Watch docker logs, takes about 1hr to exec ollama_entrypoint.sh on 1st run
1. python ollama_agentic_ai.py (on your local terminal)

