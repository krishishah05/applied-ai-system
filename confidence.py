"""
Confidence scoring for the Applied AI Documentation Assistant.

Computes a 0.0-1.0 confidence score for a retrieval result by combining
three independent signals:
  1. Score gap  — how much better the top result is than the median
  2. Term coverage — fraction of meaningful query terms found in the snippet
  3. Length factor — penalizes very short snippets that may be fragments
"""

import string

STOP_WORDS = {
    "where", "is", "the", "a", "an", "how", "do", "i", "what",
    "which", "does", "are", "in", "of", "to", "for", "and", "or",
    "it", "any", "there", "these", "my", "me", "on", "at", "by",
    "with", "from", "that", "this", "be", "was", "were", "has", "have"
}


def extract_meaningful_terms(query):
    """
    Tokenise query and return terms that carry semantic signal.
    Removes stop words and tokens shorter than 3 characters.
    """
    terms = []
    for word in query.lower().split():
        word = word.strip(string.punctuation)
        if word and word not in STOP_WORDS and len(word) >= 3:
            terms.append(word)
    return terms


def compute_confidence(top_score, all_scores, query_terms, top_snippet):
    """
    Returns a confidence score in [0.0, 1.0].

    Parameters
    ----------
    top_score   : float  — retrieval score of the best paragraph
    all_scores  : list   — scores of all retrieved paragraphs
    query_terms : list   — meaningful query tokens (from extract_meaningful_terms)
    top_snippet : str    — text of the best paragraph

    Weights
    -------
    40%  score gap    — relative separation between best and median result
    40%  term coverage — query terms present in the top snippet
    20%  length factor — snippets under 20 words are penalised
    """
    if not all_scores or top_score <= 0:
        return 0.0

    # Signal 1: relative gap between top score and median score
    sorted_scores = sorted(all_scores, reverse=True)
    median_score = sorted_scores[len(sorted_scores) // 2]
    gap = (top_score - median_score) / (top_score + 1e-9)
    gap = max(0.0, min(gap, 1.0))

    # Signal 2: fraction of meaningful query terms present in the snippet
    snippet_lower = top_snippet.lower()
    if query_terms:
        matched = sum(1 for t in query_terms if t in snippet_lower)
        coverage = matched / len(query_terms)
    else:
        coverage = 0.5  # neutral when query has no meaningful terms

    # Signal 3: snippet length — penalise fragments shorter than 20 words
    word_count = len(top_snippet.split())
    length_factor = min(word_count / 20.0, 1.0)

    score = 0.4 * gap + 0.4 * coverage + 0.2 * length_factor
    return round(min(max(score, 0.0), 1.0), 2)


def confidence_label(score):
    """Map a numeric confidence score to a human-readable tier."""
    if score >= 0.75:
        return "HIGH"
    elif score >= 0.45:
        return "MEDIUM"
    else:
        return "LOW"
