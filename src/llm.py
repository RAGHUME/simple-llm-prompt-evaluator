"""
LLM Interface Module
====================
Handles all communication with the local Ollama API.
- Time-limited model listing with TTL cache (not lru_cache)
- Configurable timeouts on generation
- Graceful error handling
"""

import requests
import time
import os
from src.utils import get_logger

logger = get_logger(__name__)

# Allow overriding the local Ollama URL via Render Environment Variables for Hybrid deployments
BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{BASE_URL}/api/generate"
OLLAMA_TAGS_URL = f"{BASE_URL}/api/tags"

# TTL-based cache for model listing (refreshes every 30s)
_models_cache = {"models": [], "timestamp": 0, "ttl": 30}


def get_available_models():
    """Fetch available models from local Ollama instance with 30s TTL cache."""
    now = time.time()
    if now - _models_cache["timestamp"] < _models_cache["ttl"] and _models_cache["models"]:
        return _models_cache["models"]
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=3)
        if response.status_code == 200:
            models = response.json().get('models', [])
            names = [model['name'] for model in models]
            _models_cache["models"] = names
            _models_cache["timestamp"] = now
            return names
        return _models_cache["models"]  # Return stale cache on non-200
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Ollama: {e}")
        return _models_cache["models"]  # Return stale cache on error


def invalidate_model_cache():
    """Force-refresh the model cache on next call."""
    _models_cache["timestamp"] = 0


def generate_response(prompt, model="phi3:mini", temperature=0.7, max_tokens=None, timeout=120):
    """
    Generate a response using the local Ollama API.

    Args:
        prompt: The prompt string to send
        model: Ollama model name
        temperature: Sampling temperature (0.0-1.0)
        max_tokens: Max tokens to generate (None = model default)
        timeout: Request timeout in seconds (default 120)

    Returns:
        str: The generated response text, or an error message string
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens or 512
        }
    }

    try:
        response = requests.post(OLLAMA_API_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ({timeout}s) generating response from model {model}")
        return f"Error: Request timed out after {timeout}s. The model may be overloaded."
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to Ollama at {OLLAMA_API_URL}")
        return "Error: Cannot connect to Ollama. Make sure it is running (ollama serve)."
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating response from model {model}: {e}")
        return f"Error: Unable to generate response. {str(e)}"
