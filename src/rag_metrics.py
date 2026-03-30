"""
RAG-Specific Evaluation Metrics
================================
Specialized LLM-as-Judge prompts for Retrieval-Augmented Generation evaluation.

Two metrics:
1. Faithfulness / Groundedness — Did the AI only use info from the provided context?
2. Answer Relevance — Did the AI actually answer the user's question?

These are displayed as SEPARATE metrics (not mixed into overall score)
because they only apply when context documents are provided.
"""

import re
from src.llm import generate_response
from src.utils import get_logger

logger = get_logger(__name__)


def evaluate_faithfulness(llm_output, context, model="phi3:mini"):
    """
    Check if the LLM output is grounded in the provided context.
    Detects hallucinated claims that aren't supported by the source material.

    Args:
        llm_output: The LLM's response text
        context: The retrieved documents / context provided to the LLM
        model: Ollama model name for the judge

    Returns:
        dict: {score: 0-10, verdict: "grounded"|"hallucinated", explanation: str}
    """
    judge_prompt = f"""You are a strict factual accuracy judge. Your job is to check if the Response contains ONLY information that can be found in the Context. Any claim, fact, or detail NOT present in the Context is a hallucination.

Context:
{context}

Response to evaluate:
{llm_output}

Scoring rules:
- 10: Every claim in the response is directly supported by the context
- 7-9: Mostly grounded, minor inferences that are reasonable
- 4-6: Some claims are not in the context but are related  
- 1-3: Multiple claims have no basis in the context
- 0: Response is completely unrelated to the context

You MUST respond with EXACTLY this format (3 lines, nothing else):
SCORE: [number 0-10]
VERDICT: [grounded or hallucinated]
EXPLANATION: [one sentence explaining why]"""

    try:
        response = generate_response(judge_prompt, model=model, temperature=0.1, max_tokens=100)
        return _parse_rag_judge_response(response, metric_name="faithfulness")
    except Exception as e:
        logger.error(f"Faithfulness evaluation error: {e}")
        return {"score": 5.0, "verdict": "unknown", "explanation": f"Evaluation failed: {e}"}


def evaluate_relevance(llm_output, question, model="phi3:mini"):
    """
    Check if the LLM output actually answers the user's question.
    A response might be factually correct but completely off-topic.

    Args:
        llm_output: The LLM's response text
        question: The original user question/prompt
        model: Ollama model name for the judge

    Returns:
        dict: {score: 0-10, verdict: "relevant"|"off-topic", explanation: str}
    """
    judge_prompt = f"""You are a relevance judge. Your job is to check if the Response directly answers the Question. A response that summarizes context without answering the question scores low.

Question:
{question}

Response to evaluate:
{llm_output}

Scoring rules:
- 10: Directly and completely answers the question
- 7-9: Answers the question but includes extra info or misses minor points
- 4-6: Partially answers the question, does not fully address it
- 1-3: Barely related to the question
- 0: Does not answer the question at all

You MUST respond with EXACTLY this format (3 lines, nothing else):
SCORE: [number 0-10]
VERDICT: [relevant or off-topic]
EXPLANATION: [one sentence explaining why]"""

    try:
        response = generate_response(judge_prompt, model=model, temperature=0.1, max_tokens=100)
        return _parse_rag_judge_response(response, metric_name="relevance")
    except Exception as e:
        logger.error(f"Relevance evaluation error: {e}")
        return {"score": 5.0, "verdict": "unknown", "explanation": f"Evaluation failed: {e}"}


def _parse_rag_judge_response(response_text, metric_name="metric"):
    """
    Parse the structured judge response into a result dict.
    Handles messy LLM output gracefully.
    """
    result = {"score": 5.0, "verdict": "unknown", "explanation": "Could not parse judge response"}

    try:
        text = response_text.strip()

        # Extract score
        score_match = re.search(r'SCORE:\s*(\d+\.?\d*)', text, re.IGNORECASE)
        if score_match:
            score = float(score_match.group(1))
            result["score"] = min(10.0, max(0.0, score))
        else:
            # Fallback: find any number in the response
            numbers = re.findall(r'\d+\.?\d*', text)
            if numbers:
                score = float(numbers[0])
                result["score"] = min(10.0, max(0.0, score))

        # Extract verdict
        verdict_match = re.search(r'VERDICT:\s*(\w[\w\s-]*)', text, re.IGNORECASE)
        if verdict_match:
            verdict = verdict_match.group(1).strip().lower()
            if metric_name == "faithfulness":
                result["verdict"] = "grounded" if "ground" in verdict else "hallucinated"
            else:
                result["verdict"] = "relevant" if "relev" in verdict else "off-topic"
        else:
            # Infer from score
            if result["score"] >= 6:
                result["verdict"] = "grounded" if metric_name == "faithfulness" else "relevant"
            else:
                result["verdict"] = "hallucinated" if metric_name == "faithfulness" else "off-topic"

        # Extract explanation
        explain_match = re.search(r'EXPLANATION:\s*(.+)', text, re.IGNORECASE)
        if explain_match:
            result["explanation"] = explain_match.group(1).strip()
        else:
            # Use the whole response as explanation if parsing fails
            result["explanation"] = text[:200] if text else "No explanation provided"

    except Exception as e:
        logger.error(f"Error parsing {metric_name} judge response: {e}")
        result["explanation"] = f"Parse error: {e}"

    return result


def evaluate_rag(llm_output, question, context, model="phi3:mini"):
    """
    Run both RAG metrics (faithfulness + relevance) and return combined results.

    Args:
        llm_output: The LLM's response text
        question: The original user question/prompt
        context: The retrieved documents / context
        model: Ollama model name

    Returns:
        dict: {
            faithfulness: {score, verdict, explanation},
            relevance: {score, verdict, explanation}
        }
    """
    faith = evaluate_faithfulness(llm_output, context, model=model)
    relev = evaluate_relevance(llm_output, question, model=model)
    return {
        "faithfulness": faith,
        "relevance": relev
    }
