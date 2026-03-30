<div align="center">
  <h1>🚀 Simple LLM Prompt Evaluator (v3.0)</h1>
  <p><b>A high-performance, production-grade LLM evaluation framework.</b></p>
  
  ![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
  ![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-white.svg?style=for-the-badge&logo=ollama)
  ![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
</div>

<br/>

> **🔗 Live Demo:** Currently accessible via (https://unequilateral-upbraidingly-rena.ngrok-free.dev) (Deployed locally).

> **Stop guessing which prompt works best.** Connect locally to Ollama and systematically grade prompt engineering variations to scientifically determine which prompts produce the absolute best outputs.

This framework moves beyond basic "eye-test" checks by providing **LLM-as-a-Judge RAG heuristics**, deterministic **mathematical assertions**, semantic similarity vectorization, and **prompt optimization lineage tracking**.

---

## 🌟 Key Features

| Feature | Description |
|---------|-------------|
| ⚡ **Concurrent Prompt Engine** | Evaluate multiple prompt strategies simultaneously using non-blocking async Python processing. |
| 🛡️ **Assertion Rule Engine** | Enforce deterministic pass/fail rules: `Must contain`, `Regex match`, `Max/Min words`, `Valid JSON`. |
| 📊 **Multi-Model Matrix** | Test N-prompts × M-models in a multi-dimensional visual heatmap. |
| 📚 **RAG Metrics (Judge)** | True *Faithfulness* & *Answer Relevance* scoring using the LLM to grade its own logical output. |
| 🗃️ **Large-Scale CSV Batching** | Upload large `.csv` datasets to evaluate hundreds of prompts asynchronously. |
| 📈 **Self-Healing Iterations** | Automatically rewrite failing prompts, tracking the optimization history with Chart.js line graphs. |
| 📋 **PDF Reports** | Download professional, color-coded evaluation reports directly to your machine. |
| 🎨 **Premium UI/UX** | A custom-built, dark-first glassmorphism design system modeled after modern SaaS apps. |

---

## 🛠️ Prerequisites

Before running this project you need:

1. **Python 3.9+** — [Download Python](https://python.org/downloads)
2. **Ollama** — [Download Ollama](https://ollama.com/download)
3. **At least one Ollama model** — e.g., `phi3:mini`

---

## 🤖 Recommended Local Models

Because this project uses **LLM-as-a-Judge** to evaluate hallucinations and rewrite poor prompts automatically, performance relies heavily on how "smart" your local model is.

| Model | Weight | Best For | Start Command |
|-------|------|----------|---------------|
| **llama3** (or 3.1) | 8B | 🏆 **Best Overall.** Excellent at prompt generation, strictly following formatting bounds, and understanding nuanced references. Needs 8GB+ RAM. | `ollama pull llama3` |
| **phi3:mini** | 3.8B | 🏎️ **Fastest / Default.** Extremely fast inference for Batch/Matrix testing. Can run on almost any older hardware or laptop without dedicated GPUs. | `ollama pull phi3:mini` |
| **qwen2.5:7b** | 7B | ⭐ **Best Reasoner.** Currently dominating open-source charts for strictly following instructions and generating code (e.g. JSON/XML formats). | `ollama pull qwen2.5:7b` |
| **mistral** | 7B | ⚖️ **Reliable Middleman.** A resilient, uncensored fallback model if Llama3 is too slow on your hardware. | `ollama pull mistral` |

> 💡 **Pro Tip:** Use the **Matrix Tab** in this application to evaluate the exact same prompt across `phi3:mini`, `llama3`, and `qwen2.5` simultaneously. This allows you to mathematically *prove* which model handles your specific data best without guessing!

---

## 🚀 How to Run

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/simple-llm-prompt-evaluator.git
cd simple-llm-prompt-evaluator
```

### Step 2: Create a Virtual Environment (Recommended)

**Windows (PowerShell/CMD):**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** The first install may take a few minutes as `sentence-transformers` downloads the embedding model (~90MB). This only happens once.

### Step 4: Start Ollama

Open a **separate terminal** and run:

```bash
ollama serve
```

Then pull at least one model:

```bash
ollama pull phi3:mini
```

Other recommended models:
```bash
ollama pull llama3
ollama pull mistral
```

### Step 5: Start the Evaluator Server

```bash
python main.py
```

Or use uvicorn directly:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Windows shortcut:** Double-click `start.bat` — it checks everything and starts automatically.

### Step 6: Open the Dashboard

Open your browser and navigate to:

| URL | Purpose |
|-----|---------|
| **http://localhost:8000** | Dashboard UI |
| **http://localhost:8000/docs** | Interactive API Documentation (Swagger) |

---

## 📖 Feature Guide

### Evaluate Tab
- Write your question and an optional reference/expected answer
- Create multiple prompt variants with different strategies (Zero-Shot, Few-Shot, Chain-of-Thought, Role-Based)
- Toggle **RAG Mode** to provide context documents for faithfulness scoring
- Add **Assertion Rules** for pass/fail compliance checks
- Click **Evaluate →** to run all variants concurrently

### Iterations Tab
- View optimization lineage history with interactive Chart.js graphs
- Track how prompt scores improve across optimization attempts
- Each optimization run creates a lineage with baseline → v2 → v3 progression
- Data is populated automatically when you run **Improve worst** or **Optimize Failed Prompts**

### Compare Tab
- Paste multiple prompts (one per line) for direct side-by-side comparison
- Perfect for A/B testing minor linguistic tweaks

### Matrix Tab
- Enter prompts and select 2+ models to build a cross-model evaluation grid
- Visual heatmap shows which model handles which prompt best

### Dataset Mode
- Upload a CSV with `prompt` and `expected_output` columns
- Run batch evaluation and optimize failing prompts automatically
- Export results as CSV

### History Tab
- View all past evaluation runs with scores, similarity, and feedback
- Click **View** on any entry to see the full prompt analysis details
- Download PDF reports of your evaluation history

---

## 📁 Project Structure

```
simple-llm-prompt-evaluator/
├── main.py                 # FastAPI backend — all API endpoints
├── requirements.txt        # Python dependencies
├── start.bat               # Windows startup script
├── start.sh                # Linux/macOS startup script
│
├── src/                    # Backend modules
│   ├── llm.py              # Ollama API communication
│   ├── evaluator.py        # Core evaluation engine (similarity, length, judge)
│   ├── optimizer.py         # Prompt optimization with retry/rollback
│   ├── embeddings.py       # Sentence-transformers + LRU cache
│   ├── metrics.py          # BLEU, ROUGE-1/2/L calculations
│   ├── assertions.py       # Deterministic rule engine
│   ├── rag_metrics.py      # RAG faithfulness & relevance judges
│   ├── matrix.py           # Multi-model matrix evaluator
│   ├── report.py           # PDF report generator
│   ├── templates.py        # Prompt template library
│   └── utils.py            # DB operations, logging, CSV helpers
│
├── static/                 # Frontend
│   ├── index.html          # Main dashboard page
│   ├── css/style.css       # Design system (dark/light themes)
│   └── js/
│       ├── app.js          # Frontend application logic
│       └── chart.umd.js    # Chart.js (bundled for offline use)
│
├── db/                     # SQLite database (auto-created)
│   └── results.db          # Evaluation history & lineage data
│
└── data/                   # Sample CSV datasets for testing
    ├── prompts.csv
    ├── test_business_marketing.csv
    ├── test_math_logic.csv
    └── test_poor_prompts.csv
```

---

## 🏗️ Tech Stack & Architecture

- **Backend:** FastAPI (Python) running `asyncio` routines mapped to a `ThreadPoolExecutor` to handle concurrent LLM requests simultaneously.
- **ML Engine:** `sentence-transformers` (`all-MiniLM-L6-v2`) layered with an MD5-hashed LRU Dictionary cache to avoid redundant tensor calculations on identical text.
- **Frontend / UI:** Vanilla HTML5/CSS3 with completely native ES6 JavaScript. Custom-built "Glassmorphism" Design System. **No heavy abstraction frameworks (React/Vue).**
- **Database:** SQLite3 (`db/results.db`) managing relational tables to automatically track "Prompt Lineage" and historical data retention.
- **Visualizations:** Bundled offline `Chart.js` for self-healing lineage analytics.

---

## 🧗‍♂️ Challenges Faced & Engineering Solutions

Building a local-LLM interface comes with significant architectural roadblocks:

1. **The Concurrency Problem:** Originally, local Ollama heavily queued single-thread requests causing the UI to freeze. **Solution:** By converting blocking Python `requests` into a thread-pooled async/await ecosystem within FastAPI, the system can now hit the evaluator with 3-5 background requests at the exact same time without locking the browser.
2. **"Lazy" Model Grading:** When asking smaller local models (like `phi3:mini`) to act as a "Judge," they often defaulted to lazy `10/10` scores or completely hallucinated the required JSON schema response. **Solution:** We introduced deterministic *Assertion Rules* acting as a hard programmatic "bouncer" to strictly validate outputs (Regex, max-words, Substring matched) before they even reach the LLM Judge step.
3. **Compute Waste Penalty:** Running the `all-MiniLM-L6-v2` semantic similarity sentence-transformer repeatedly on the exact same text during intensive A/B testing was a massive waste of local CPU resources. **Solution:** Engineered a robust memory cache mapping MD5-hashed prompt strings to their saved vector equivalents, cutting subsequent semantic comparisons from `600ms` down to roughly `<2ms`.

---

## ⚖️ Pros & Cons of This Setup

### ✅ Pros (The Advantages)
*   **Absolute Privacy (100% Offline):** Zero telemetry. Your prompts and sensitive RAG contexts never leave your physical computer. There are absolutely no running API bills.
*   **Blazing Fast UI:** Moving away from heavy python-rendering frameworks (like Streamlit) to a native Async API/Vanilla JS approach resulted in sub-10 millisecond DOM updates. 
*   **Scientific Accountability:** Replaces subjective "I think this prompt is better" guesswork with cold, hard mathematical charts proving whether tweaking a specific word actually improved your model's accuracy.

### ❌ Cons (The Limitations)
*   **Hardware Bottleneck:** Because it is completely self-hosted, your evaluation speed is entirely dictated by your physical computer's RAM and GPU allowance.
*   **Single-Player Architecture:** Right now, this is designed entirely as a local developer tool, meaning there is no robust multi-user web authentication (JWT/OAuth) protecting the API if you choose to launch this publicly on the open cloud.

---

## 🔧 Troubleshooting

### "Cannot connect to Ollama"
```bash
# Make sure Ollama is running in a separate terminal:
ollama serve

# Verify it's working:
curl http://localhost:11434/api/tags
```

### "No models found"
```bash
# Pull at least one model:
ollama pull phi3:mini
```

### "ModuleNotFoundError: No module named 'fastapi'"
```bash
# Install all dependencies:
pip install -r requirements.txt

# If using a virtual environment, make sure it's activated:
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate
```

### "sentence-transformers is slow to load"
The first run downloads the embedding model (~90MB). Subsequent runs use the cached model and start in seconds. The model loads at startup via `preload_model()`.

### Port 8000 already in use
```bash
# Use a different port:
uvicorn main:app --port 8080
# Then open http://localhost:8080
```

---

## 📊 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Serve dashboard UI |
| `GET` | `/api/health` | Health check + Ollama status |
| `GET` | `/api/models` | List available Ollama models |
| `POST` | `/api/evaluate` | Evaluate prompt variants (concurrent) |
| `POST` | `/api/evaluate/batch` | Batch evaluate from CSV dataset |
| `POST` | `/api/evaluate/matrix` | Multi-model matrix evaluation |
| `POST` | `/api/compare` | Compare multiple prompts |
| `POST` | `/api/optimize` | Optimize a low-scoring prompt |
| `POST` | `/api/optimize/batch` | Batch optimize failed prompts |
| `GET` | `/api/history` | Get evaluation history |
| `GET` | `/api/history/{id}` | Get single history entry details |
| `POST` | `/api/history/clear` | Clear all history |
| `GET` | `/api/iterations` | Get optimization lineage data |
| `GET` | `/api/templates` | Get prompt templates |
| `GET` | `/api/assertion-types` | Get assertion rule types |
| `GET` | `/api/report/download` | Download PDF report |
| `POST` | `/api/upload-csv` | Upload CSV for batch mode |

---

## 📝 License

MIT License. Feel free to fork and modify for your own internal pipeline testing!
