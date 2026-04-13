"""
Agentic self-critique loop for the Applied AI Documentation Assistant.

After a RAG answer is generated, the agent asks the LLM to evaluate
whether the answer is grounded in the retrieved snippets. If groundedness
fails, the agent retries with a wider retrieval window (higher top_k).

Observable intermediate steps are printed during execution so the
decision-making process is transparent.
"""

import json
import re

MAX_RETRIES = 2  # max extra attempts after the first try


def _critique(llm_client, query, answer, snippets):
    """
    Ask the LLM to evaluate whether an answer is grounded in snippets.

    Returns (is_grounded: bool, reason: str).
    Falls back to (True, reason) on parse failure to avoid infinite loops.
    """
    if not snippets:
        return False, "No snippets available for grounding check"

    context_lines = "\n".join(
        f"[{fname}] {text[:200]}" for fname, text in snippets
    )

    prompt = f"""You are a quality evaluator for a documentation assistant.

User asked: "{query}"
Assistant answered: "{answer}"

The answer should be grounded only in these documentation snippets:
{context_lines}

Evaluate whether the assistant's answer is grounded in the snippets.
Reply with valid JSON only — no markdown fences:
{{"grounded": true or false, "reason": "one sentence"}}"""

    try:
        response = llm_client.model.generate_content(prompt)
        raw = (response.text or "").strip()
        raw = re.sub(r"```(?:json)?\n?", "", raw).strip().rstrip("`")
        result = json.loads(raw)
        return bool(result.get("grounded", False)), str(result.get("reason", ""))
    except Exception as exc:
        return True, f"Critique parse error (assuming grounded): {exc}"


def agentic_rag_answer(bot, query, verbose=True):
    """
    Run the agentic RAG loop with self-critique.

    Steps
    -----
    1. Retrieve top_k snippets and generate an answer
    2. Ask the LLM to evaluate groundedness (self-critique)
    3. If not grounded and retries remain, increase top_k and repeat
    4. Return the best answer with execution metadata

    Parameters
    ----------
    bot     : DocuBot instance (must have llm_client set)
    query   : str — the user's question
    verbose : bool — print intermediate steps

    Returns
    -------
    dict with keys: answer, grounded, critique, attempts, final_top_k
    """
    if bot.llm_client is None:
        raise RuntimeError("Agentic RAG mode requires an LLM client.")

    top_k = 3

    for attempt in range(1, MAX_RETRIES + 2):
        if verbose:
            print(f"\n  [Agent] Attempt {attempt} — retrieving top_k={top_k}")

        snippets = bot.retrieve(query, top_k=top_k)

        if not snippets:
            if verbose:
                print("  [Agent] No snippets found — returning refusal")
            return {
                "answer": "I do not know based on the docs I have.",
                "grounded": True,
                "critique": "No matching documentation found",
                "attempts": attempt,
                "final_top_k": top_k,
            }

        answer = bot.llm_client.answer_from_snippets(query, snippets)

        if verbose:
            print(f"  [Agent] Answer generated ({len(answer)} chars)")
            print("  [Agent] Running self-critique...")

        is_grounded, reason = _critique(bot.llm_client, query, answer, snippets)

        if verbose:
            status = "PASS" if is_grounded else "FAIL"
            print(f"  [Agent] Groundedness check: {status} — {reason}")

        if is_grounded or attempt > MAX_RETRIES:
            return {
                "answer": answer,
                "grounded": is_grounded,
                "critique": reason,
                "attempts": attempt,
                "final_top_k": top_k,
            }

        # Broaden retrieval and retry
        top_k = min(top_k + 2, max(len(bot.documents) * 2, top_k + 2))
        if verbose:
            print(f"  [Agent] Not grounded — retrying with top_k={top_k}")

    return {
        "answer": answer,
        "grounded": False,
        "critique": "Max retries reached",
        "attempts": MAX_RETRIES + 1,
        "final_top_k": top_k,
    }
