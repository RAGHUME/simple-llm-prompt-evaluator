"""
Multi-Model Matrix Evaluator
=============================
Evaluates prompts across multiple models simultaneously.
Produces a grid: rows=prompts, columns=models, cells=scores.
Uses concurrent evaluation with configurable worker limit.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.llm import generate_response
from src.evaluator import evaluate_response
from src.assertions import run_all_assertions
from src.rag_metrics import evaluate_rag
from src.utils import get_logger

logger = get_logger(__name__)

# Max parallel workers (Ollama can only handle ~2-3 concurrent requests efficiently)
MAX_WORKERS = 3


def _evaluate_cell(prompt, expected_output, model, temperature, use_judge, assertions=None, context=None):
    """
    Evaluate a single cell in the matrix (one prompt × one model).
    Returns all scores, assertion results, and RAG metrics.
    """
    start = time.time()

    try:
        # Generate LLM response
        llm_output = generate_response(prompt, model=model, temperature=temperature)

        # Run standard evaluation
        eval_result = evaluate_response(
            prompt=prompt,
            llm_output=llm_output,
            expected_output=expected_output,
            model=model,
            use_judge=use_judge
        )

        elapsed_ms = (time.time() - start) * 1000

        cell = {
            "model": model,
            "llm_output": llm_output[:500],
            "score": round(eval_result.get("overall_score", 0), 2),
            "scores": {
                "semantic_similarity": round(eval_result.get("semantic_similarity", 0) or 0, 4),
                "bleu": round(eval_result.get("bleu", 0) or 0, 4),
                "rouge1": round(eval_result.get("rouge1", 0) or 0, 4),
                "judge": round((eval_result.get("judge_score", 0) or 0) / 10, 4) if eval_result.get("judge_score") else None,
            },
            "word_count": eval_result.get("word_count", 0),
            "feedback": eval_result.get("feedback", ""),
            "time_ms": round(elapsed_ms, 1),
            "error": None
        }

        # Run assertions if provided
        if assertions:
            cell["assertions"] = run_all_assertions(assertions, llm_output)
        else:
            cell["assertions"] = {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True}

        # Run RAG metrics if context is provided
        if context and context.strip():
            cell["rag"] = evaluate_rag(llm_output, prompt, context, model=model)
        else:
            cell["rag"] = None

        return cell

    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        logger.error(f"Matrix cell error (model={model}): {e}")
        return {
            "model": model,
            "llm_output": f"Error: {str(e)}",
            "score": 0,
            "scores": {"semantic_similarity": 0, "bleu": 0, "rouge1": 0, "judge": None},
            "word_count": 0,
            "feedback": str(e),
            "time_ms": round(elapsed_ms, 1),
            "error": str(e),
            "assertions": {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True},
            "rag": None
        }


def evaluate_matrix(prompts, models, expected_output, temperature=0.7, use_judge=False, assertions=None, context=None):
    """
    Evaluate a matrix of prompts × models concurrently.

    Args:
        prompts: List of prompt strings
        models: List of model name strings
        expected_output: The expected/reference answer
        temperature: Sampling temperature
        use_judge: Whether to use LLM-as-Judge
        assertions: List of assertion dicts [{type, value}]
        context: RAG context documents (optional)

    Returns:
        dict: {
            rows: [{prompt, cells: [cell_per_model]}],
            summary: {best_model, best_prompt, total_time_ms}
        }
    """
    start_total = time.time()
    rows = []

    # Build all (prompt, model) pairs
    tasks = []
    for p_idx, prompt in enumerate(prompts):
        for model in models:
            tasks.append((p_idx, prompt, model))

    # Execute concurrently with limited workers
    results_map = {}  # (p_idx, model) -> cell result

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_key = {}
        for (p_idx, prompt, model) in tasks:
            future = pool.submit(
                _evaluate_cell,
                prompt, expected_output, model, temperature, use_judge, assertions, context
            )
            future_to_key[future] = (p_idx, model)

        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results_map[key] = future.result()
            except Exception as e:
                p_idx, model = key
                logger.error(f"Matrix future error: {e}")
                results_map[key] = {
                    "model": model, "llm_output": f"Error: {e}", "score": 0,
                    "scores": {}, "word_count": 0, "feedback": str(e),
                    "time_ms": 0, "error": str(e),
                    "assertions": {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True},
                    "rag": None
                }

    # Assemble into row-based structure
    best_score = -1
    best_model = ""
    best_prompt_idx = 0

    for p_idx, prompt in enumerate(prompts):
        cells = []
        for model in models:
            cell = results_map.get((p_idx, model), {"model": model, "score": 0, "error": "Not evaluated"})
            cells.append(cell)
            if cell["score"] > best_score:
                best_score = cell["score"]
                best_model = model
                best_prompt_idx = p_idx

        rows.append({
            "prompt": prompt[:200],
            "prompt_full": prompt,
            "cells": cells
        })

    total_time = (time.time() - start_total) * 1000

    return {
        "rows": rows,
        "models": models,
        "summary": {
            "best_model": best_model,
            "best_prompt_index": best_prompt_idx,
            "best_score": round(best_score, 2),
            "total_evaluations": len(tasks),
            "total_time_ms": round(total_time, 1)
        }
    }
