brew install ollama
brew services start ollama
ollama pull qwen3:14b qwen3-vl
brew install mlx-lx
brew install python@3.13
python3.13 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium