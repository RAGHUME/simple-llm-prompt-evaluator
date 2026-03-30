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
    """Truncate text for PDF table cells."""
    if not text:
        return ""
    text = str(text).replace("\n", " ").replace("\r", "")
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text


def generate_pdf_report(results, model_name="Unknown", temperature=0.7):
    """
    Generate a PDF report from evaluation results.
    
    Args:
        results: List of dicts with keys: Prompt, Expected, LLM Output, Score, Similarity
        model_name: Name of the model used
        temperature: Temperature setting used
    
    Returns:
        bytes: The PDF file content as bytes
    """
    pdf = EvalReport()
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- Section 1: Configuration Summary ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Configuration", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Model: {model_name}    |    Temperature: {temperature}    |    Total Prompts: {len(results)}", new_x="LMARGIN", new_y="NEXT")
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
    pdf.cell(0, 6, f"Best Prompt (#{best_idx + 1}): {scores[best_idx]:.1f}/100 - {_safe_text(results[best_idx].get('Prompt', ''), 60)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Worst Prompt (#{worst_idx + 1}): {scores[worst_idx]:.1f}/100 - {_safe_text(results[worst_idx].get('Prompt', ''), 60)}", new_x="LMARGIN", new_y="NEXT")
    
    good = sum(1 for s in scores if s >= 80)
    ok = sum(1 for s in scores if 60 <= s < 80)
    poor = sum(1 for s in scores if s < 60)
    pdf.cell(0, 6, f"Scores: {good} Good (80+)  |  {ok} OK (60-79)  |  {poor} Poor (<60)", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Section 3: Score Chart ---
    if scores:
        chart_path = os.path.join(tempfile.gettempdir(), "eval_chart.png")
        _create_score_chart(scores, chart_path)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Score Distribution", new_x="LMARGIN", new_y="NEXT")
        pdf.image(chart_path, x=10, w=190)
        pdf.ln(4)
        # Clean up temp file
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
        # Check if we need a new page (leave space for content)
        if pdf.get_y() > 240:
            pdf.add_page()

        score = r.get("Score", 0)
        color = (46, 204, 113) if score >= 80 else (243, 156, 18) if score >= 60 else (231, 76, 60)

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*color)
        pdf.cell(0, 6, f"#{i+1}  Score: {score:.1f}/100", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"Prompt: {_safe_text(r.get('Prompt', ''), 100)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"Expected: {_safe_text(r.get('Expected', ''), 100)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 5, f"LLM Output: {_safe_text(r.get('LLM Output', ''), 100)}", new_x="LMARGIN", new_y="NEXT")

        sim = r.get("Similarity", None)
        judge = r.get("Judge", None)
        feedback = r.get("Feedback", "")
        extra = f"Similarity: {sim*100:.1f}%" if sim else ""
        if judge is not None:
            extra += f"  |  Judge: {judge}/10"
        if extra:
            pdf.cell(0, 5, extra, new_x="LMARGIN", new_y="NEXT")
        if feedback:
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(0, 5, f"Feedback: {_safe_text(feedback, 100)}", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

    # Return PDF as bytes (fpdf2 returns bytearray, FastAPI needs bytes)
    return bytes(pdf.output())
