"""
Utility Functions
=================
Logging, CSV handling, and SQLite database operations.
"""

import pandas as pd
import os
import sqlite3
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('LLM-Prompt-Evaluator')


def get_logger(name):
    return logging.getLogger(name)


def read_prompts_csv(filepath):
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return pd.DataFrame()


def save_results_csv(results, filepath):
    df = pd.DataFrame(results)
    if os.path.exists(filepath):
        existing_df = pd.read_csv(filepath)
        df = pd.concat([existing_df, df], ignore_index=True)
    df.to_csv(filepath, index=False)


# =====================
# Database Functions
# =====================

def init_db(db_path):
    """Create the database and tables if they don't exist."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt TEXT,
            expected_output TEXT,
            llm_output TEXT,
            model_name TEXT,
            score REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    # Upgrade schema: add new columns if they don't exist
    # This keeps backward compatibility with older databases
    new_columns = [
        ("judge_score", "REAL"),
        ("feedback", "TEXT"),
        ("semantic_similarity", "REAL"),
        ("lineage_id", "TEXT"),
        ("iteration", "INTEGER"),
    ]
    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE evaluation_results ADD COLUMN {col_name} {col_type}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists, skip

    conn.close()


def save_to_db(db_path, prompt, expected_output, llm_output, model_name, score,
               judge_score=None, feedback=None, semantic_similarity=None, lineage_id=None, iteration=0):
    """Save a single evaluation result to the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO evaluation_results 
        (prompt, expected_output, llm_output, model_name, score, judge_score, feedback, semantic_similarity, lineage_id, iteration)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (prompt, expected_output, llm_output, model_name, score, judge_score, feedback, semantic_similarity, lineage_id, iteration))
    conn.commit()
    conn.close()


def get_history(db_path, limit=100):
    """
    Fetch past evaluation results from the database.
    Returns a list of dictionaries, newest first.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, prompt, expected_output, llm_output, model_name, score, 
               judge_score, feedback, semantic_similarity, lineage_id, iteration, timestamp
        FROM evaluation_results 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_history_entry(db_path, entry_id):
    """
    Fetch a single evaluation result by its ID.
    Returns the full record as a dictionary, or None if not found.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, prompt, expected_output, llm_output, model_name, score, 
               judge_score, feedback, semantic_similarity, lineage_id, iteration, timestamp
        FROM evaluation_results 
        WHERE id = ?
    ''', (entry_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def clear_history(db_path):
    """Delete all evaluation results from the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM evaluation_results")
    conn.commit()
    conn.close()

def get_iterations(db_path, limit=50):
    """
    Fetch all iterations from the db, specifically looking for ones with lineage_id.
    Group them by lineage_id and sort by iteration ASC so we can render charts easily.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Get rows that have a lineage_id
    cursor.execute('''
        SELECT id, prompt, expected_output, llm_output, model_name, score, 
               judge_score, feedback, semantic_similarity, lineage_id, iteration, timestamp
        FROM evaluation_results 
        WHERE lineage_id IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit * 5,)) # load more since multiple rows belong to one lineage
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Group by lineage
    lineages = {}
    for r in rows:
        lid = r['lineage_id']
        if lid not in lineages:
            lineages[lid] = []
        lineages[lid].append(r)
        
    # Sort each lineage internally by iteration ascending
    result = []
    # Reverse so newest are first
    for lid, items in lineages.items():
        items.sort(key=lambda x: x['iteration'])
        result.append({
            "lineage_id": lid,
            "original_prompt": items[0]['prompt'] if items else "",
            "model_name": items[0]['model_name'] if items else "",
            "timestamp": items[0]['timestamp'] if items else "",
            "iterations": items
        })
    return result
