<div align="center">

# 🧠 Simple LLM Prompt Evaluator (v3.0)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?style=flat&logo=ollama)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**A high-performance, production-grade LLM evaluation and auto-optimization framework.**

Connect locally to an Ollama server and systematically grade prompt engineering variations to mathematically determine which prompts produce the absolute best outputs.

[Features](#-key-features) • [Installation](#-quickstart-guide) • [Recommended Models](#-recommended-local-models) • [Architecture](#-architecture)

</div>

---

> Stop relying on the "eye-test" to see if your AI prompts are working. This framework brings **deterministic assertions**, **RAG Faithfulness judges**, and **semantic baseline testing** to local, open-source models. 

## 🌟 Why is this unique?
Most prompt testing tools are simply chat-boxes. **This project is a scientific evaluation engine.** 
If a prompt fails to meet your expected output or violates strict length/format rules, the system doesn't just log it—**it automatically rewrites the prompt**, tests it again, and plots its learning curve on a lineage graph.

### ⚡ Highlight Features
*   **Concurrent Execution:** Test up to 3 prompts simultaneously using asynchronous multi-threading.
*   **LLM-as-a-Judge:** AI doesn't just grade itself blindly; the system instructs the model to critique its own hallucination rates.
*   **Assertion Rules Engines:** Set strict `Regex`, `Max Words`, and `JSON Format` pass/fail bounds. 
*   **Offline First:** Full ML semantic text similarity calculation (`sentence-transformers`) stored entirely in local memory with LRU caching. No external API keys required!
*   **PDF Generation:** Instantly export A/B test reports to share with stakeholders.

---

## 🛠️ Quickstart Guide

### Prerequisites
1. **Python 3.9+** — [Download Here](https://python.org/downloads)
2. **Ollama Engine** — [Download Here](https://ollama.com/download)

### 1. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/RAGHUME/simple-llm-prompt-evaluator.git
cd simple-llm-prompt-evaluator

# Create and activate a Virtual Environment
python -m venv venv
venv\Scripts\activate   # (On Mac/Linux: source venv/bin/activate)

# Install required packages
pip install -r requirements.txt
```

### 2. Start Local AI
Open a **new terminal tab** and launch your Ollama engine, then pull down a small model:
```bash
ollama serve
ollama pull phi3:mini
```

### 3. Launch the Server
Go back to your original terminal and start the web framework:
```bash
# Windows users can simply double-click start.bat!
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
You can now access your dashboard at **http://localhost:8000**!

---

## 🤖 Recommended Local Models

Because this project uses the LLM to grade itself and rewrite prompts, performance relies heavily on how "smart" your local model is.

| Model | Size | Hardware | Best For | Start Command |
|-------|------|----------|----------|---------------|
| **llama3** | 8B | 8GB+ RAM | **Best Overall.** Understands nuanced formatting bounds perfectly. | `ollama pull llama3` |
| **qwen2.5:7b** | 7B | 8GB+ RAM | **Best Reasoner.** Dominates at strictly generating raw code/JSON. | `ollama pull qwen2.5:7b` |
| **phi3:mini**| 3.8B| 4GB+ RAM | **Fastest / Default.** Can run on any older hardware extremely fast. | `ollama pull phi3:mini` |

> 💡 **Pro Tip:** Use the *Matrix Tab* in the application to test the exact same prompt across all three of these models simultaneously to see which one perfectly handles your specific use-case!

---

## 🏗️ Architecture Stack

This project is built for speed, migrating away from slow synchronous Python frameworks into modern web paradigms.

- **Backend:** `FastAPI` (Python) over `uvicorn[standard]`
- **ML Engine:** `sentence-transformers/all-MiniLM-L6-v2` with Custom MD5 Hashing 
- **Frontend Controller:** Vanilla HTML5 + CSS3 + ES6 JavaScript (Sub-10ms DOM updates)
- **Database Tracking:** Persistent `SQLite3` instance for tracking optimization iteration lineage.

---

<details>
<summary><strong>🔧 Click to view Troubleshooting FAQ</strong></summary>

**Error: Cannot connect to Ollama**
Make sure Ollama is actually running in a separate terminal via `ollama serve`. 

**Error: Port 8000 already in use**
If you have another web server running, start the application on a new port:
`uvicorn main:app --port 8080 --reload`

**It's running slow the very first time!**
The very first time you click "Evaluate", `sentence-transformers` automatically downloads a ~90MB ML model to your cache. This only happens once. Subsequent runs take seconds.
</details>

---
<div align="center">
<i>Built with passion for prompt engineering. MIT License.</i>
</div>
