"""
Team export bundle — ZIP with JSON, CSV (Excel-friendly), PNG chart, and PDF summary.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.report import generate_pdf_report, score_chart_png_bytes

CSV_COLUMNS = [
    "id",
    "index",
    "timestamp",
    "model_name",
    "category",
    "score",
    "semantic_similarity",
    "judge_score",
    "prompt",
    "expected_output",
    "llm_output",
    "feedback",
    "lineage_id",
    "iteration",
]


def _history_to_rows(history: List[dict]) -> Tuple[List[dict], List[dict]]:
    json_rows: List[dict] = []
    report_rows: List[dict] = []
    for h in history:
        json_rows.append(
            {
                "id": h.get("id"),
                "index": None,
                "timestamp": h.get("timestamp"),
                "model_name": h.get("model_name"),
                "category": None,
                "score": h.get("score") if h.get("score") is not None else 0,
                "semantic_similarity": h.get("semantic_similarity"),
                "judge_score": h.get("judge_score"),
                "prompt": h.get("prompt") or "",
                "expected_output": h.get("expected_output") or "",
                "llm_output": h.get("llm_output") or "",
                "feedback": h.get("feedback") or "",
                "lineage_id": h.get("lineage_id"),
                "iteration": h.get("iteration"),
            }
        )
        report_rows.append(
            {
                "Prompt": h.get("prompt") or "",
                "Expected": h.get("expected_output") or "",
                "LLM Output": h.get("llm_output") or "",
                "Score": h.get("score") if h.get("score") is not None else 0,
                "Similarity": h.get("semantic_similarity"),
                "Judge": h.get("judge_score"),
                "Feedback": h.get("feedback") or "",
            }
        )
    return json_rows, report_rows


def _client_items_to_rows(items: List[dict], model_name: str) -> Tuple[List[dict], List[dict]]:
    json_rows: List[dict] = []
    report_rows: List[dict] = []
    for raw in items:
        prompt = str(raw.get("prompt") or "")
        expected = str(raw.get("expected_output") or raw.get("expected") or "")
        llm_out = str(raw.get("llm_output") or "")
        score = raw.get("score")
        try:
            score_f = float(score) if score is not None else 0.0
        except (TypeError, ValueError):
            score_f = 0.0
        sim = raw.get("semantic_similarity")
        if sim is None:
            sim = raw.get("similarity")
        judge = raw.get("judge_score")
        feedback = str(raw.get("feedback") or "")
        category = raw.get("category")
        idx = raw.get("index")

        json_rows.append(
            {
                "id": None,
                "index": idx,
                "timestamp": None,
                "model_name": model_name,
                "category": category,
                "score": score_f,
                "semantic_similarity": sim,
                "judge_score": judge,
                "prompt": prompt,
                "expected_output": expected,
                "llm_output": llm_out,
                "feedback": feedback,
                "lineage_id": None,
                "iteration": None,
            }
        )
        report_rows.append(
            {
                "Prompt": prompt,
                "Expected": expected,
                "LLM Output": llm_out,
                "Score": score_f,
                "Similarity": sim,
                "Judge": judge,
                "Feedback": feedback,
            }
        )
    return json_rows, report_rows


def _csv_bytes(json_rows: List[dict]) -> bytes:
    sio = io.StringIO()
    w = csv.writer(sio)
    w.writerow(CSV_COLUMNS)
    for row in json_rows:
        w.writerow([row.get(c, "") for c in CSV_COLUMNS])
    return ("\ufeff" + sio.getvalue()).encode("utf-8")


def build_team_bundle_zip(
    json_rows: List[dict],
    report_rows: List[dict],
    model_name: str,
    *,
    source: str,
    title: Optional[str] = None,
) -> bytes:
    if not json_rows or not report_rows:
        raise ValueError("bundle requires at least one row")
    if len(json_rows) != len(report_rows):
        raise ValueError("json and report row counts must match")

    models_seen = sorted(
        {str(r.get("model_name")) for r in json_rows if r.get("model_name")}
    )
    scores = [float(r.get("score") or 0) for r in json_rows]
    chart_bytes = score_chart_png_bytes(scores)
    pdf_bytes = generate_pdf_report(report_rows, model_name=model_name, entry_id=None)

    manifest: Dict[str, Any] = {
        "export_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "LLM Prompt Evaluator",
        "source": source,
        "title": title or source,
        "row_count": len(json_rows),
        "primary_model": model_name,
        "models_seen": models_seen,
        "files": {
            "manifest.json": "Export metadata (this bundle format).",
            "evaluations.json": "Full evaluations: prompts, outputs, scores, metrics.",
            "evaluations.csv": "Same data as JSON; UTF-8 BOM for Microsoft Excel.",
            "scores_chart.png": "Bar chart of scores in row order.",
            "eval_summary.pdf": "Printable summary with statistics and per-row detail.",
        },
    }

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        zf.writestr("evaluations.json", json.dumps(json_rows, indent=2, default=str))
        zf.writestr("evaluations.csv", _csv_bytes(json_rows))
        if chart_bytes:
            zf.writestr("scores_chart.png", chart_bytes)
        zf.writestr("eval_summary.pdf", pdf_bytes)

    return out.getvalue()


def zip_from_history(history: List[dict], *, title: Optional[str] = None) -> bytes:
    json_rows, report_rows = _history_to_rows(history)
    model_name = (history[0].get("model_name") or "Unknown") if history else "Unknown"
    return build_team_bundle_zip(
        json_rows,
        report_rows,
        model_name,
        source="history",
        title=title,
    )


def zip_from_dataset_items(items: List[dict], model_name: str, *, title: Optional[str] = None) -> bytes:
    json_rows, report_rows = _client_items_to_rows(items, model_name)
    return build_team_bundle_zip(
        json_rows,
        report_rows,
        model_name,
        source="dataset_batch",
        title=title,
    )
