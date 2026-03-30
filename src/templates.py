"""
Prompt Templates Library
========================
Pre-built prompt templates for common tasks.
Each template has a name, category, prompt text, and example expected output.
Users can load these templates to quickly test different prompt styles.
"""

# Each template is a dictionary with:
#   - name: Display name for the dropdown
#   - category: Category for grouping (Summarization, Translation, etc.)
#   - prompt: The prompt template text
#   - expected: An example expected output for evaluation

PROMPT_TEMPLATES = [
    # --- Summarization ---
    {
        "name": "Summarize in 1 sentence",
        "category": "Summarization",
        "prompt": "Summarize the following text in exactly one sentence: [PASTE YOUR TEXT HERE]",
        "expected": "A concise one-sentence summary of the key point."
    },
    {
        "name": "Summarize in 2-3 sentences",
        "category": "Summarization",
        "prompt": "Summarize the following text in 2-3 sentences. Be clear and concise: [PASTE YOUR TEXT HERE]",
        "expected": "A brief 2-3 sentence summary capturing the main ideas."
    },
    {
        "name": "ELI5 (Explain Like I'm 5)",
        "category": "Summarization",
        "prompt": "Explain the following concept in simple words that a 5-year-old would understand. Use short sentences: [PASTE YOUR CONCEPT HERE]",
        "expected": "A very simple, child-friendly explanation using everyday words."
    },

    # --- Translation ---
    {
        "name": "Translate to Spanish",
        "category": "Translation",
        "prompt": "Translate the following text to Spanish. Return ONLY the translation, no explanations: [PASTE YOUR TEXT HERE]",
        "expected": "The Spanish translation of the input text."
    },
    {
        "name": "Translate to French",
        "category": "Translation",
        "prompt": "Translate the following text to French. Return ONLY the translation, no explanations: [PASTE YOUR TEXT HERE]",
        "expected": "The French translation of the input text."
    },
    {
        "name": "Translate to Hindi",
        "category": "Translation",
        "prompt": "Translate the following text to Hindi. Return ONLY the translation, no explanations: [PASTE YOUR TEXT HERE]",
        "expected": "The Hindi translation of the input text."
    },

    # --- Code Generation ---
    {
        "name": "Python function",
        "category": "Code Generation",
        "prompt": "Write a Python function that [DESCRIBE WHAT IT SHOULD DO]. Include a docstring. Return only the code, no explanations.",
        "expected": "A clean Python function with docstring that performs the described task."
    },
    {
        "name": "Fix this code",
        "category": "Code Generation",
        "prompt": "Fix the bug in the following code. Return ONLY the corrected code:\n\n[PASTE YOUR CODE HERE]",
        "expected": "The corrected version of the code with the bug fixed."
    },
    {
        "name": "Explain this code",
        "category": "Code Generation",
        "prompt": "Explain what the following code does in plain English. Keep it under 3 sentences:\n\n[PASTE YOUR CODE HERE]",
        "expected": "A clear 1-3 sentence explanation of the code's purpose and logic."
    },

    # --- Q&A / Factual ---
    {
        "name": "Short factual answer",
        "category": "Q&A",
        "prompt": "Answer the following question in one sentence. Be precise and factual: [YOUR QUESTION HERE]",
        "expected": "A single sentence with the correct factual answer."
    },
    {
        "name": "Definition",
        "category": "Q&A",
        "prompt": "Define the following term in one clear sentence. Do not add examples or extra context: [YOUR TERM HERE]",
        "expected": "A precise one-sentence definition of the term."
    },
    {
        "name": "Compare two things",
        "category": "Q&A",
        "prompt": "Compare [THING A] and [THING B] in a short paragraph. List key differences only.",
        "expected": "A concise paragraph highlighting 3-4 key differences."
    },

    # --- Creative Writing ---
    {
        "name": "Write a haiku",
        "category": "Creative",
        "prompt": "Write a haiku (5-7-5 syllable pattern) about [YOUR TOPIC HERE]. Return only the haiku.",
        "expected": "A three-line haiku following the 5-7-5 syllable pattern."
    },
    {
        "name": "Write a tagline",
        "category": "Creative",
        "prompt": "Write a catchy tagline (under 10 words) for [YOUR PRODUCT/IDEA HERE]. Return only the tagline.",
        "expected": "A short, memorable tagline under 10 words."
    },
    {
        "name": "Write a short story",
        "category": "Creative",
        "prompt": "Write a very short story (under 100 words) about [YOUR TOPIC HERE]. Make it engaging with a clear beginning, middle, and end.",
        "expected": "An engaging micro-story under 100 words with a complete narrative arc."
    },
]


def get_template_names():
    """Returns a list of template names for the dropdown, grouped by category."""
    return ["(Select a template)"] + [f"[{t['category']}] {t['name']}" for t in PROMPT_TEMPLATES]


def get_template_by_index(index):
    """Returns a template dictionary by its index (offset by 1 for the placeholder)."""
    if index <= 0 or index > len(PROMPT_TEMPLATES):
        return None
    return PROMPT_TEMPLATES[index - 1]
