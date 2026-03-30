"""
Advanced Evaluation Metrics
===========================
Calculates BLEU, ROUGE, and other NLP metrics for response evaluation.
"""

import re
from collections import Counter
from typing import List, Tuple, Optional
import math


def tokenize(text: str) -> List[str]:
    """Simple tokenization by splitting on non-alphanumeric"""
    return re.findall(r'\b\w+\b', text.lower())


def get_ngrams(tokens: List[str], n: int) -> List[Tuple[str, ...]]:
    """Generate n-grams from token list"""
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def calculate_bleu(reference: str, candidate: str, max_n: int = 4) -> float:
    """
    Calculate BLEU score between reference and candidate text.
    Returns score between 0 and 1.
    """
    ref_tokens = tokenize(reference)
    cand_tokens = tokenize(candidate)
    
    if len(cand_tokens) == 0:
        return 0.0
    
    # Brevity penalty
    bp = 1.0
    if len(cand_tokens) < len(ref_tokens):
        bp = math.exp(1 - len(ref_tokens) / len(cand_tokens))
    
    # Calculate precision for each n-gram order
    scores = []
    for n in range(1, min(max_n + 1, len(cand_tokens) + 1)):
        ref_ngrams = Counter(get_ngrams(ref_tokens, n))
        cand_ngrams = Counter(get_ngrams(cand_tokens, n))
        
        # Clip counts
        clipped = sum((cand_ngrams & ref_ngrams).values())
        total = sum(cand_ngrams.values())
        
        if total == 0:
            scores.append(0.0)
        else:
            scores.append(clipped / total)
    
    # Geometric mean of scores
    if any(s == 0 for s in scores):
        return 0.0
    
    geo_mean = math.exp(sum(math.log(s) for s in scores) / len(scores))
    return bp * geo_mean


def calculate_rouge_n(reference: str, candidate: str, n: int = 1) -> float:
    """
    Calculate ROUGE-N score (recall-oriented).
    Returns F1 score between 0 and 1.
    """
    ref_tokens = tokenize(reference)
    cand_tokens = tokenize(candidate)
    
    if len(ref_tokens) == 0 or len(cand_tokens) == 0:
        return 0.0
    
    ref_ngrams = set(get_ngrams(ref_tokens, n))
    cand_ngrams = set(get_ngrams(cand_tokens, n))
    
    if len(ref_ngrams) == 0:
        return 0.0
    
    overlap = len(ref_ngrams & cand_ngrams)
    
    # ROUGE recall
    recall = overlap / len(ref_ngrams)
    # ROUGE precision
    precision = overlap / len(cand_ngrams) if len(cand_ngrams) > 0 else 0
    # F1 score
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def calculate_rouge_l(reference: str, candidate: str) -> float:
    """
    Calculate ROUGE-L (Longest Common Subsequence) score.
    """
    ref_tokens = tokenize(reference)
    cand_tokens = tokenize(candidate)
    
    if len(ref_tokens) == 0 or len(cand_tokens) == 0:
        return 0.0
    
    # Calculate LCS length
    m, n = len(ref_tokens), len(cand_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i-1] == cand_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])
    
    lcs_length = dp[m][n]
    
    if lcs_length == 0:
        return 0.0
    
    recall = lcs_length / m
    precision = lcs_length / n
    
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def calculate_all_metrics(reference: str, candidate: str) -> dict:
    """
    Calculate all metrics at once.
    Returns dict with bleu, rouge1, rouge2, rougeL scores.
    """
    return {
        "bleu": calculate_bleu(reference, candidate),
        "rouge1": calculate_rouge_n(reference, candidate, n=1),
        "rouge2": calculate_rouge_n(reference, candidate, n=2),
        "rougeL": calculate_rouge_l(reference, candidate)
    }


# Simple tests
if __name__ == "__main__":
    ref = "The cat sat on the mat and looked outside"
    cand = "The cat sat on the mat"
    
    metrics = calculate_all_metrics(ref, cand)
    print(f"Reference: {ref}")
    print(f"Candidate: {cand}")
    print(f"BLEU: {metrics['bleu']:.3f}")
    print(f"ROUGE-1: {metrics['rouge1']:.3f}")
    print(f"ROUGE-2: {metrics['rouge2']:.3f}")
    print(f"ROUGE-L: {metrics['rougeL']:.3f}")
