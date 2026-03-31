"""
LLM Prompt Evaluator - FastAPI Backend
=======================================
Complete REST API for evaluating, comparing, and optimizing LLM prompts.

API Endpoints:
- GET  /                        - Serve the UI
- GET  /api/health              - Health check + Ollama status
- GET  /api/models              - List available Ollama models
- POST /api/evaluate            - Evaluate prompt variant(s) — concurrent
- POST /api/evaluate/batch      - Batch evaluate from CSV dataset
- POST /api/evaluate/matrix     - Multi-model matrix evaluation
- POST /api/compare             - Compare multiple prompts
- POST /api/optimize            - Optimize a low-performing prompt
- GET  /api/history             - Get evaluation history
- POST /api/history/clear       - Clear evaluation history
- GET  /api/templates           - Get prompt templates
- GET  /api/assertion-types     - Get available assertion rule types
- GET  /api/report/download     - PDF from history (?entry_id= for single run; else up to 50 rows)
- GET  /api/export/bundle       - ZIP: JSON + CSV + PNG chart + PDF (from history)
- POST /api/export/bundle       - Same ZIP from client-supplied evaluation rows (e.g. dataset batch)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
import asyncio
import json
import os
import sys
import csv
import io
import time
import traceback
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict, deque
import threading

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.llm import get_available_models, generate_response, invalidate_model_cache
from src.evaluator import evaluate_response
from src.optimizer import optimize_prompt
from src.utils import init_db, save_to_db, get_history, clear_history, get_iterations, get_history_entry
from src.report import generate_pdf_report
from src.export_bundle import zip_from_history, zip_from_dataset_items
from src.templates import PROMPT_TEMPLATES
from src.embeddings import preload_model
from src.assertions import ASSERTION_TYPES
from src.matrix import evaluate_matrix

# ── Database ──
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "results.db")
init_db(DB_PATH)

# ── Thread pool for CPU-bound LLM/eval work (must be >= peak parallel batch/matrix/optimize) ──
MAX_BATCH_CONCURRENCY = int(os.environ.get("BATCH_MAX_CONCURRENCY", "6"))
MAX_MATRIX_CONCURRENCY = int(os.environ.get("MATRIX_MAX_CONCURRENCY", "4"))
MAX_OPTIMIZE_BATCH_CONCURRENCY = int(os.environ.get("OPTIMIZE_BATCH_CONCURRENCY", "2"))
_EXECUTOR_WORKERS = max(
    12,
    MAX_BATCH_CONCURRENCY + MAX_MATRIX_CONCURRENCY + MAX_OPTIMIZE_BATCH_CONCURRENCY + 4,
)
executor = ThreadPoolExecutor(max_workers=_EXECUTOR_WORKERS)
ETA_FALLBACK_SEC_PER_PROMPT = {
    "phi3:mini": 2.0,
    "phi3": 2.2,
    "llama3": 4.8,
    "mistral": 3.8,
    "mistral:7b": 4.0,
    "gemma:2b": 2.5,
    "gemma:7b": 4.6,
}
model_runtime_samples_ms = defaultdict(lambda: deque(maxlen=100))
job_store: Dict[str, Dict[str, Any]] = {}
job_lock = threading.Lock()

# ── Lifespan: preload models at startup ──
@asynccontextmanager
async def lifespan(app):
    """Preload heavy resources at startup so first request is fast."""
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, preload_model)
    yield  # App runs here
    # Shutdown cleanup (if needed) goes below yield


# ── FastAPI App ──
app = FastAPI(
    title="LLM Prompt Evaluator API",
    description="Evaluate, compare, and optimize LLM prompts",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets (CSS, JS)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# =====================
# Pydantic Models
# =====================

class PromptVariant(BaseModel):
    id: int
    text: str
    strategy: str = "zero-shot"

class EvaluateRequest(BaseModel):
    query: str
    reference_answer: Optional[str] = None
    prompt_variants: List[PromptVariant]
    model: str = "phi3:mini"
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2048)
    fast_mode: bool = False

class BatchEvaluateRequest(BaseModel):
    prompts: List[Dict[str, Any]]
    model: str = "phi3:mini"
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2048)
    fast_mode: bool = False

class CompareRequest(BaseModel):
    query: str = ""
    prompts: List[str]
    expected_output: str
    model: str = "phi3:mini"
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2048)
    fast_mode: bool = False

class MatrixRequest(BaseModel):
    prompts: List[str]
    models: List[str]
    expected_output: str = ""
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2048)
    fast_mode: bool = False

class OptimizeRequest(BaseModel):
    original_prompt: str
    expected_output: str
    current_score: float
    model: str = "phi3:mini"
    use_judge: bool = False

class BatchOptimizeItem(BaseModel):
    prompt: str
    expected_output: str
    score: float
    category: str = "General"

class BatchOptimizeRequest(BaseModel):
    items: List[BatchOptimizeItem]
    model: str = "phi3:mini"
    use_judge: bool = False
    fast_mode: bool = False


class TeamBundlePost(BaseModel):
    """Body for POST /api/export/bundle — typically dataset batch rows from the UI."""

    items: List[Dict[str, Any]]
    model_name: str = "phi3:mini"
    title: Optional[str] = None

class EtaRequest(BaseModel):
    model: str = "phi3:mini"
    prompt_count: int = Field(default=1, ge=1, le=2000)
    use_judge: bool = False
    use_rag: bool = False
    operation: str = "evaluate"  # evaluate, compare, batch, matrix
    fast_mode: bool = False
    max_tokens: Optional[int] = Field(default=None, ge=32, le=2048)

class HistoryEntry(BaseModel):
    id: int = 0
    prompt: str
    expected_output: Optional[str] = None
    llm_output: str
    model_name: str
    score: float
    judge_score: Optional[float] = None
    semantic_similarity: Optional[float] = None
    feedback: Optional[str] = None
    timestamp: str = ""


# =====================
# Helper: run sync function in thread pool
# =====================

async def run_in_thread(fn, *args):
    """Run a blocking function in a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, fn, *args)

def _record_model_runtime(model: str, elapsed_ms: float):
    """Store recent runtime samples to improve ETA accuracy over time."""
    if not model or elapsed_ms <= 0:
        return
    model_runtime_samples_ms[model].append(float(elapsed_ms))

def _base_seconds_per_prompt(model: str) -> float:
    samples = model_runtime_samples_ms.get(model)
    if samples and len(samples) > 0:
        avg_ms = sum(samples) / len(samples)
        # Clamp to avoid unstable spikes from one bad run.
        return max(0.5, min(avg_ms / 1000.0, 60.0))
    return ETA_FALLBACK_SEC_PER_PROMPT.get(model, 3.0)

def _create_job(job_type: str) -> str:
    job_id = str(uuid.uuid4())
    with job_lock:
        job_store[job_id] = {
            "id": job_id,
            "type": job_type,
            "status": "running",
            "events": [],
            "result": None,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
    return job_id

def _append_job_event(job_id: str, payload: Dict[str, Any]):
    with job_lock:
        job = job_store.get(job_id)
        if not job:
            return
        job["events"].append(payload)
        job["updated_at"] = time.time()

def _finish_job(job_id: str, result: Any):
    with job_lock:
        job = job_store.get(job_id)
        if not job:
            return
        job["status"] = "completed"
        job["result"] = result
        job["updated_at"] = time.time()

def _fail_job(job_id: str, error_msg: str):
    with job_lock:
        job = job_store.get(job_id)
        if not job:
            return
        job["status"] = "failed"
        job["error"] = error_msg
        job["updated_at"] = time.time()


def _evaluate_single(
    prompt_text,
    reference,
    model,
    temperature,
    use_judge,
    assertions=None,
    context=None,
    max_tokens=None,
    fast_mode=False
):
    """Synchronous function: generate + evaluate a single prompt."""
    start = time.time()
    effective_use_judge = bool(use_judge and not fast_mode)
    effective_context = None if fast_mode else context
    effective_max_tokens = max_tokens if max_tokens is not None else (128 if fast_mode else None)
    effective_timeout = 45 if fast_mode else 120
    llm_output = generate_response(
        prompt_text,
        model=model,
        temperature=temperature,
        max_tokens=effective_max_tokens,
        timeout=effective_timeout
    )
    eval_result = evaluate_response(
        prompt=prompt_text,
        llm_output=llm_output,
        expected_output=reference,
        model=model,
        use_judge=effective_use_judge,
        assertions=assertions,
        context=effective_context,
        lite_metrics=bool(fast_mode),
    )
    elapsed_ms = (time.time() - start) * 1000
    _record_model_runtime(model, elapsed_ms)
    return llm_output, eval_result, elapsed_ms


# =====================
# UI Serving
# =====================

@app.get("/")
async def root():
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "LLM Prompt Evaluator API", "docs": "/docs"}


# =====================
# API: Health
# =====================

@app.get("/api/health")
async def health_check():
    models = get_available_models()
    return {
        "status": "healthy",
        "ollama_connected": len(models) > 0,
        "available_models": models,
        "timestamp": datetime.now().isoformat()
    }


# =====================
# API: Models
# =====================

@app.get("/api/models")
async def list_models():
    invalidate_model_cache()
    models = get_available_models()
    model_meta = {
        "phi3:mini": {"speed_tag": "fast"},
        "phi3": {"speed_tag": "fast"},
        "llama3": {"speed_tag": "accurate"},
        "mistral": {"speed_tag": "accurate"},
        "mistral:7b": {"speed_tag": "accurate"},
        "gemma:2b": {"speed_tag": "fast"},
        "gemma:7b": {"speed_tag": "accurate"},
    }
    result = []
    for name in models:
        meta = model_meta.get(name, {})
        result.append({
            "name": name,
            "status": "active",
            "speed_tag": meta.get("speed_tag", "standard"),
        })
    return result


# =====================
# API: Templates
# =====================

@app.get("/api/templates")
async def get_templates():
    return PROMPT_TEMPLATES


# =====================
# API: Evaluate (single query, multiple prompt variants)
# =====================

@app.post("/api/evaluate")
async def evaluate(request: EvaluateRequest):
    if not request.prompt_variants:
        raise HTTPException(400, "At least one prompt variant is required.")

    # Run all variants concurrently (up to 3 in parallel)
    async def eval_variant(variant):
        try:
            full_prompt = f"{request.query}\n\n{variant.text}" if request.query else variant.text
            llm_output, eval_result, elapsed_ms = await run_in_thread(
                _evaluate_single,
                full_prompt,
                request.reference_answer,
                request.model,
                request.temperature,
                request.use_judge,
                request.assertions,
                request.context,
                request.max_tokens,
                request.fast_mode
            )

            overall = eval_result.get('overall_score', 0)

            # Hallucination detection
            hallucination = False
            sim = eval_result.get('semantic_similarity')
            if sim is not None and sim < 0.3:
                hallucination = True
            judge = eval_result.get('judge_score')
            if judge is not None and judge < 4:
                hallucination = True

            return {
                "variant_id": variant.id,
                "prompt_text": variant.text,
                "strategy": variant.strategy,
                "llm_output": llm_output,
                "scores": {
                    "bleu": round(eval_result.get('bleu', 0) or 0, 4),
                    "rouge1": round(eval_result.get('rouge1', 0) or 0, 4),
                    "rouge2": round(eval_result.get('rouge2', 0) or 0, 4),
                    "rougeL": round(eval_result.get('rougeL', 0) or 0, 4),
                    "semantic_similarity": round(sim or 0, 4),
                    "judge": round((judge or 0) / 10, 4) if judge else 0
                },
                "overall_score": round(overall, 2),
                "word_count": eval_result.get('word_count', 0),
                "feedback": eval_result.get('feedback', ''),
                "hallucination_detected": hallucination,
                "processing_time_ms": round(elapsed_ms, 1),
                "assertions": eval_result.get('assertions'),
                "rag": eval_result.get('rag')
            }
        except Exception as e:
            traceback.print_exc()
            return {
                "variant_id": variant.id,
                "prompt_text": variant.text,
                "strategy": variant.strategy,
                "llm_output": f"Error: {str(e)}",
                "scores": {"bleu":0,"rouge1":0,"rouge2":0,"rougeL":0,"semantic_similarity":0,"judge":0},
                "overall_score": 0,
                "word_count": 0,
                "feedback": f"Evaluation failed: {str(e)}",
                "hallucination_detected": False,
                "processing_time_ms": 0,
                "assertions": None,
                "rag": None
            }

    # Run all variants concurrently
    results = await asyncio.gather(*[eval_variant(v) for v in request.prompt_variants])
    results = list(results)

    # Sort by score descending
    results.sort(key=lambda x: x['overall_score'], reverse=True)
    return results


# =====================
# API: Batch Evaluate (dataset)
# =====================

@app.post("/api/evaluate/batch")
async def evaluate_batch(request: BatchEvaluateRequest):
    semaphore = asyncio.Semaphore(MAX_BATCH_CONCURRENCY)

    async def eval_item(idx, item):
        prompt = item.get('prompt', '')
        expected = item.get('expected_output', '')
        category = item.get('category', 'General')

        async with semaphore:
            try:
                llm_output, eval_result, elapsed_ms = await run_in_thread(
                    _evaluate_single,
                    prompt, expected,
                    request.model, request.temperature, request.use_judge,
                    request.assertions, request.context,
                    request.max_tokens, request.fast_mode
                )

                return {
                    "index": idx + 1,
                    "prompt": prompt[:200],
                    "expected": expected[:200],
                    "category": category,
                    "llm_output": llm_output[:300],
                    "score": round(eval_result['overall_score'], 2),
                    "bleu": round(eval_result.get('bleu', 0) or 0, 4),
                    "rouge1": round(eval_result.get('rouge1', 0) or 0, 4),
                    "similarity": round(eval_result.get('semantic_similarity', 0) or 0, 4),
                    "judge_score": eval_result.get('judge_score'),
                    "feedback": eval_result.get('feedback', ''),
                    "time_ms": round(elapsed_ms, 1)
                }
            except Exception as e:
                return {
                    "index": idx + 1,
                    "prompt": prompt[:200],
                    "expected": expected[:200],
                    "category": category,
                    "llm_output": f"Error: {e}",
                    "score": 0,
                    "bleu": 0, "rouge1": 0, "similarity": 0,
                    "judge_score": None,
                    "feedback": str(e),
                    "time_ms": 0
                }

    tasks = [eval_item(idx, item) for idx, item in enumerate(request.prompts)]
    results = await asyncio.gather(*tasks)
    return list(results)

def _run_batch_job(job_id: str, payload: Dict[str, Any]):
    prompts = payload.get("prompts", []) or []
    model = payload.get("model", "phi3:mini")
    temperature = payload.get("temperature", 0.7)
    use_judge = payload.get("use_judge", False)
    assertions = payload.get("assertions")
    context = payload.get("context")
    max_tokens = payload.get("max_tokens")
    fast_mode = payload.get("fast_mode", False)

    total = len(prompts)
    results = []
    start_time = time.time()
    _append_job_event(job_id, {"type": "started", "progress": 0, "message": f"Starting batch run ({total} prompts)"})

    try:
        def _eval_one(idx, item):
            prompt = item.get('prompt', '')
            expected = item.get('expected_output', '')
            category = item.get('category', 'General')
            step_start = time.time()
            try:
                llm_output, eval_result, elapsed_ms = _evaluate_single(
                    prompt, expected, model, temperature, use_judge, assertions, context, max_tokens, fast_mode
                )
                return idx, {
                    "index": idx + 1,
                    "prompt": prompt[:200],
                    "expected": expected[:200],
                    "category": category,
                    "llm_output": llm_output[:300],
                    "score": round(eval_result['overall_score'], 2),
                    "bleu": round(eval_result.get('bleu', 0) or 0, 4),
                    "rouge1": round(eval_result.get('rouge1', 0) or 0, 4),
                    "similarity": round(eval_result.get('semantic_similarity', 0) or 0, 4),
                    "judge_score": eval_result.get('judge_score'),
                    "feedback": eval_result.get('feedback', ''),
                    "time_ms": round(elapsed_ms, 1)
                }, round((time.time() - step_start) * 1000, 1)
            except Exception as e:
                return idx, {
                    "index": idx + 1,
                    "prompt": prompt[:200],
                    "expected": expected[:200],
                    "category": category,
                    "llm_output": f"Error: {e}",
                    "score": 0,
                    "bleu": 0, "rouge1": 0, "similarity": 0,
                    "judge_score": None,
                    "feedback": str(e),
                    "time_ms": 0
                }, round((time.time() - step_start) * 1000, 1)

        ordered_results: Dict[int, Dict[str, Any]] = {}
        completed = 0
        with ThreadPoolExecutor(max_workers=MAX_BATCH_CONCURRENCY) as pool:
            future_to_idx = {
                pool.submit(_eval_one, idx, item): idx
                for idx, item in enumerate(prompts)
            }
            from concurrent.futures import as_completed
            for future in as_completed(future_to_idx):
                idx, row, step_ms = future.result()
                ordered_results[idx] = row
                completed += 1
                progress = int((completed / max(total, 1)) * 100)
                _append_job_event(job_id, {
                    "type": "progress",
                    "progress": progress,
                    "completed": completed,
                    "total": total,
                    "step_ms": step_ms,
                    "message": f"Processed prompt {completed}/{total}"
                })

        results = [ordered_results[i] for i in range(total)]

        _append_job_event(job_id, {
            "type": "complete",
            "progress": 100,
            "total_time_ms": round((time.time() - start_time) * 1000, 1),
            "message": "Batch run complete"
        })
        _finish_job(job_id, results)
    except Exception as e:
        _append_job_event(job_id, {"type": "error", "message": str(e), "progress": 100})
        _fail_job(job_id, str(e))


# =====================
# API: Compare prompts
# =====================

@app.post("/api/compare")
async def compare_prompts(request: CompareRequest):
    if len(request.prompts) < 2:
        raise HTTPException(400, "Need at least 2 prompts to compare.")

    async def _eval_prompt(prompt):
        try:
            full_prompt = f"{request.query}\n\n{prompt}" if request.query else prompt
            llm_output, eval_result, elapsed_ms = await run_in_thread(
                _evaluate_single,
                full_prompt,
                request.expected_output,
                request.model,
                request.temperature,
                request.use_judge,
                request.assertions,
                request.context,
                request.max_tokens,
                request.fast_mode
            )

            return {
                "prompt": prompt,
                "llm_output": llm_output[:500],
                "score": round(eval_result['overall_score'], 2),
                "bleu": round(eval_result.get('bleu', 0) or 0, 4),
                "rouge1": round(eval_result.get('rouge1', 0) or 0, 4),
                "similarity": round(eval_result.get('semantic_similarity', 0) or 0, 4),
                "judge_score": eval_result.get('judge_score'),
                "feedback": eval_result.get('feedback', ''),
                "time_ms": round(elapsed_ms, 1)
            }
        except Exception as e:
            return {
                "prompt": prompt,
                "llm_output": f"Error: {e}",
                "score": 0, "bleu": 0, "rouge1": 0, "similarity": 0,
                "judge_score": None, "feedback": str(e), "time_ms": 0
            }

    # Run queries concurrently
    results = await asyncio.gather(*[_eval_prompt(p) for p in request.prompts])
    results = list(results)

    results.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(results):
        r['rank'] = i + 1

    return results


# =====================
# API: Multi-Model Matrix
# =====================

@app.post("/api/evaluate/matrix")
async def evaluate_matrix_endpoint(request: MatrixRequest):
    if len(request.prompts) == 0:
        raise HTTPException(400, "At least one prompt is required.")
    if len(request.models) == 0:
        raise HTTPException(400, "At least one model is required.")

    try:
        def do_matrix():
            return evaluate_matrix(
                prompts=request.prompts,
                models=request.models,
                expected_output=request.expected_output,
                temperature=request.temperature,
                use_judge=request.use_judge,
                assertions=request.assertions,
                context=request.context
            )

        result = await run_in_thread(do_matrix)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Matrix evaluation failed: {str(e)}")

def _run_matrix_job(job_id: str, payload: Dict[str, Any]):
    prompts = payload.get("prompts", []) or []
    models = payload.get("models", []) or []
    expected_output = payload.get("expected_output", "")
    temperature = payload.get("temperature", 0.7)
    use_judge = payload.get("use_judge", False)
    assertions = payload.get("assertions")
    context = payload.get("context")
    max_tokens = payload.get("max_tokens")
    fast_mode = payload.get("fast_mode", False)

    total = len(prompts) * len(models)
    completed = 0
    start_time = time.time()
    _append_job_event(job_id, {"type": "started", "progress": 0, "message": f"Starting matrix run ({total} cells)"})

    try:
        results_map: Dict[tuple, Dict[str, Any]] = {}
        tasks = []
        for p_idx, prompt in enumerate(prompts):
            for model in models:
                tasks.append((p_idx, prompt, model))

        with ThreadPoolExecutor(max_workers=MAX_MATRIX_CONCURRENCY) as pool:
            future_to_key = {}
            for p_idx, prompt, model in tasks:
                future = pool.submit(
                    _evaluate_single,
                    prompt, expected_output, model, temperature, use_judge, assertions, context,
                    max_tokens, fast_mode
                )
                future_to_key[future] = (p_idx, prompt, model)

            from concurrent.futures import as_completed
            for future in as_completed(future_to_key):
                p_idx, prompt, model = future_to_key[future]
                try:
                    llm_output, eval_result, elapsed_ms = future.result()
                    sim = eval_result.get('semantic_similarity')
                    judge = eval_result.get('judge_score')
                    cell = {
                        "model": model,
                        "llm_output": llm_output[:500],
                        "score": round(eval_result.get("overall_score", 0), 2),
                        "scores": {
                            "semantic_similarity": round(sim or 0, 4),
                            "bleu": round(eval_result.get("bleu", 0) or 0, 4),
                            "rouge1": round(eval_result.get("rouge1", 0) or 0, 4),
                            "judge": round((judge or 0) / 10, 4) if judge else None,
                        },
                        "word_count": eval_result.get("word_count", 0),
                        "feedback": eval_result.get("feedback", ""),
                        "time_ms": round(elapsed_ms, 1),
                        "error": None,
                        "assertions": eval_result.get("assertions") or {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True},
                        "rag": eval_result.get("rag"),
                    }
                except Exception as e:
                    cell = {
                        "model": model,
                        "llm_output": f"Error: {str(e)}",
                        "score": 0,
                        "scores": {"semantic_similarity": 0, "bleu": 0, "rouge1": 0, "judge": None},
                        "word_count": 0,
                        "feedback": str(e),
                        "time_ms": 0,
                        "error": str(e),
                        "assertions": {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True},
                        "rag": None,
                    }

                results_map[(p_idx, model)] = cell
                completed += 1
                progress = int((completed / max(total, 1)) * 100)
                _append_job_event(job_id, {
                    "type": "progress",
                    "progress": progress,
                    "completed": completed,
                    "total": total,
                    "message": f"Processed {completed}/{total} matrix cells"
                })

        rows = []
        best_score = -1
        best_model = ""
        best_prompt_idx = 0
        for p_idx, prompt in enumerate(prompts):
            cells = []
            for model in models:
                cell = results_map.get((p_idx, model), {"model": model, "score": 0, "error": "Not evaluated"})
                cells.append(cell)
                if cell.get("score", 0) > best_score:
                    best_score = cell["score"]
                    best_model = model
                    best_prompt_idx = p_idx

            rows.append({"prompt": prompt[:200], "prompt_full": prompt, "cells": cells})

        result = {
            "rows": rows,
            "models": models,
            "summary": {
                "best_model": best_model,
                "best_prompt_index": best_prompt_idx,
                "best_score": round(best_score, 2),
                "total_evaluations": total,
                "total_time_ms": round((time.time() - start_time) * 1000, 1),
            }
        }
        _append_job_event(job_id, {"type": "complete", "progress": 100, "message": "Matrix run complete"})
        _finish_job(job_id, result)
    except Exception as e:
        _append_job_event(job_id, {"type": "error", "message": str(e), "progress": 100})
        _fail_job(job_id, str(e))

@app.post("/api/jobs/batch/start")
async def start_batch_job(request: BatchEvaluateRequest):
    job_id = _create_job("batch")
    thread = threading.Thread(target=_run_batch_job, args=(job_id, request.dict()), daemon=True)
    thread.start()
    return {"job_id": job_id, "type": "batch"}

@app.post("/api/jobs/matrix/start")
async def start_matrix_job(request: MatrixRequest):
    job_id = _create_job("matrix")
    thread = threading.Thread(target=_run_matrix_job, args=(job_id, request.dict()), daemon=True)
    thread.start()
    return {"job_id": job_id, "type": "matrix"}

@app.get("/api/jobs/{job_id}/result")
async def get_job_result(job_id: str):
    with job_lock:
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return {
            "id": job["id"],
            "type": job["type"],
            "status": job["status"],
            "error": job["error"],
            "result": job["result"],
        }

@app.get("/api/jobs/{job_id}/events")
async def stream_job_events(job_id: str):
    with job_lock:
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")

    async def event_generator():
        idx = 0
        idle_ticks = 0
        while True:
            payload = None
            status = "running"
            with job_lock:
                job = job_store.get(job_id)
                if not job:
                    payload = {"type": "error", "message": "Job not found"}
                    status = "failed"
                else:
                    status = job["status"]
                    if idx < len(job["events"]):
                        payload = job["events"][idx]
                        idx += 1

            if payload is not None:
                yield f"data: {json.dumps(payload)}\n\n"
                idle_ticks = 0
            else:
                idle_ticks += 1
                if idle_ticks % 20 == 0:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                if status in ("completed", "failed"):
                    break
                await asyncio.sleep(0.25)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# =====================
# API: Assertion Types (metadata for frontend dropdown)
# =====================

@app.get("/api/assertion-types")
async def get_assertion_types():
    return ASSERTION_TYPES

@app.post("/api/eta")
async def estimate_eta(request: EtaRequest):
    """
    Estimate analysis time for a pending run.
    Learns from recent runtime samples per model when available.
    """
    op = (request.operation or "evaluate").lower()
    op_multiplier = {
        "evaluate": 1.0,
        "compare": 1.0,
        "batch": 1.0,
        "matrix": 1.0,
    }.get(op, 1.0)
    judge_multiplier = 1.35 if request.use_judge else 1.0
    rag_multiplier = 1.2 if request.use_rag else 1.0
    token_multiplier = 1.0
    if request.max_tokens and request.max_tokens > 0:
        token_multiplier = max(0.5, min(request.max_tokens / 256.0, 4.0))
    if request.fast_mode:
        token_multiplier *= 0.65
    sec_per_prompt = _base_seconds_per_prompt(request.model)
    estimated_seconds = request.prompt_count * sec_per_prompt * op_multiplier * judge_multiplier * rag_multiplier * token_multiplier

    return {
        "operation": op,
        "model": request.model,
        "prompt_count": request.prompt_count,
        "estimated_seconds": round(estimated_seconds, 1),
        "estimated_ms": int(estimated_seconds * 1000),
        "seconds_per_prompt": round(sec_per_prompt, 2),
        "uses_runtime_samples": bool(model_runtime_samples_ms.get(request.model)),
        "factors": {
            "judge_multiplier": judge_multiplier,
            "rag_multiplier": rag_multiplier,
            "operation_multiplier": op_multiplier,
        }
    }


# =====================
# API: Optimize
# =====================

@app.post("/api/optimize")
async def optimize(request: OptimizeRequest):
    try:
        # Denormalize score if it comes in 0-1 format
        input_score = request.current_score
        if input_score <= 1.0:
            input_score = input_score * 100

        lineage_id = str(uuid.uuid4())
        
        # Save baseline to DB to start the lineage
        save_to_db(
            DB_PATH,
            prompt=request.original_prompt,
            expected_output=request.expected_output,
            llm_output="Baseline evaluation",
            model_name=request.model,
            score=input_score,
            lineage_id=lineage_id,
            iteration=0
        )

        def do_optimize():
            return optimize_prompt(
                original_prompt=request.original_prompt,
                expected_output=request.expected_output,
                original_score=input_score,
                model=request.model,
                use_judge=request.use_judge,
                max_retries=3,
                db_path=DB_PATH,
                lineage_id=lineage_id
            )

        improved, new_response, new_eval, did_improve, iterations = await run_in_thread(do_optimize)

        # Detect changes
        changes = []
        old_l = request.original_prompt.lower()
        new_l = improved.lower()
        if 'expert' in new_l and 'expert' not in old_l:
            changes.append("Added expert role definition")
        if any(x in new_l for x in ['step by step', 'walk through']) and not any(x in old_l for x in ['step by step', 'walk through']):
            changes.append("Added step-by-step structure")
        if any(x in new_l for x in ['under', 'less than', 'max', 'words']) and not any(x in old_l for x in ['under', 'less than', 'max', 'words']):
            changes.append("Added length constraints")
        if 'cover:' in new_l or 'include:' in new_l:
            changes.append("Added specific concepts to cover")
        if not changes:
            changes.append("Rewritten for clarity and specificity")

        new_score = new_eval['overall_score']
        orig_score = input_score
        improvement = ((new_score - orig_score) / max(orig_score, 0.01)) * 100

        return {
            "original_prompt": request.original_prompt,
            "improved_prompt": improved,
            "original_score": round(orig_score, 2),
            "improved_score": round(new_score, 2),
            "improvement_percent": round(improvement, 1),
            "changes_made": changes,
            "new_response": new_response[:500] if new_response else "",
            "did_improve": did_improve,
            "iterations": iterations,
            "new_evaluation": {
                "bleu": round(new_eval.get('bleu', 0) or 0, 4),
                "rouge1": round(new_eval.get('rouge1', 0) or 0, 4),
                "similarity": round(new_eval.get('semantic_similarity', 0) or 0, 4),
                "judge_score": new_eval.get('judge_score'),
                "feedback": new_eval.get('feedback', '')
            }
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Optimization failed: {str(e)}")

# =====================
# API: Optimize Batch
# =====================

@app.post("/api/optimize/batch")
async def optimize_batch(request: BatchOptimizeRequest):
    try:
        dataset_len = len(request.items) or 1
        fast_mode = request.fast_mode
        use_judge_eff = bool(request.use_judge and not fast_mode)
        max_retries = 1 if fast_mode else 3

        async def process_one(idx: int, item: BatchOptimizeItem):
            orig_score = item.score
            threshold = 70.0 if orig_score > 1.0 else 0.7
            if orig_score >= threshold:
                row = {
                    "index": idx + 1,
                    "original_prompt": item.prompt,
                    "improved_prompt": item.prompt,
                    "original_score": orig_score,
                    "improved_score": orig_score,
                    "improvement_percent": 0.0,
                    "status": "passed",
                    "category": item.category,
                    "iterations": [],
                }
                return row, orig_score, orig_score, False

            lineage_id = str(uuid.uuid4())
            save_to_db(
                DB_PATH,
                prompt=item.prompt,
                expected_output=item.expected_output,
                llm_output="Baseline evaluation",
                model_name=request.model,
                score=orig_score * 100 if orig_score <= 1.0 else orig_score,
                lineage_id=lineage_id,
                iteration=0,
            )

            def do_optimize():
                norm_score = orig_score * 100 if orig_score <= 1.0 else orig_score
                return optimize_prompt(
                    original_prompt=item.prompt,
                    expected_output=item.expected_output,
                    original_score=norm_score,
                    model=request.model,
                    use_judge=use_judge_eff,
                    max_retries=max_retries,
                    db_path=DB_PATH,
                    lineage_id=lineage_id,
                    fast_mode=fast_mode,
                )

            improved, _new_response, new_eval, did_improve, iterations = await run_in_thread(do_optimize)
            new_score = new_eval["overall_score"]
            improvement = (
                ((new_score - orig_score) / max(orig_score, 0.01)) * 100
                if orig_score > 1.0
                else ((new_score / 100 - orig_score) / max(orig_score, 0.01)) * 100
            )
            final_new_score = new_score if orig_score > 1.0 else new_score / 100

            row = {
                "index": idx + 1,
                "original_prompt": item.prompt,
                "improved_prompt": improved,
                "original_score": orig_score,
                "improved_score": final_new_score,
                "improvement_percent": round(improvement, 1),
                "status": "optimized" if did_improve else "failed_to_improve",
                "category": item.category,
                "iterations": iterations,
            }
            return row, orig_score, final_new_score, bool(did_improve)

        sem = asyncio.Semaphore(MAX_OPTIMIZE_BATCH_CONCURRENCY)

        async def bounded(idx: int, item: BatchOptimizeItem):
            async with sem:
                return await process_one(idx, item)

        ordered = await asyncio.gather(
            *[bounded(i, it) for i, it in enumerate(request.items)]
        )

        results = []
        original_total_score = 0.0
        new_total_score = 0.0
        improvements_count = 0
        for row, orig_s, new_s, imp in ordered:
            results.append(row)
            original_total_score += orig_s
            new_total_score += new_s
            if imp:
                improvements_count += 1

        return {
            "summary": {
                "total_prompts": dataset_len,
                "prompts_optimized": improvements_count,
                "original_avg_score": round(original_total_score / dataset_len, 2),
                "new_avg_score": round(new_total_score / dataset_len, 2),
            },
            "results": results,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Batch optimization failed: {str(e)}")


# =====================
# API: History
# =====================

@app.get("/api/history")
async def get_evaluation_history(limit: int = 200):
    history = get_history(DB_PATH, limit=limit)
    return history


@app.get("/api/history/{entry_id}")
async def get_history_detail(entry_id: int):
    """Retrieve a single history entry by ID with full details."""
    entry = get_history_entry(DB_PATH, entry_id)
    if entry is None:
        raise HTTPException(404, f"History entry #{entry_id} not found")
    return entry


@app.post("/api/history/save")
async def save_to_history(entry: HistoryEntry):
    try:
        save_to_db(
            DB_PATH,
            prompt=entry.prompt,
            expected_output=entry.expected_output or '',
            llm_output=entry.llm_output,
            model_name=entry.model_name,
            score=entry.score,
            judge_score=entry.judge_score,
            feedback=entry.feedback,
            semantic_similarity=entry.semantic_similarity
        )
        return {"status": "saved"}
    except Exception as e:
        raise HTTPException(500, f"Failed to save: {e}")


@app.post("/api/history/clear")
async def clear_history_endpoint():
    clear_history(DB_PATH)
    return {"status": "cleared"}

@app.get("/api/iterations")
async def api_get_iterations():
    """Retrieve all tracked iterations/lineages."""
    try:
        iterations = get_iterations(DB_PATH, limit=50)
        return {"iterations": iterations, "count": len(iterations)}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Failed to retrieve iterations: {str(e)}")


# =====================
# API: CSV Upload for batch
# =====================

@app.post("/api/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    """Parse an uploaded CSV and return structured prompt data."""
    try:
        content = await file.read()
        text = content.decode('utf-8-sig')  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))

        prompts = []
        for row in reader:
            # Support various column name formats
            prompt = row.get('prompt') or row.get('Prompt') or row.get('question') or row.get('Question') or ''
            expected = row.get('expected_output') or row.get('Expected') or row.get('answer') or row.get('Answer') or ''
            category = row.get('category') or row.get('Category') or 'General'

            if prompt.strip():
                prompts.append({
                    "prompt": prompt.strip(),
                    "expected_output": expected.strip(),
                    "category": category.strip()
                })

        return {"prompts": prompts, "count": len(prompts)}
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {str(e)}")


# =====================
# API: Report Download
# =====================

@app.get("/api/report/download")
async def download_report(entry_id: Optional[int] = None):
    """
    Generate and download a PDF report from evaluation history.
    Omit entry_id for a summary report (up to 50 recent runs).
    Pass entry_id to download a single-run PDF for that history row.
    """
    try:
        if entry_id is not None:
            row = get_history_entry(DB_PATH, entry_id)
            if not row:
                raise HTTPException(404, "History entry not found.")
            history = [row]
        else:
            history = get_history(DB_PATH, limit=50)
        if not history:
            raise HTTPException(404, "No evaluation history to generate report from.")

        report_data = []
        for h in history:
            report_data.append({
                "Prompt": h.get('prompt', ''),
                "Expected": h.get('expected_output', ''),
                "LLM Output": h.get('llm_output', ''),
                "Score": h.get('score', 0),
                "Similarity": h.get('semantic_similarity'),
                "Judge": h.get('judge_score'),
                "Feedback": h.get('feedback', '')
            })

        model_name = history[0].get('model_name', 'Unknown') if history else 'Unknown'
        pdf_bytes = generate_pdf_report(
            report_data,
            model_name=model_name,
            entry_id=entry_id if entry_id is not None else None,
        )

        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"eval_run_{entry_id}_{ts}.pdf" if entry_id is not None else f"eval_report_{ts}.pdf"
        # ASCII-only filename for broad browser / OS compatibility
        cd = f'attachment; filename="{filename}"'

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": cd,
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-store",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Report generation failed: {str(e)}")


# =====================
# API: Team export bundle (ZIP)
# =====================


def _zip_bundle_response(zip_bytes: bytes, label: str) -> Response:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"eval_team_bundle_{label}_{ts}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/export/bundle")
async def export_bundle_from_history(limit: int = Query(50, ge=1, le=500)):
    """ZIP with manifest.json, evaluations.json, evaluations.csv, scores_chart.png, eval_summary.pdf."""
    try:
        history = get_history(DB_PATH, limit=limit)
        if not history:
            raise HTTPException(404, "No evaluation history to export.")

        def run():
            return zip_from_history(history)

        zip_bytes = await run_in_thread(run)
        return _zip_bundle_response(zip_bytes, "history")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Export bundle failed: {str(e)}")


@app.post("/api/export/bundle")
async def export_bundle_from_body(body: TeamBundlePost):
    """Build the same ZIP from rows supplied by the client (e.g. last dataset batch)."""
    try:
        if not body.items:
            raise HTTPException(400, "items must include at least one row.")

        def run():
            return zip_from_dataset_items(body.items, body.model_name, title=body.title)

        zip_bytes = await run_in_thread(run)
        return _zip_bundle_response(zip_bytes, "dataset")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Export bundle failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    # Keep auto-reload OFF by default to avoid restarts during ngrok/public demos.
    reload_dev = os.environ.get("UVICORN_RELOAD", "0").lower() in {"1", "true", "yes"}
    uvicorn.run("main:app", host=host, port=port, reload=reload_dev)
