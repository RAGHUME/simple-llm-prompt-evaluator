"""
Evaluator Module
================
Evaluates LLM responses using three methods:
1. Semantic Similarity — do the meanings match?
2. Length Deviation Penalty — is the response too long/short?
3. LLM-as-Judge — does an AI think the answer is correct?

Also generates human-readable feedback explaining the scores.
"""

import re
from src.embeddings import calculate_semantic_similarity
from src.llm import generate_response
from src.utils import get_logger
from src.metrics import calculate_all_metrics
from src.assertions import run_all_assertions
from src.rag_metrics import evaluate_rag

logger = get_logger(__name__)


# =====================
# LLM-as-Judge
# =====================

def llm_judge(prompt, response, expected, model="llama3"):
    """
    Uses the LLM itself to judge the quality of a response.
    Returns a score from 0.0 to 10.0
    
    The LLM evaluates based on:
    - Correctness: Is the answer factually right?
    - Completeness: Does it cover what was asked?
    - Clarity: Is it clear and well-written?
    """
    judge_prompt = f"""You are an expert evaluator. Score the Model Answer compared to the Expected Answer.

Question: {prompt}
Expected Answer: {expected}
Model Answer: {response}

Score from 0 to 10 based on:
- Correctness (is the answer right?)
- Completeness (does it cover the key points?)
- Clarity (is it clear and concise?)

Return ONLY a single number between 0 and 10. Nothing else."""

    try:
        score_text = generate_response(judge_prompt, model=model, temperature=0.1, max_tokens=10)
        # Extract the first number found in the response
        numbers = re.findall(r'\d+\.?\d*', score_text.strip())
        if numbers:
            score = float(numbers[0])
            return min(10.0, max(0.0, score))  # Clamp to 0-10
        return 5.0  # Default if parsing fails
    except Exception as e:
        logger.error(f"LLM Judge error: {e}")
        return 5.0


# =====================
# Feedback Generator
# =====================

def generate_feedback(results, expected_output=None):
    """
    Generates a human-readable explanation of WHY the score is what it is.
    Looks at each component and builds a feedback string.
    """
    feedback_parts = []
    score = results.get("overall_score", 0)

    # Overall assessment
    if score >= 90:
        feedback_parts.append("Excellent match! The response closely aligns with expectations.")
    elif score >= 70:
        feedback_parts.append("Good response with room for improvement.")
    elif score >= 50:
        feedback_parts.append("Moderate match. Several areas need attention.")
    else:
        feedback_parts.append("Poor match. The response significantly deviates from expectations.")

    # Length feedback
    if expected_output:
        expected_words = len(expected_output.split())
        actual_words = results.get("word_count", 0)
        ratio = actual_words / max(expected_words, 1)

        if ratio > 5.0:
            feedback_parts.append(f"Way too verbose ({actual_words} words vs {expected_words} expected). The AI over-explained.")
        elif ratio > 2.5:
            feedback_parts.append(f"Too long ({actual_words} words vs {expected_words} expected). Add constraints to shorten the response.")
        elif ratio < 0.5:
            feedback_parts.append(f"Too short ({actual_words} words vs {expected_words} expected). The response may be incomplete.")
        else:
            feedback_parts.append(f"Length is acceptable ({actual_words} words vs {expected_words} expected).")

    # Similarity feedback
    sim = results.get("semantic_similarity")
    if sim is not None:
        if sim >= 0.9:
            feedback_parts.append("Meaning is nearly identical to the expected output.")
        elif sim >= 0.7:
            feedback_parts.append("Meaning is similar but some key details differ.")
        elif sim >= 0.5:
            feedback_parts.append("Partial meaning overlap. The response covers the topic but diverges from expectations.")
        else:
            feedback_parts.append("Low semantic match. The response may be about a different topic or uses very different wording.")

    # Judge feedback
    judge = results.get("judge_score")
    if judge is not None:
        if judge >= 8:
            feedback_parts.append(f"LLM Judge rated it {judge}/10 — Highly accurate and complete.")
        elif judge >= 6:
            feedback_parts.append(f"LLM Judge rated it {judge}/10 — Mostly correct with minor issues.")
        elif judge >= 4:
            feedback_parts.append(f"LLM Judge rated it {judge}/10 — Partially correct, missing key points.")
        else:
            feedback_parts.append(f"LLM Judge rated it {judge}/10 — Significant errors or irrelevant content.")

    return " | ".join(feedback_parts)


# =====================
# Main Evaluation
# =====================

def evaluate_response(prompt, llm_output, expected_output=None, model=None, use_judge=False, assertions=None, context=None):
    """
    Evaluate the LLM output using multiple metrics.
    
    Args:
        prompt: The original prompt
        llm_output: The LLM's response text
        expected_output: The ideal/expected response (optional)
        model: Model name for LLM Judge (optional)
        use_judge: Whether to use LLM-as-Judge scoring (slower but more accurate)
        assertions: List of assertion rule dicts (optional)
        context: RAG context documents for faithfulness/relevance (optional)
    
    Returns:
        Dictionary with all scores and feedback
    """
    results = {
        "word_count": len(llm_output.split()),
        "char_count": len(llm_output),
        "semantic_similarity": None,
        "judge_score": None,
        "bleu": None,
        "rouge1": None,
        "rouge2": None,
        "rougeL": None,
        "feedback": "",
        "overall_score": 0.0,
        "assertions": None,
        "rag": None
    }

    score_components = []
    weights = []

    # --- Metric 1: Semantic Similarity & BLEU/ROUGE ---
    if expected_output:
        similarity = calculate_semantic_similarity(llm_output, expected_output)
        results["semantic_similarity"] = similarity

        # Calculate BLEU and ROUGE metrics
        metrics = calculate_all_metrics(expected_output, llm_output)
        results["bleu"] = metrics["bleu"]
        results["rouge1"] = metrics["rouge1"]
        results["rouge2"] = metrics["rouge2"]
        results["rougeL"] = metrics["rougeL"]

        if use_judge:
            score_components.append(similarity * 100)
            weights.append(0.40)  # 40% weight when judge is on
        else:
            score_components.append(similarity * 100)
            weights.append(0.60)  # 60% weight when judge is off

    # --- Metric 2: Length Deviation Penalty ---
    if expected_output:
        expected_word_count = len(expected_output.split())
        actual_word_count = results["word_count"]
        ratio = max(actual_word_count, 1) / max(expected_word_count, 1)

        if 0.7 <= ratio <= 1.5:
            length_score = 100
        elif 0.5 <= ratio <= 2.5:
            length_score = 70
        elif ratio > 5.0:
            length_score = 10  # Heavy penalty for extreme verbosity
        else:
            length_score = 40

        score_components.append(length_score)
        weights.append(0.20)
    else:
        if results["word_count"] > 5:
            score_components.append(100)
        else:
            score_components.append(50)
        weights.append(0.20)

    # --- Metric 3: LLM-as-Judge (optional) ---
    if use_judge and expected_output and model:
        judge_score = llm_judge(prompt, llm_output, expected_output, model=model)
        results["judge_score"] = judge_score
        score_components.append(judge_score * 10)  # Convert 0-10 to 0-100
        weights.append(0.40)  # 40% weight

    # --- Calculate weighted overall score ---
    if score_components and weights:
        total_weight = sum(weights)
        weighted_sum = sum(s * w for s, w in zip(score_components, weights))
        results["overall_score"] = float(weighted_sum / total_weight)
    else:
        results["overall_score"] = 0.0

    # --- Generate feedback ---
    results["feedback"] = generate_feedback(results, expected_output)

    # --- Assertion checks (deterministic, no LLM call) ---
    if assertions:
        results["assertions"] = run_all_assertions(assertions, llm_output)

    # --- RAG metrics (separate, not in overall score) ---
    if context and context.strip() and model:
        results["rag"] = evaluate_rag(llm_output, prompt, context, model=model)

    return results
