"""
Assertion Engine
================
Deterministic rule-based checks for LLM outputs.
No LLM calls — pure string/format validation.

Supported assertion types:
- contains: Output must contain a substring
- not_contains: Output must NOT contain a substring
- is_json: Output must be valid JSON
- regex: Output must match a regex pattern
- starts_with: Output must start with a prefix
- max_length: Output must be under N words
- min_length: Output must be at least N words
"""

import re
import json
from src.utils import get_logger

logger = get_logger(__name__)


def run_assertion(rule_type, rule_value, llm_output):
    """
    Run a single assertion against the LLM output.

    Args:
        rule_type: One of the supported assertion types
        rule_value: The value/parameter for the rule (e.g., the substring to check)
        llm_output: The LLM's response text

    Returns:
        dict: {rule_type, rule_value, passed: bool, detail: str}
    """
    output_lower = llm_output.lower().strip()
    value_lower = str(rule_value).lower().strip()

    result = {
        "rule_type": rule_type,
        "rule_value": str(rule_value),
        "passed": False,
        "detail": ""
    }

    try:
        if rule_type == "contains":
            found = value_lower in output_lower
            result["passed"] = found
            result["detail"] = f'Found "{rule_value}"' if found else f'"{rule_value}" not found in output'

        elif rule_type == "not_contains":
            absent = value_lower not in output_lower
            result["passed"] = absent
            result["detail"] = f'"{rule_value}" correctly absent' if absent else f'Found forbidden text "{rule_value}"'

        elif rule_type == "is_json":
            try:
                # Try to extract JSON from the output (may be wrapped in text)
                stripped = llm_output.strip()
                # Try raw parse first
                json.loads(stripped)
                result["passed"] = True
                result["detail"] = "Valid JSON"
            except json.JSONDecodeError:
                # Try to find JSON block in markdown code fences
                json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', stripped)
                if json_match:
                    try:
                        json.loads(json_match.group(1).strip())
                        result["passed"] = True
                        result["detail"] = "Valid JSON (inside code block)"
                    except json.JSONDecodeError:
                        result["passed"] = False
                        result["detail"] = "Invalid JSON structure"
                else:
                    result["passed"] = False
                    result["detail"] = "Output is not valid JSON"

        elif rule_type == "regex":
            try:
                match = re.search(str(rule_value), llm_output, re.IGNORECASE | re.MULTILINE)
                result["passed"] = match is not None
                result["detail"] = f"Pattern matched" if match else f"Pattern /{rule_value}/ not found"
            except re.error as e:
                result["passed"] = False
                result["detail"] = f"Invalid regex: {e}"

        elif rule_type == "starts_with":
            starts = output_lower.startswith(value_lower)
            result["passed"] = starts
            result["detail"] = f'Starts with "{rule_value}"' if starts else f'Does not start with "{rule_value}"'

        elif rule_type == "max_length":
            try:
                max_words = int(rule_value)
                word_count = len(llm_output.split())
                result["passed"] = word_count <= max_words
                result["detail"] = f"{word_count} words (max {max_words})" if result["passed"] else f"{word_count} words exceeds {max_words} word limit"
            except ValueError:
                result["passed"] = False
                result["detail"] = f"Invalid max_length value: {rule_value}"

        elif rule_type == "min_length":
            try:
                min_words = int(rule_value)
                word_count = len(llm_output.split())
                result["passed"] = word_count >= min_words
                result["detail"] = f"{word_count} words (min {min_words})" if result["passed"] else f"{word_count} words is below {min_words} word minimum"
            except ValueError:
                result["passed"] = False
                result["detail"] = f"Invalid min_length value: {rule_value}"

        else:
            result["detail"] = f"Unknown assertion type: {rule_type}"

    except Exception as e:
        logger.error(f"Assertion error ({rule_type}): {e}")
        result["detail"] = f"Assertion error: {str(e)}"

    return result


def run_all_assertions(assertions, llm_output):
    """
    Run a list of assertions against the LLM output.

    Args:
        assertions: List of dicts, each with 'type' and 'value' keys
        llm_output: The LLM's response text

    Returns:
        dict: {
            results: [list of individual assertion results],
            total: int,
            passed: int,
            failed: int,
            all_passed: bool
        }
    """
    if not assertions:
        return {"results": [], "total": 0, "passed": 0, "failed": 0, "all_passed": True}

    results = []
    for assertion in assertions:
        rule_type = assertion.get("type", "").strip()
        rule_value = assertion.get("value", "").strip()
        if rule_type:
            result = run_assertion(rule_type, rule_value, llm_output)
            results.append(result)

    passed = sum(1 for r in results if r["passed"])
    failed = len(results) - passed

    return {
        "results": results,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "all_passed": failed == 0
    }


# Supported types for frontend dropdown
ASSERTION_TYPES = [
    {"value": "contains", "label": "Must contain", "placeholder": "e.g., Python"},
    {"value": "not_contains", "label": "Must NOT contain", "placeholder": "e.g., As an AI language model"},
    {"value": "is_json", "label": "Must be valid JSON", "placeholder": "(no value needed)"},
    {"value": "regex", "label": "Must match regex", "placeholder": r"e.g., ^\d{3}-\d{4}$"},
    {"value": "starts_with", "label": "Must start with", "placeholder": "e.g., {"},
    {"value": "max_length", "label": "Max word count", "placeholder": "e.g., 200"},
    {"value": "min_length", "label": "Min word count", "placeholder": "e.g., 50"},
]
