"""
PDF Report Generator
====================
Generates a professional PDF report of evaluation results.
Uses fpdf2 for PDF creation and matplotlib for score charts.
"""

import os
import tempfile
from datetime import datetime
from fpdf import FPDF
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
from src.utils import get_logger

logger = get_logger(__name__)


class EvalReport(FPDF):
    """Custom PDF class with header and footer."""

    def __init__(self, title="LLM Prompt Evaluator Report"):
        super().__init__()
        self.report_title = title

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, self.report_title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _create_score_chart(scores, filepath):
    """Creates a bar chart of scores and saves it as an image."""
    fig, ax = plt.subplots(figsize=(10, 4))
    colors = ['#2ecc71' if s >= 80 else '#f39c12' if s >= 60 else '#e74c3c' for s in scores]
    ax.bar(range(len(scores)), scores, color=colors)
    ax.set_xlabel("Prompt #")
    ax.set_ylabel("Score")
    ax.set_title("Evaluation Scores")
    ax.set_ylim(0, 105)
    ax.axhline(y=80, color='green', linestyle='--', alpha=0.5, label='Good (80+)')
    ax.axhline(y=60, color='orange', linestyle='--', alpha=0.5, label='OK (60+)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(filepath, dpi=150)
    plt.close(fig)


def _safe_text(text, max_len=80):
    """Truncate and sanitize text for PDF single-line cells (latin-1)."""
    if not text:
        return ""
    text = str(text).replace("\n", " ").replace("\r", "")
    text = text.encode("latin-1", "replace").decode("latin-1")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def _safe_text_multiline(text):
    """Full body text for multi_cell: keep newlines, latin-1 only."""
    if not text:
        return ""
    text = str(text).replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("latin-1", "replace").decode("latin-1")


def _pdf_write_block(pdf, label, body, content_width=190, line_height=5):
    """Write a labeled section with wrapped paragraphs (readable in PDF viewers)."""
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, line_height, label, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    txt = _safe_text_multiline(body)
    if txt.strip():
        pdf.multi_cell(
            content_width,
            line_height,
            txt,
            new_x="LMARGIN",
            new_y="NEXT",
        )
    else:
        pdf.cell(0, line_height, "(empty)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def generate_pdf_report(results, model_name="Unknown", temperature=0.7, entry_id=None):
    """
    Generate a PDF report from evaluation results.

    Args:
        results: List of dicts with keys: Prompt, Expected, LLM Output, Score, Similarity, Feedback, Judge
        model_name: Name of the model used
        temperature: Temperature setting used
        entry_id: If set and len(results)==1, shown in the header (history row id).

    Returns:
        bytes: The PDF file content as bytes
    """
    model_name = model_name.encode("latin-1", "replace").decode("latin-1")
    single = len(results) == 1
    report_title = "Single Evaluation Report" if single else "LLM Prompt Evaluator Report"
    pdf = EvalReport(title=report_title)
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- Section 1: Configuration Summary ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Configuration", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    head = f"Model: {model_name}    |    Temperature: {temperature}    |    Runs in report: {len(results)}"
    if single and entry_id is not None:
        head += f"    |    History ID: {entry_id}"
    pdf.cell(0, 6, head, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Section 2: Summary Statistics ---
    scores = [r.get("Score", 0) for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0
    best_idx = scores.index(max(scores)) if scores else 0
    worst_idx = scores.index(min(scores)) if scores else 0

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary Statistics", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Average Score: {avg_score:.1f}/100", new_x="LMARGIN", new_y="NEXT")
    if single:
        pdf.cell(
            0,
            6,
            f"Score: {scores[0]:.1f}/100",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    else:
        pdf.cell(
            0,
            6,
            f"Best Prompt (#{best_idx + 1}): {scores[best_idx]:.1f}/100 - {_safe_text(results[best_idx].get('Prompt', ''), 60)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.cell(
            0,
            6,
            f"Worst Prompt (#{worst_idx + 1}): {scores[worst_idx]:.1f}/100 - {_safe_text(results[worst_idx].get('Prompt', ''), 60)}",
            new_x="LMARGIN",
            new_y="NEXT",
        )

    good = sum(1 for s in scores if s >= 80)
    ok = sum(1 for s in scores if 60 <= s < 80)
    poor = sum(1 for s in scores if s < 60)
    pdf.cell(
        0,
        6,
        f"Scores: {good} Good (80+)  |  {ok} OK (60-79)  |  {poor} Poor (<60)",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(4)

    # --- Section 3: Score Chart ---
    if scores:
        fd, chart_path = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            _create_score_chart(scores, chart_path)
            if pdf.get_y() > 200:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Score Distribution", new_x="LMARGIN", new_y="NEXT")
            pdf.image(chart_path, x=10, w=190)
            pdf.ln(4)
        finally:
            try:
                os.remove(chart_path)
            except OSError:
                pass

    # --- Section 4: Detailed Results ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Detailed Results", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for i, r in enumerate(results):
        if pdf.get_y() > 255:
            pdf.add_page()

        score = r.get("Score", 0)
        color = (46, 204, 113) if score >= 80 else (243, 156, 18) if score >= 60 else (231, 76, 60)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*color)
        pdf.cell(0, 6, f"#{i + 1}  Score: {score:.1f}/100", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        _pdf_write_block(pdf, "Prompt:", r.get("Prompt", ""))
        _pdf_write_block(pdf, "Expected:", r.get("Expected", ""))
        _pdf_write_block(pdf, "LLM Output:", r.get("LLM Output", ""))

        sim = r.get("Similarity", None)
        judge = r.get("Judge", None)
        feedback = r.get("Feedback", "")
        parts = []
        if sim is not None:
            parts.append(f"Similarity: {float(sim) * 100:.1f}%")
        if judge is not None:
            parts.append(f"Judge: {judge}/10")
        if parts:
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 5, "  |  ".join(parts), new_x="LMARGIN", new_y="NEXT")
        if feedback:
            _pdf_write_block(pdf, "Feedback:", feedback)

        pdf.ln(3)

    out = pdf.output(dest="S")
    return bytes(out) if not isinstance(out, bytes) else out
