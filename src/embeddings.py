"""
Embeddings Module
=================
Handles semantic similarity calculations using sentence-transformers.
Includes hash-based LRU cache and batch encoding for performance.
"""

import hashlib
from collections import OrderedDict
from src.utils import get_logger

logger = get_logger(__name__)

_model = None
_model_loaded = False

# ── Embedding cache (LRU, 512 entries) ──
_embedding_cache = OrderedDict()
_CACHE_MAX = 512


def _cache_key(text):
    """Generate a short hash key for cache lookup."""
    return hashlib.md5(text.encode('utf-8', errors='replace')).hexdigest()


def _get_cached_embedding(text):
    """Return cached embedding or None."""
    key = _cache_key(text)
    if key in _embedding_cache:
        _embedding_cache.move_to_end(key)
        return _embedding_cache[key]
    return None


def _set_cached_embedding(text, embedding):
    """Store embedding in cache, evicting oldest if full."""
    key = _cache_key(text)
    _embedding_cache[key] = embedding
    _embedding_cache.move_to_end(key)
    if len(_embedding_cache) > _CACHE_MAX:
        _embedding_cache.popitem(last=False)


def _load_model():
    """Load the sentence-transformers model (called once)."""
    global _model, _model_loaded
    if _model_loaded:
        return _model
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading sentence-transformers model (all-MiniLM-L6-v2)...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        _model_loaded = True
        logger.info("Sentence-transformers model loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load sentence-transformers model: {e}")
        _model = None
        _model_loaded = True  # Don't retry on every call
    return _model


def preload_model():
    """Preload the embedding model at startup. Call from main.py."""
    _load_model()


def calculate_semantic_similarity(text1, text2):
    """
    Calculate semantic similarity between two texts using cosine similarity.
    Returns a score between 0.0 and 1.0.
    Uses batch encoding and LRU cache for performance.
    Falls back to simple word overlap if model is unavailable.
    """
    if not text1 or not text2:
        return 0.0

    model = _load_model()

    if model is None:
        # Fallback: simple word overlap (Jaccard similarity)
        logger.warning("Using fallback word-overlap similarity (model unavailable)")
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    try:
        from sentence_transformers import util

        # Check cache for both texts
        emb1 = _get_cached_embedding(text1)
        emb2 = _get_cached_embedding(text2)

        if emb1 is not None and emb2 is not None:
            # Both cached — fastest path
            cosine_scores = util.cos_sim(emb1, emb2)
        elif emb1 is None and emb2 is None:
            # Neither cached — batch encode both at once (~30% faster)
            embeddings = model.encode([text1, text2], convert_to_tensor=True)
            emb1, emb2 = embeddings[0], embeddings[1]
            _set_cached_embedding(text1, emb1)
            _set_cached_embedding(text2, emb2)
            cosine_scores = util.cos_sim(emb1, emb2)
        else:
            # One cached, one not — encode the missing one
            if emb1 is None:
                emb1 = model.encode(text1, convert_to_tensor=True)
                _set_cached_embedding(text1, emb1)
            else:
                emb2 = model.encode(text2, convert_to_tensor=True)
                _set_cached_embedding(text2, emb2)
            cosine_scores = util.cos_sim(emb1, emb2)

        score = cosine_scores[0][0].item()
        return max(0.0, min(1.0, score))
    except Exception as e:
        logger.error(f"Error calculating semantic similarity: {e}")
        return 0.0
