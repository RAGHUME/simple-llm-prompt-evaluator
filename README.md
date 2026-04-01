<div align="center">
  <h1>🚀 Simple LLM Prompt Evaluator (v3.0)</h1>
  <p><b>A high-performance, production-grade LLM evaluation framework.</b></p>
  
  ![Python](https://img.shields.io/badge/Python-3.9+-blue.svg?style=for-the-badge&logo=python)
  ![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
  ![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-white.svg?style=for-the-badge&logo=ollama)
  ![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
</div>

<br/>
> **🔗 Demo Video:**https://drive.google.com/drive/u/1/folders/1zFV22sD0uPswTNsIVWLi4JWPNqO_FjfA.

> **🎥 Demo Videos:** [Google Drive Folder](https://drive.google.com/drive/u/1/folders/1zFV22sD0uPswTNsIVWLi4JWPNqO_FjfA)
>
> **🔗 Live Demo:** Currently accessible via (https://unequilateral-upbraidingly-rena.ngrok-free.dev) (Deployed locally).
> 
> **How to Access the Live Demo:**
> 1. Click the Ngrok Tunnel link above.
> 2. You will see a standard warning screen from Ngrok (this is normal for free tunnels).
> 3. Click the **"Visit Site"** button on that screen.
> 4. The application dashboard will load directly from my local machine! Feel free to run prompt evaluations to see it in action.
> 
> 🛑 **Note for Developer (How to fix `ERR_NGROK_8012` / `undefined://undefined`):**
> This almost always means the tunnel target is wrong or your app restarted. Use the "Stable ngrok runbook" below (`reload` must be OFF).

> **Stop guessing which prompt works best.** Connect locally to Ollama and systematically grade prompt engineering variations to scientifically determine which prompts produce the absolute best outputs.

This framework moves beyond basic "eye-test" checks by providing **LLM-as-a-Judge RAG heuristics**, deterministic **mathematical assertions**, semantic similarity vectorization, and **prompt optimization lineage tracking**.

---

## 🌟 Key Features

| Feature | Description |
|---------|-------------|
| ⚡ **Concurrent Prompt Engine** | Evaluate multiple prompt strategies simultaneously using non-blocking async Python processing. |
| 🧩 **Prompt Versioning + Diff Viewer** | See original vs optimized prompts side-by-side with highlighted added/removed words and score delta. |
| ⏱️ **Pre-Run Cost/Compute Estimator** | Shows estimated runtime, token usage, and fast-vs-accurate recommendation before running Evaluate/Compare/Matrix/Dataset. |
| 🛡️ **Assertion Rule Engine** | Enforce deterministic pass/fail rules: `Must contain`, `Regex match`, `Max/Min words`, `Valid JSON`. |
| 📊 **Multi-Model Matrix** | Test N-prompts × M-models in a multi-dimensional visual heatmap. |
| 📚 **RAG Metrics (Judge)** | True *Faithfulness* & *Answer Relevance* scoring using the LLM to grade its own logical output. |
| 🗃️ **Large-Scale CSV Batching** | Upload large `.csv` datasets to evaluate hundreds of prompts asynchronously. |
| 📈 **Self-Healing Iterations** | Automatically rewrite failing prompts, tracking the optimization history with Chart.js line graphs. |
| 📦 **Team Export Bundle** | One-click ZIP export with `JSON + Excel-ready CSV + score chart PNG + PDF summary` for sharing. |
| 📋 **PDF Reports (Single + Full)** | Download full history report or a single-run PDF directly from the History detail view. |
| 🚀 **Fast Mode** | Lower-latency mode with reduced token/time settings and fast-path evaluation options for quicker feedback loops. |
| 🎨 **Premium UI/UX** | A custom-built, dark-first glassmorphism design system modeled after modern SaaS apps. |

### 🔥 What’s New (Recent Updates)

1. **Prompt diff viewer (versioning):**
   - Word-level diff for optimized prompts
   - Score delta (`old → new`) visible in Optimize, Dataset, and Iterations flows
2. **Cost/compute estimator across pages:**
   - Live estimate for runtime + token count
   - Automatic fast-vs-accurate recommendation before runs
3. **Team export bundle:**
   - Export evaluations as one ZIP containing `manifest.json`, `evaluations.json`, `evaluations.csv`, `scores_chart.png`, and `eval_summary.pdf`
4. **Improved reports and downloads:**
   - Single-run PDF export from History row
   - Better CSV compatibility for Excel (UTF-8 BOM + robust quoting)
5. **Stable sharing workflow:**
   - `start-share.bat` for one-click API + ngrok
   - startup defaults tuned for non-reload stable public demos

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

## 🚀 How to Run (Simple)

If you only need one clear setup path, follow this exact checklist.

### 1) Clone

```bash
git clone https://github.com/RAGHUME/simple-llm-prompt-evaluator.git
cd simple-llm-prompt-evaluator
```

### 2) Create and activate virtual environment

**Windows**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

### 4) Start Ollama and pull a model (first time only)

In another terminal:

```bash
ollama serve
ollama pull phi3:mini
```

### 5) Start this project

**Best for beginners (Windows):**
```bash
start.bat
```

**Cross-platform manual start:**
```bash
python main.py
```

### 6) Open app

- UI: [http://localhost:8000](http://localhost:8000)
- API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🌍 Share Publicly with ngrok (Simple)

### Windows (one command)

```bash
start-share.bat
```

It starts API + ngrok and opens your public URL.

### Manual (all OS)

```bash
# Terminal A
ollama serve

# Terminal B (stable, no reload)
python main.py

# Terminal C
ngrok http 8000
```

Use the HTTPS URL shown by ngrok.

---

## ❗ If Link Is Not Opening

1. Check local API:
   ```bash
   curl http://127.0.0.1:8000/api/health
   ```
2. Restart ngrok:
   ```bash
   ngrok http 8000
   ```
3. Keep your PC awake and online.
4. Free ngrok may show a warning page first — click **Visit Site**.
5. Free ngrok URLs can change; update README link when that happens.

---

## Advanced Run Options (Optional)

### Dev mode with auto-reload (not for public demo)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Stable Linux/macOS script

```bash
chmod +x start.sh
./start.sh
```

---

## 📖 Feature Guide

### Evaluate Tab
- Write your question and an optional reference/expected answer
- Create multiple prompt variants with different strategies (Zero-Shot, Few-Shot, Chain-of-Thought, Role-Based)
- See pre-run runtime/token estimate and recommendation in the top bar
- Toggle **RAG Mode** to provide context documents for faithfulness scoring
- Add **Assertion Rules** for pass/fail compliance checks
- Click **Evaluate →** to run all variants concurrently

### Iterations Tab
- View optimization lineage history with interactive Chart.js graphs
- Track how prompt scores improve across optimization attempts
- Each optimization run creates a lineage with baseline → v2 → v3 progression
- Open **vs prev** to inspect prompt version diffs between iterations
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
- Open row-level prompt diffs (original vs optimized) with score gain
- Export results as CSV or Team Bundle ZIP

### History Tab
- View all past evaluation runs with scores, similarity, and feedback
- Click **View** on any entry to see the full prompt analysis details
- Download full-history PDF, or single-run PDF from the detail modal
- Export Team Bundle ZIP for sharing with others

---

## 📁 Project Structure

```
simple-llm-prompt-evaluator/
├── main.py                 # FastAPI backend — all API endpoints
├── requirements.txt        # Python dependencies
├── start.bat               # Windows startup script
├── start.sh                # Linux/macOS startup script
├── start-share.bat         # Windows one-click API + ngrok sharing
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

### ngrok URL opens warning page, not app
This is expected on free ngrok. Click **Visit Site** once, then it forwards to your app.

### ngrok URL not opening app (expired / 404 / `ERR_NGROK_8012`)
1. Ensure API is running locally: `http://127.0.0.1:8000/api/health`
2. Restart only ngrok: `ngrok http 8000`
3. Use stable mode (no `--reload`) while sharing publicly
4. Update README/demo link with the new tunnel URL (free URLs can rotate)

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

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'Add your feature'`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📝 License

MIT License. Feel free to fork and modify for your own internal pipeline testing!
