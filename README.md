# 🚀 LLM Prompt Evaluator (v3.0)

A high-performance, production-grade LLM evaluation framework. Connect locally to Ollama and systematically grade prompt engineering variations to scientifically determine which prompts produce the best outputs.

This framework moves beyond basic "eye-test" checks by providing LLM-as-a-Judge RAG heuristics, deterministic mathematical assertions, semantic comparisons, and prompt optimization lineage tracking.

---

## 🌟 Key Features

| Feature | Description |
|---------|-------------|
| ⚡ **Concurrent Prompt Engine** | Evaluate multiple prompt strategies simultaneously using async processing |
| 🛡️ **Assertion Rule Testing** | Deterministic pass/fail rules: `Must contain`, `Regex match`, `Max words`, `Valid JSON` |
| 📊 **Multi-Model Matrix Grid** | Test N-prompts × M-models in a visual heatmap grid |
| 📚 **RAG Metrics** | Faithfulness & Answer Relevance scoring via LLM-as-Judge |
| 🗃️ **CSV Dataset Mode** | Upload `.csv` files for batch evaluation of hundreds of prompts |
| 📈 **Iteration / Lineage Tracking** | Track optimization history with Chart.js visualizations |
| 🔄 **Auto-Optimization** | Automatically rewrite low-scoring prompts using LLM feedback |
| 📋 **PDF Reports** | Download professional evaluation reports |
| 🎨 **Premium Dashboard** | Dark-first glassmorphism UI with light mode toggle |

---

## 🛠️ Prerequisites

Before running this project you need:

1. **Python 3.9+** — [Download Python](https://python.org/downloads)
2. **Ollama** — [Download Ollama](https://ollama.com/download)
3. **At least one Ollama model** — e.g., `phi3:mini`, `llama3`, `mistral`

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

## 🏗️ Architecture

- **Backend:** FastAPI (Python) with `asyncio` + `ThreadPoolExecutor` for concurrent LLM calls
- **ML Engine:** `sentence-transformers` (all-MiniLM-L6-v2) with MD5-hashed LRU cache
- **Frontend:** Vanilla HTML5 + CSS3 + ES6 JavaScript — no heavy frameworks, sub-10ms load
- **Database:** SQLite (`db/results.db`) for evaluation history and optimization lineage tracking
- **Charts:** Chart.js (bundled locally) for iteration/lineage visualization

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
