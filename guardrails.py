"""
Input validation, output grounding checks, and interaction logging
for the Applied AI Documentation Assistant.

Guardrails sit at two points in the pipeline:
  1. Before retrieval — validate the user's query
  2. After generation — verify the answer is grounded in retrieved snippets
"""

import os
import re
import string
import logging
from datetime import datetime

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=os.path.join("logs", "docubot.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input validation constants
# ---------------------------------------------------------------------------

MAX_QUERY_LENGTH = 400
MIN_QUERY_LENGTH = 3

# Patterns that suggest injection or credential-stuffing attempts
BLOCKED_PATTERNS = [
    r"\b(rm\s+-rf|drop\s+table|delete\s+from)\b",
    r"(password|secret|api[_\s]?key)\s*[=:]\s*\S+",
]

# Topics clearly outside developer-documentation scope
OUT_OF_SCOPE_PHRASES = [
    "recipe", "weather forecast", "stock price", "sports score",
    "celebrity", "write me a poem", "tell me a joke", "movie review",
]


def validate_input(query):
    """
    Check whether a query is safe and in scope before processing.

    Returns
    -------
    (is_valid: bool, reason: str)
        reason is "ok" on success, or a user-facing message on failure.
    """
    if not query or len(query.strip()) < MIN_QUERY_LENGTH:
        logger.warning("Query rejected: too short (%d chars)", len(query))
        return False, "Query is too short. Please ask a full question."

    if len(query) > MAX_QUERY_LENGTH:
        logger.warning("Query rejected: too long (%d chars)", len(query))
        return False, f"Query exceeds the {MAX_QUERY_LENGTH}-character limit."

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning("Query blocked by guardrail pattern: %s", pattern)
            return False, "Query contains blocked content and cannot be processed."

    query_lower = query.lower()
    for phrase in OUT_OF_SCOPE_PHRASES:
        if phrase in query_lower:
            logger.info("Out-of-scope query: %.60s", query)
            return False, (
                "This question appears to be outside the scope of "
                "developer documentation."
            )

    return True, "ok"


# ---------------------------------------------------------------------------
# Output grounding check
# ---------------------------------------------------------------------------

def validate_output(answer, snippets):
    """
    Estimate whether an answer is grounded in the retrieved snippets by
    checking word-level overlap.

    Returns
    -------
    (is_grounded: bool, note: str)
    """
    answer_lower = answer.lower()

    # Explicit refusals are always acceptable
    if "i do not know" in answer_lower or "cannot answer" in answer_lower:
        return True, "Appropriate refusal"

    if not snippets:
        return False, "No snippets were retrieved — answer may be ungrounded"

    for _filename, text in snippets:
        # Extract longer words as a proxy for content words
        snippet_words = [
            w.strip(string.punctuation).lower()
            for w in text.split()
            if len(w) > 4
        ][:40]
        overlap = sum(1 for w in snippet_words if w in answer_lower)
        if overlap >= 3:
            return True, "Grounded"

    logger.warning("Output grounding check failed — low overlap with snippets")
    return False, "Answer has low overlap with retrieved snippets"


# ---------------------------------------------------------------------------
# Interaction logging
# ---------------------------------------------------------------------------

def log_interaction(query, mode, answer, confidence=None):
    """Write a single query/answer interaction to the log file."""
    summary = (answer or "")[:120].replace("\n", " ")
    conf_str = f" confidence={confidence:.2f}" if confidence is not None else ""
    logger.info("[%s]%s | Q: %.80s | A: %s", mode, conf_str, query, summary)
