"""
CLI runner for the Applied AI Documentation Assistant.

Modes
-----
1. Naive LLM    — Gemini answers from general knowledge, no docs
2. Retrieval    — keyword-based snippet retrieval, no LLM
3. RAG          — retrieval + Gemini, grounded answers with citations
4. Agentic RAG  — RAG with self-critique loop and automatic retry

All modes apply input guardrails and show a confidence score in Modes 2-4.
"""

from dotenv import load_dotenv
load_dotenv()

from docubot import DocuBot
from llm_client import GeminiClient
from dataset import SAMPLE_QUERIES
from confidence import compute_confidence, confidence_label, extract_meaningful_terms
from guardrails import validate_input, validate_output, log_interaction
from agent import agentic_rag_answer

DOCS_FOLDER = "docs"
EXTRA_DOCS = ["custom_docs"]


def try_create_llm_client():
    try:
        client = GeminiClient()
        return client, True
    except RuntimeError as exc:
        print("Warning: LLM features are disabled.")
        print(f"Reason: {exc}")
        print("You can still run Retrieval mode.\n")
        return None, False


def choose_mode(has_llm):
    print("Choose a mode:")
    if has_llm:
        print("  1) Naive LLM          (Gemini, no docs)")
    else:
        print("  1) Naive LLM          (unavailable — no GEMINI_API_KEY)")
    print("  2) Retrieval only     (no LLM, shows confidence score)")
    if has_llm:
        print("  3) RAG                (retrieval + Gemini, grounded)")
        print("  4) Agentic RAG        (RAG + self-critique loop)")
    else:
        print("  3) RAG                (unavailable — no GEMINI_API_KEY)")
        print("  4) Agentic RAG        (unavailable — no GEMINI_API_KEY)")
    print("  q) Quit")
    return input("Enter choice: ").strip().lower()


def get_queries():
    print("\nPress Enter to run built-in sample queries.")
    custom = input("Or type a custom question: ").strip()
    return ([custom], "custom query") if custom else (SAMPLE_QUERIES, "sample queries")


def _show_confidence(bot, query, snippets):
    if not snippets:
        return
    terms = extract_meaningful_terms(query)
    all_scores = [bot.score_document(query, text) for _, text in snippets]
    top_score = all_scores[0] if all_scores else 0.0
    top_snippet = snippets[0][1]
    conf = compute_confidence(top_score, all_scores, terms, top_snippet)
    print(f"Confidence: {conf:.2f} [{confidence_label(conf)}]")


def run_naive_llm_mode(bot, has_llm):
    if not has_llm or bot.llm_client is None:
        print("\nNaive LLM mode is unavailable (no GEMINI_API_KEY).\n")
        return

    queries, label = get_queries()
    print(f"\nRunning naive LLM mode on {label}...\n")
    all_text = bot.full_corpus_text()

    for query in queries:
        valid, reason = validate_input(query)
        if not valid:
            print(f"[Guardrail] {reason}\n")
            continue
        print("=" * 60)
        print(f"Question: {query}\n")
        answer = bot.llm_client.naive_answer_over_full_docs(query, all_text)
        print("Answer:")
        print(answer)
        log_interaction(query, "naive", answer)
        print()


def run_retrieval_only_mode(bot):
    queries, label = get_queries()
    print(f"\nRunning retrieval mode on {label}...\n")

    for query in queries:
        valid, reason = validate_input(query)
        if not valid:
            print(f"[Guardrail] {reason}\n")
            continue
        print("=" * 60)
        print(f"Question: {query}\n")
        snippets = bot.retrieve(query, top_k=5)
        _show_confidence(bot, query, snippets)
        answer = bot.answer_retrieval_only(query)
        print("Retrieved snippets:")
        print(answer)
        log_interaction(query, "retrieval", answer)
        print()


def run_rag_mode(bot, has_llm):
    if not has_llm or bot.llm_client is None:
        print("\nRAG mode is unavailable (no GEMINI_API_KEY).\n")
        return

    queries, label = get_queries()
    print(f"\nRunning RAG mode on {label}...\n")

    for query in queries:
        valid, reason = validate_input(query)
        if not valid:
            print(f"[Guardrail] {reason}\n")
            continue
        print("=" * 60)
        print(f"Question: {query}\n")
        snippets = bot.retrieve(query, top_k=5)
        _show_confidence(bot, query, snippets)
        answer = bot.answer_rag(query)
        grounded, note = validate_output(answer, snippets)
        if not grounded:
            print(f"[Guardrail] Output warning: {note}")
        print("Answer:")
        print(answer)
        log_interaction(query, "rag", answer)
        print()


def run_agentic_rag_mode(bot, has_llm):
    if not has_llm or bot.llm_client is None:
        print("\nAgentic RAG mode is unavailable (no GEMINI_API_KEY).\n")
        return

    queries, label = get_queries()
    print(f"\nRunning agentic RAG mode on {label}...\n")

    for query in queries:
        valid, reason = validate_input(query)
        if not valid:
            print(f"[Guardrail] {reason}\n")
            continue
        print("=" * 60)
        print(f"Question: {query}\n")
        result = agentic_rag_answer(bot, query, verbose=True)
        print(f"\nAnswer (attempts={result['attempts']}, grounded={result['grounded']}):")
        print(result["answer"])
        log_interaction(query, "agentic", result["answer"])
        print()


def main():
    print("Applied AI Documentation Assistant")
    print("===================================\n")

    llm_client, has_llm = try_create_llm_client()
    bot = DocuBot(
        docs_folder=DOCS_FOLDER,
        extra_docs_folders=EXTRA_DOCS,
        llm_client=llm_client,
    )
    print(f"Loaded {len(bot.documents)} documents from {DOCS_FOLDER}/ + {EXTRA_DOCS}\n")

    while True:
        choice = choose_mode(has_llm)
        if choice == "q":
            print("\nGoodbye.")
            break
        elif choice == "1":
            run_naive_llm_mode(bot, has_llm)
        elif choice == "2":
            run_retrieval_only_mode(bot)
        elif choice == "3":
            run_rag_mode(bot, has_llm)
        elif choice == "4":
            run_agentic_rag_mode(bot, has_llm)
        else:
            print("\nUnknown choice. Please pick 1, 2, 3, 4, or q.\n")


if __name__ == "__main__":
    main()
