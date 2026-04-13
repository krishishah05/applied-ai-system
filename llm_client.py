"""
Gemini client wrapper for the Applied AI Documentation Assistant.

Handles:
- Configuring the Gemini client from the GEMINI_API_KEY environment variable
- Naive "generation only" answers over the full docs corpus (Mode 1)
- RAG style answers that use only retrieved snippets (Mode 3 & 4)
"""

import os
from google import genai
from google.genai import types

GEMINI_MODEL_NAME = "gemini-1.5-flash"


class GeminiClient:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing GEMINI_API_KEY environment variable. "
                "Set it in your shell or .env file to enable LLM features."
            )
        self.client = genai.Client(api_key=api_key)
        # Expose model attribute so agent.py can call generate_content directly
        self.model = self

    def generate_content(self, prompt):
        """Direct generate call — used by agent.py for self-critique."""
        response = self.client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
        )
        return _Response(response.text or "")

    def naive_answer_over_full_docs(self, query, all_text):
        prompt = f"You are a documentation assistant.\nAnswer this developer question: {query}"
        response = self.client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
        )
        return (response.text or "").strip()

    def answer_from_snippets(self, query, snippets):
        if not snippets:
            return "I do not know based on the docs I have."

        context = "\n\n".join(f"File: {fname}\n{text}" for fname, text in snippets)

        prompt = f"""You are a cautious documentation assistant helping developers understand a codebase.

You will receive:
- A developer question
- A small set of snippets from project files

Your job:
- Answer the question using only the information in the snippets.
- If the snippets do not provide enough evidence, refuse to guess.

Snippets:
{context}

Developer question:
{query}

Rules:
- Use only the information in the snippets. Do not invent new functions,
  endpoints, or configuration values.
- If the snippets are not enough to answer confidently, reply exactly:
  "I do not know based on the docs I have."
- When you do answer, briefly mention which files you relied on.
"""
        response = self.client.models.generate_content(
            model=GEMINI_MODEL_NAME,
            contents=prompt,
        )
        return (response.text or "").strip()


class _Response:
    """Minimal response wrapper so agent.py can call response.text."""
    def __init__(self, text):
        self.text = text
