"""
Core retrieval pipeline for the Applied AI Documentation Assistant.

Responsibilities:
- Load documents from one or more doc folders (supports RAG Enhancement)
- Build an inverted index for fast candidate lookup
- Score paragraphs with IDF-weighted matching and prefix support
- Retrieve top-k snippets with optional confidence scores
- Support retrieval-only, naive LLM, and RAG answer modes
"""

import os
import glob
import re
import string


class DocuBot:
    def __init__(self, docs_folder="docs", extra_docs_folders=None, llm_client=None):
        """
        Parameters
        ----------
        docs_folder        : primary directory of .md/.txt documentation files
        extra_docs_folders : optional list of additional doc directories
                             (RAG Enhancement — multi-source retrieval)
        llm_client         : optional GeminiClient for LLM-powered modes
        """
        self.docs_folder = docs_folder
        self.extra_docs_folders = extra_docs_folders or []
        self.llm_client = llm_client

        self.documents = self.load_documents()
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Load all .md and .txt files from docs_folder and any extra_docs_folders.
        Returns a list of (filename, text) tuples.
        """
        all_folders = [self.docs_folder] + self.extra_docs_folders
        docs = []
        seen = set()

        for folder in all_folders:
            if not os.path.isdir(folder):
                continue
            for path in glob.glob(os.path.join(folder, "*.*")):
                if not (path.endswith(".md") or path.endswith(".txt")):
                    continue
                filename = os.path.basename(path)
                if filename in seen:
                    continue
                seen.add(filename)
                with open(path, "r", encoding="utf-8") as f:
                    docs.append((filename, f.read()))

        return docs

    # -----------------------------------------------------------
    # Index Construction
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        Build an inverted index: { word: [filename, ...] }

        Tokens are lowercased and stripped of punctuation.
        """
        index = {}
        for filename, text in documents:
            for word in text.lower().split():
                word = word.strip(string.punctuation)
                if not word:
                    continue
                if word not in index:
                    index[word] = []
                if filename not in index[word]:
                    index[word].append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        IDF-weighted relevance score for a (query, paragraph) pair.

        - Stop words and tokens < 3 chars are skipped
        - Exact matches are weighted by IDF (words in fewer docs score higher)
        - Prefix matches (e.g. "generated" -> "generate_access_token") score 0.5x
        - A 10-point bonus is awarded for exact phrase matches
        """
        STOP_WORDS = {
            "where", "is", "the", "a", "an", "how", "do", "i", "what",
            "which", "does", "are", "in", "of", "to", "for", "and", "or",
            "it", "any", "there", "these"
        }

        query_lower = query.lower()
        text_lower = text.lower()
        text_words = [w.strip(string.punctuation) for w in text_lower.split()]
        total_docs = max(len(self.documents), 1)
        query_words = [w.strip(string.punctuation) for w in query_lower.split()]

        word_score = 0.0
        for qword in query_words:
            if not qword or qword in STOP_WORDS or len(qword) < 3:
                continue
            doc_freq = len(self.index.get(qword, [qword]))
            idf = total_docs / doc_freq
            if qword in text_lower:
                word_score += text_lower.count(qword) * idf
            else:
                stem = qword[:max(4, len(qword) - 2)]
                for tw in text_words:
                    if tw.startswith(stem):
                        word_score += 0.5 * idf
                        break

        phrase_bonus = 10 if query_lower in text_lower else 0
        return word_score + phrase_bonus

    def _split_into_paragraphs(self, text):
        """Split text on blank lines, filtering fragments shorter than 30 chars."""
        paragraphs = re.split(r"\n\s*\n", text)
        return [p.strip() for p in paragraphs if len(p.strip()) > 30]

    # -----------------------------------------------------------
    # Retrieval
    # -----------------------------------------------------------

    def retrieve(self, query, top_k=3):
        """
        Return top_k (filename, snippet) pairs ranked by relevance score.
        """
        if not self.documents:
            return []

        query_words = [
            w.strip(string.punctuation).lower()
            for w in query.split()
            if w.strip(string.punctuation)
        ]
        candidate_files = set()
        for word in query_words:
            if word in self.index:
                candidate_files.update(self.index[word])

        candidates = (
            [(f, t) for f, t in self.documents if f in candidate_files]
            if candidate_files
            else self.documents
        )

        scored = []
        for filename, text in candidates:
            paragraphs = self._split_into_paragraphs(text)
            if not paragraphs:
                score = self.score_document(query, text)
                if score > 0:
                    scored.append((score, filename, text[:500]))
                continue
            for para in paragraphs:
                score = self.score_document(query, para)
                if score > 0:
                    scored.append((score, filename, para))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, filename, snippet in scored:
            results.append((filename, snippet))
            if len(results) >= top_k:
                break

        return results

    def retrieve_with_scores(self, query, top_k=3):
        """
        Like retrieve(), but also returns the raw relevance scores.
        Returns a list of (score, filename, snippet) tuples.
        Used by the confidence module and test harness.
        """
        if not self.documents:
            return []

        query_words = [
            w.strip(string.punctuation).lower()
            for w in query.split()
            if w.strip(string.punctuation)
        ]
        candidate_files = set()
        for word in query_words:
            if word in self.index:
                candidate_files.update(self.index[word])

        candidates = (
            [(f, t) for f, t in self.documents if f in candidate_files]
            if candidate_files
            else self.documents
        )

        scored = []
        for filename, text in candidates:
            paragraphs = self._split_into_paragraphs(text)
            if not paragraphs:
                score = self.score_document(query, text)
                if score > 0:
                    scored.append((score, filename, text[:500]))
                continue
            for para in paragraphs:
                score = self.score_document(query, para)
                if score > 0:
                    scored.append((score, filename, para))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    # -----------------------------------------------------------
    # Answer Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=5):
        """Return ranked snippets as plain text — no LLM involved."""
        snippets = self.retrieve(query, top_k=top_k)
        if not snippets:
            return "I do not know based on these docs."
        return "\n---\n".join(f"[{fname}]\n{text}" for fname, text in snippets)

    def answer_rag(self, query, top_k=5):
        """Retrieve snippets then ask Gemini to synthesise an answer."""
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )
        snippets = self.retrieve(query, top_k=top_k)
        if not snippets:
            return "I do not know based on these docs."
        return self.llm_client.answer_from_snippets(query, snippets)

    def full_corpus_text(self):
        """Concatenate all documents — used by naive LLM mode."""
        return "\n\n".join(text for _, text in self.documents)
