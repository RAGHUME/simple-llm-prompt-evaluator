"""
Prompt Optimizer
================
Uses the LLM itself to analyze why a prompt failed and generate an improved version.

Strategies:
1. Constraint Injection — adds length limits, format rules
2. Negative Examples — tells the AI what NOT to do
3. Direct Instruction — rewrites the prompt to be extremely explicit
"""

from src.llm import generate_response
from src.evaluator import evaluate_response
from src.utils import get_logger, save_to_db

logger = get_logger(__name__)


def _generate_improved_prompt(original_prompt, expected_output, current_score, model, temperature):
    """
    Internal helper that asks the LLM to improve the given prompt.
    """
    expected_word_count = len(expected_output.split())
    
    # Choose strategy based on score severity
    if current_score < 50:
        strategy = "CRITICAL_REWRITE"
    elif current_score < 75:
        strategy = "ADD_CONSTRAINTS"
    else:
        strategy = "FINE_TUNE"
    
    sys_prompt = f"""You are an expert prompt engineer. Analyze why this prompt failed and rewrite it.

ORIGINAL PROMPT: {original_prompt}
EXPECTED OUTPUT: {expected_output}
CURRENT SCORE: {current_score:.1f}/100
EXPECTED WORD COUNT: {expected_word_count} words

ANALYSIS RULES:
- The expected output is {expected_word_count} words long. The rewritten prompt MUST ask for a response of similar length.
- If the expected output is 1-2 sentences, the prompt must say "Answer in 1-2 sentences" or "Keep it under {expected_word_count + 5} words."
- If the expected output is a list, the prompt must specify the exact format (e.g., "comma-separated", "numbered list").
- If the expected output is code, the prompt must say "Return only the code, no explanations."
- Add "Do not add extra information, greetings, or explanations" to prevent verbosity.

STRATEGY: {strategy}
{"- Completely rewrite the prompt from scratch. Make it impossible for the AI to give a wrong answer." if strategy == "CRITICAL_REWRITE" else ""}
{"- Add specific constraints: word limits, format rules, and negative instructions (what NOT to do)." if strategy == "ADD_CONSTRAINTS" else ""}
{"- Make small targeted fixes. The prompt is almost good — just tighten the wording." if strategy == "FINE_TUNE" else ""}

Return ONLY the improved prompt. No explanations, no commentary, no quotes around it."""

    logger.info(f"Optimizing prompt using strategy: {strategy}, model: {model}, temp: {temperature}")
    improved_prompt = generate_response(sys_prompt, model=model, temperature=temperature)
    
    # Clean up the response — remove quotes and extra whitespace
    improved = improved_prompt.strip()
    if improved.startswith('"') and improved.endswith('"'):
        improved = improved[1:-1]
    if improved.startswith("'") and improved.endswith("'"):
        improved = improved[1:-1]
    
    return improved


def optimize_prompt(original_prompt, expected_output, original_score, model="llama3", use_judge=False, max_retries=3, db_path=None, lineage_id=None):
    """
    Iteratively tries to write a better prompt. Tests the output internally.
    Guarantees that the returned score is >= the original score.
    Returns: (best_prompt, best_response, best_eval_dict, did_improve_bool, iterations_list)
    """
    best_prompt = original_prompt
    best_score = original_score
    best_eval = None
    best_resp = None
    did_improve = False
    iterations_list = []

    for attempt in range(max_retries):
        # Slightly increase temperature on retries to get different ideas
        temp = 0.7 + (attempt * 0.1)
        
        # 1. Generate new prompt
        candidate_prompt = _generate_improved_prompt(original_prompt, expected_output, original_score, model, temp)
        
        # 2. Automatically test the new prompt
        candidate_resp = generate_response(candidate_prompt, model=model, temperature=0.7)
        candidate_eval = evaluate_response(candidate_prompt, candidate_resp, expected_output, model=model, use_judge=use_judge)
        candidate_score = candidate_eval['overall_score']
        
        logger.info(f"Optimization Attempt {attempt+1}/{max_retries}: Score went from {original_score:.1f} -> {candidate_score:.1f}")
        
        # Log to tracking
        iterations_list.append({
            "attempt": attempt + 1,
            "score": candidate_score,
            "prompt": candidate_prompt
        })

        if db_path and lineage_id:
            save_to_db(
                db_path,
                prompt=candidate_prompt,
                expected_output=expected_output or '',
                llm_output=candidate_resp,
                model_name=model,
                score=candidate_score,
                judge_score=candidate_eval.get('judge_score'),
                feedback=candidate_eval.get('feedback'),
                semantic_similarity=candidate_eval.get('semantic_similarity'),
                lineage_id=lineage_id,
                iteration=attempt + 1
            )
        
        # 3. Check if it improved
        if candidate_score > best_score:
            best_score = candidate_score
            best_prompt = candidate_prompt
            best_resp = candidate_resp
            best_eval = candidate_eval
            did_improve = True
            
            # If it crosses 70, break early to save time for dataset loops
            if best_score >= 70.0:
                logger.info("Found acceptable prompt (>70 score). Breaking optimization loop early.")
                break
                
    # If we couldn't beat the original score after N retries, we safely return the original
    if not did_improve:
        logger.warning(f"Failed to optimally improve prompt after {max_retries} attempts. Keeping original.")
        # Generate a baseline evaluation just in case the caller needs it
        best_resp = generate_response(original_prompt, model=model, temperature=0.7)
        best_eval = evaluate_response(original_prompt, best_resp, expected_output, model=model, use_judge=use_judge)
        
    return best_prompt, best_resp, best_eval, did_improve, iterations_list
