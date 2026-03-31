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
- GET  /api/report/download     - Download PDF report from history
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, Response
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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.llm import get_available_models, generate_response, invalidate_model_cache
from src.evaluator import evaluate_response
from src.optimizer import optimize_prompt
from src.utils import init_db, save_to_db, get_history, clear_history, get_iterations, get_history_entry
from src.report import generate_pdf_report
from src.templates import PROMPT_TEMPLATES
from src.embeddings import preload_model
from src.assertions import ASSERTION_TYPES
from src.matrix import evaluate_matrix

# ── Database ──
DB_PATH = os.path.join(os.path.dirname(__file__), "db", "results.db")
init_db(DB_PATH)

# ── Thread pool for CPU-bound LLM/eval work ──
executor = ThreadPoolExecutor(max_workers=3)
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

class BatchEvaluateRequest(BaseModel):
    prompts: List[Dict[str, Any]]
    model: str = "phi3:mini"
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None

class CompareRequest(BaseModel):
    query: str = ""
    prompts: List[str]
    expected_output: str
    model: str = "phi3:mini"
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None

class MatrixRequest(BaseModel):
    prompts: List[str]
    models: List[str]
    expected_output: str = ""
    temperature: float = 0.7
    use_judge: bool = False
    assertions: Optional[List[Dict[str, str]]] = None
    context: Optional[str] = None

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

class EtaRequest(BaseModel):
    model: str = "phi3:mini"
    prompt_count: int = Field(default=1, ge=1, le=2000)
    use_judge: bool = False
    use_rag: bool = False
    operation: str = "evaluate"  # evaluate, compare, batch, matrix

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


def _evaluate_single(prompt_text, reference, model, temperature, use_judge, assertions=None, context=None):
    """Synchronous function: generate + evaluate a single prompt."""
    start = time.time()
    llm_output = generate_response(prompt_text, model=model, temperature=temperature)
    eval_result = evaluate_response(
        prompt=prompt_text,
        llm_output=llm_output,
        expected_output=reference,
        model=model,
        use_judge=use_judge,
        assertions=assertions,
        context=context
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
                request.context
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
    results = []
    total = len(request.prompts)

    for idx, item in enumerate(request.prompts):
        prompt = item.get('prompt', '')
        expected = item.get('expected_output', '')
        category = item.get('category', 'General')

        try:
            llm_output, eval_result, elapsed_ms = await run_in_thread(
                _evaluate_single,
                prompt, expected,
                request.model, request.temperature, request.use_judge,
                request.assertions, request.context
            )

            results.append({
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
            })
        except Exception as e:
            results.append({
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
            })

    return results


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
                request.context
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
    sec_per_prompt = _base_seconds_per_prompt(request.model)
    estimated_seconds = request.prompt_count * sec_per_prompt * op_multiplier * judge_multiplier * rag_multiplier

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
        results = []
        improvements_count = 0
        original_total_score = 0
        new_total_score = 0

        for idx, item in enumerate(request.items):
            orig_score = item.score
            original_total_score += orig_score

            # Only optimize if score < 70 (or 0.7 depending on scale)
            threshold = 70.0 if orig_score > 1.0 else 0.7
            if orig_score >= threshold:
                results.append({
                    "index": idx + 1,
                    "original_prompt": item.prompt,
                    "improved_prompt": item.prompt,
                    "original_score": orig_score,
                    "improved_score": orig_score,
                    "improvement_percent": 0.0,
                    "status": "passed",
                    "category": item.category,
                    "iterations": []
                })
                new_total_score += orig_score
                continue

            # Need optimization
            lineage_id = str(uuid.uuid4())
            # Save baseline (iteration 0)
            save_to_db(
                DB_PATH,
                prompt=item.prompt,
                expected_output=item.expected_output,
                llm_output="Baseline evaluation",
                model_name=request.model,
                score=orig_score * 100 if orig_score <= 1.0 else orig_score,
                lineage_id=lineage_id,
                iteration=0
            )

            def do_optimize():
                # optimize_prompt uses 0-100 scale for inputs internally
                norm_score = orig_score * 100 if orig_score <= 1.0 else orig_score
                return optimize_prompt(
                    original_prompt=item.prompt,
                    expected_output=item.expected_output,
                    original_score=norm_score,
                    model=request.model,
                    use_judge=request.use_judge,
                    max_retries=3,
                    db_path=DB_PATH,
                    lineage_id=lineage_id
                )

            improved, new_response, new_eval, did_improve, iterations = await run_in_thread(do_optimize)
            
            new_score = new_eval['overall_score']
            improvement = ((new_score - orig_score) / max(orig_score, 0.01)) * 100 if orig_score > 1.0 else ((new_score/100 - orig_score) / max(orig_score, 0.01)) * 100
            
            # Since new_eval['overall_score'] is 0-100, we need to map it back if original was 0-1
            final_new_score = new_score if orig_score > 1.0 else new_score / 100
            
            results.append({
                "index": idx + 1,
                "original_prompt": item.prompt,
                "improved_prompt": improved,
                "original_score": orig_score,
                "improved_score": final_new_score,
                "improvement_percent": round(improvement, 1),
                "status": "optimized" if did_improve else "failed_to_improve",
                "category": item.category,
                "iterations": iterations
            })
            new_total_score += final_new_score
            if did_improve:
                improvements_count += 1

        dataset_len = len(request.items) or 1
        return {
            "summary": {
                "total_prompts": dataset_len,
                "prompts_optimized": improvements_count,
                "original_avg_score": round(original_total_score / dataset_len, 2),
                "new_avg_score": round(new_total_score / dataset_len, 2)
            },
            "results": results
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
async def download_report():
    """Generate and download a PDF report from evaluation history."""
    try:
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
        pdf_bytes = generate_pdf_report(report_data, model_name=model_name)

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=eval_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"}
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Report generation failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
