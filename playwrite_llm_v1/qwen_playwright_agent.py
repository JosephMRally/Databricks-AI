"""
qwen_playwright_agent.py — Browser agent using qwen3:14b + Playwright
======================================================================

Uses Ollama's native tool calling API (qwen3:14b) to drive Playwright.
qwen3:14b is a vision-capable model — it can analyze screenshots directly.
No Claude, no tokens, fully local.

HOW TO RUN
----------
1. Pull the model:
       ollama pull qwen3:14b

2. Install dependencies:
       pip install ollama playwright
       playwright install chromium

3. Run interactively:
       python qwen_playwright_agent.py

4. One-shot task:
       python qwen_playwright_agent.py --task 'go to finance.yahoo.com and browser_take_screenshot filename:test1.png fullPage:False. analyze_image_file: test1.png, "Return only an integer value, what is the value below the text 'S&P 500'?"'

5. With a starting URL:
       python qwen_playwright_agent.py --url "https://google.com" --task "https://medium.com/@ultrarelativistic"

6. Analyze an image directly:
       python qwen_playwright_agent.py --image screenshot.png --task "what is shown in this image?"
"""

import argparse
import json
import subprocess
from playwright.sync_api import sync_playwright, Page
import ollama

# ── Config ───────────────────────────────────────────────────────────────────
MODEL = "qwen3:14b"
VISION_MODEL = "qwen3-vl"  # vision-capable model for image analysis
HEADLESS = False # set to False for demonstration
MAX_STEPS = 15

# ── Tool definitions (Ollama native function calling format) ──────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigate the browser to a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Full URL to navigate to"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element on the page by CSS selector or visible text",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text=... to identify the element"}
                },
                "required": ["selector"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type text into an input field",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input field"},
                    "text": {"type": "string", "description": "Text to type"},
                    "submit": {"type": "boolean", "description": "Press Enter after typing (default false)"}
                },
                "required": ["selector", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Read the visible text content of the current page",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Take a screenshot of the current page and save it",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename to save the screenshot (e.g. result.png)"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_page_visually",
            "description": "Take a screenshot of the current page and analyze it visually using the vision model. Use this when you need to understand images, charts, diagrams, or visual layout that cannot be captured by text alone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "What to look for or analyze in the screenshot"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_image_file",
            "description": "Analyze an existing image file using the vision model",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Path to the image file to analyze"},
                    "question": {"type": "string", "description": "What to look for or analyze in the image"}
                },
                "required": ["filename", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the page up or down",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["down", "up"], "description": "Scroll direction"}
                },
                "required": ["direction"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_page_info",
            "description": "Get the current page URL and title",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "go_back",
            "description": "Navigate back to the previous page",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]


# ── Vision helpers ────────────────────────────────────────────────────────────
def ensure_model(model_name: str, label: str = "Model"):
    """Check if a model is available in Ollama, pull it if not."""
    try:
        models = ollama.list()
        names = [m["model"] for m in models.get("models", [])]
        if not any(model_name in n for n in names):
            print(f"[{label}] {model_name} not found. Downloading...")
            subprocess.run(["ollama", "pull", model_name], check=True)
            print(f"[{label}] {model_name} ready.")
        else:
            print(f"[{label}] {model_name} already installed.")
    except Exception as e:
        print(f"[{label}] Warning: could not verify/pull {model_name}: {e}")


def ensure_vision_model():
    ensure_model(VISION_MODEL, label="Vision")


def vision_query(image_path: str, question: str) -> str:
    """Send an image + question to the vision model and return the answer."""
    ensure_vision_model()
    response = ollama.chat(
        model=VISION_MODEL,
        messages=[{
            "role": "user",
            "content": question,
            "images": [image_path]  # ollama accepts file paths directly
        }]
    )
    return response["message"]["content"]


# ── Tool execution ────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict, page: Page) -> str:
    try:
        if name == "navigate":
            page.goto(args["url"], wait_until="domcontentloaded", timeout=15000)
            return f"Navigated to {args['url']} — title: {page.title()}"

        elif name == "click":
            sel = args["selector"]
            page.click(sel, timeout=8000)
            page.wait_for_load_state("domcontentloaded", timeout=8000)
            return f"Clicked '{sel}'"

        elif name == "type_text":
            sel = args["selector"]
            text = args["text"]
            page.fill(sel, text)
            if args.get("submit", False):
                page.press(sel, "Enter")
                page.wait_for_load_state("domcontentloaded", timeout=8000)
            return f"Typed '{text}' into '{sel}'"

        elif name == "read_page":
            text = page.inner_text("body")[:5000]
            return f"Page content:\n{text}"

        elif name == "screenshot":
            filename = args.get("filename", "screenshot.png")
            page.screenshot(path=filename, full_page=True)
            return f"Screenshot saved to {filename}"

        elif name == "analyze_page_visually":
            tmp = "/tmp/vision_snapshot.png"
            page.screenshot(path=tmp, full_page=False)
            question = args.get("question", "Describe what you see on this page.")
            print(f"[Vision] Analyzing page screenshot with {VISION_MODEL}...")
            answer = vision_query(tmp, question)
            return f"Visual analysis:\n{answer}"

        elif name == "analyze_image_file":
            filename = args["filename"]
            question = args.get("question", "Describe what you see in this image.")
            print(f"[Vision] Analyzing {filename} with {VISION_MODEL}...")
            answer = vision_query(filename, question)
            return f"Visual analysis of {filename}:\n{answer}"

        elif name == "scroll":
            delta = 600 if args["direction"] == "down" else -600
            page.mouse.wheel(0, delta)
            return f"Scrolled {args['direction']}"

        elif name == "get_page_info":
            return f"URL: {page.url}\nTitle: {page.title()}"

        elif name == "go_back":
            page.go_back(wait_until="domcontentloaded", timeout=10000)
            return f"Went back — now at: {page.url}"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"Error executing {name}: {e}"


# ── Agent loop ────────────────────────────────────────────────────────────────
def run_agent(task: str, start_url: str = None):
    ensure_model(MODEL, label="Agent")
    print(f"\n[Agent] Model : {MODEL}")
    print(f"[Agent] Task  : {task}\n")

    messages = [
        {
            "role": "system",
            "content": (
                "You are a browser automation agent. Use the provided tools to complete the task. "
                "Call tools one at a time. When the task is complete, respond with a plain text summary "
                "of what you found or did — no JSON, no tool calls."
            )
        },
        {"role": "user", "content": task}
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        if start_url:
            print(f"[Browser] Opening {start_url}")
            page.goto(start_url, wait_until="domcontentloaded", timeout=15000)

        for step in range(1, MAX_STEPS + 1):
            print(f"[Step {step}] Asking {MODEL}...")

            response = ollama.chat(
                model=MODEL,
                messages=messages,
                tools=TOOLS,
            )

            msg = response["message"]
            messages.append(msg)

            # No tool calls — model is done
            if not msg.get("tool_calls"):
                print(f"\n[Done] {msg['content']}")
                browser.close()
                return msg["content"]

            # Execute each tool call
            for tool_call in msg["tool_calls"]:
                name = tool_call["function"]["name"]
                args = tool_call["function"]["arguments"]
                if isinstance(args, str):
                    args = json.loads(args)

                print(f"[Tool] {name}({json.dumps(args)})")
                result = execute_tool(name, args, page)
                print(f"[Result] {result[:200]}")

                messages.append({
                    "role": "tool",
                    "content": result,
                })

        print("[Agent] Max steps reached.")
        browser.close()
        return "Max steps reached without completing the task."


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    global MODEL, HEADLESS

    parser = argparse.ArgumentParser(description="Browser agent powered by qwen3:14b + Playwright")
    parser.add_argument("--task",     type=str, help="Task to perform")
    parser.add_argument("--url",      type=str, help="Starting URL (optional)")
    parser.add_argument("--image",    type=str, help="Image file to analyze directly (no browser needed)")
    parser.add_argument("--model",    type=str, default=MODEL, help=f"Ollama model (default: {MODEL})")
    parser.add_argument("--headless", action="store_true", help="Run browser without UI")
    args = parser.parse_args()

    MODEL    = args.model
    HEADLESS = args.headless

    # Direct image analysis mode — no browser needed
    if args.image:
        task = args.task or "Describe everything you see in this image in detail."
        print(f"[Vision] Analyzing {args.image}...")
        result = vision_query(args.image, task)
        print(f"\n[Result]\n{result}")
        return

    if args.task:
        run_agent(args.task, start_url=args.url)
    else:
        print(f"Qwen3 Playwright Agent — model: {MODEL}")
        print("Type 'quit' to exit.\n")
        while True:
            task = input("Task> ").strip()
            if task.lower() in ("quit", "exit", "q"):
                break
            if task:
                run_agent(task)


if __name__ == "__main__":
    main()
