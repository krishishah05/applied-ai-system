# Model Card — Applied AI Documentation Assistant

---

## 1. System Overview

**What is this system trying to do?**  
Answer developer questions about a codebase by searching local project documentation, computing a confidence score on the retrieval result, and either returning ranked snippets (retrieval mode) or generating a grounded natural language answer (RAG and agentic modes). The system is designed to minimise hallucination and give developers a reliable starting point for investigating unfamiliar code.

**What inputs does it take?**  
A natural language developer question. Optionally, a `GEMINI_API_KEY` to enable LLM-powered modes. The document corpus is loaded automatically from `docs/` and `custom_docs/`.

**What outputs does it produce?**  
Depending on mode:
- **Retrieval Only:** Ranked paragraph snippets with source filenames and a confidence score
- **RAG:** A natural language answer with file citations and a grounding check result
- **Agentic RAG:** A self-verified answer with attempt count and groundedness metadata

---

## 2. AI Features Implemented

| Feature | Module | Description |
|---|---|---|
| RAG | `docubot.py`, `llm_client.py` | Multi-source retrieval feeds Gemini with grounded context |
| Confidence Scoring | `confidence.py` | 0-1 score per query based on retrieval signal strength |
| Input/Output Guardrails | `guardrails.py` | Blocks harmful queries; verifies output grounding |
| Agentic Self-Critique | `agent.py` | LLM evaluates its own answer and retries if ungrounded |
| Test Harness | `test_harness.py` | 10-case automated pass/fail suite with confidence reporting |
| RAG Enhancement | `custom_docs/` | Expanded corpus (DEPLOYMENT, CONTRIBUTING, ERRORS) |

---

## 3. Retrieval Design

**How does the retrieval pipeline work?**

- **Multi-source loading:** On startup, documents are loaded from both `docs/` and `custom_docs/`, giving the system 7 total files to search
- **Inverted index:** Each word maps to the files it appears in, enabling fast candidate lookup before full scoring
- **IDF-weighted scoring:** Query words are scored by how rarely they appear across documents — rare terms (like `generate_access_token`) score much higher than common terms
- **Paragraph-level splitting:** Documents are split on blank lines so only the most relevant section is returned, not an entire file
- **Prefix matching:** Query words are matched against word prefixes to handle stemming without external libraries

**What tradeoffs were made?**

- Keyword matching is fast and transparent but misses paraphrased queries. A query using "login" instead of "authenticate" may fail to retrieve the correct paragraph
- Paragraph splitting improves precision but fails on single-paragraph files and poorly formatted Markdown
- IDF scoring with a 7-document corpus gives modest separation — larger corpora benefit significantly more from IDF

---

## 4. Confidence Scoring

**How is confidence computed?**

Three signals combined with fixed weights:
- **Score gap (40%):** How much larger the top result's score is compared to the median — a large gap indicates a clear best match
- **Term coverage (40%):** Fraction of meaningful query terms found in the top snippet — directly measures relevance
- **Length factor (20%):** Penalises very short snippets that may be incomplete fragments

**Calibration observations:**  
HIGH confidence (>= 0.75) correlates strongly with correct retrieval. MEDIUM confidence (0.45-0.75) typically indicates partial matches — the right file was found but not the best paragraph. LOW confidence reliably flags cases where no clear match exists.

---

## 5. Agentic Self-Critique Loop

**How does the agent work?**

1. Retrieve top_k=3 snippets and generate an RAG answer
2. Send a separate prompt asking the LLM to evaluate whether the answer is grounded in the snippets (returns JSON with `grounded` and `reason`)
3. If grounded: return the answer with metadata
4. If not grounded and retries remain: increase top_k by 2 and repeat from step 1
5. After MAX_RETRIES (2), return the best answer found

**Observable intermediate steps:**  
The agent prints each attempt, the answer length, the self-critique result, and whether it is retrying. This makes the decision process auditable.

**Limitation:**  
The critic and the generator are the same model. In practice, the LLM sometimes validates its own ungrounded answers if they sound plausible. An independent critic model or a deterministic word-overlap check would be more reliable.

---

## 6. Guardrails

**Input guardrails:**
- Minimum query length (3 chars) and maximum (400 chars)
- Blocked patterns: credential injection (`password=...`), destructive commands (`DROP TABLE`, `rm -rf`)
- Out-of-scope phrase detection: queries about recipes, weather, sports, etc.

**Output guardrails:**
- After RAG generation, check word overlap between the answer and retrieved snippets
- Explicit refusals ("I do not know") are always accepted
- Low-overlap answers trigger a console warning

**Logging:**  
Every interaction (query, mode, answer summary, confidence) is written to `logs/docubot.log` with timestamps for auditability.

---

## 7. Testing Summary

**Test harness results (10 test cases):**

| Test | Description | Result | Confidence |
|---|---|---|---|
| TC-01 | Auth token generation location | PASS | MEDIUM (0.49) |
| TC-02 | Required auth environment variables | PASS | MEDIUM (0.69) |
| TC-03 | Database connection setup | PASS | MEDIUM (0.71) |
| TC-04 | Endpoint that lists all users | PASS | MEDIUM (0.68) |
| TC-05 | Users table schema fields | PASS | LOW (0.30) |
| TC-06 | Token refresh mechanism | PASS | MEDIUM (0.55) |
| TC-07 | Out-of-scope query returns no results | PASS | 0.00 |
| TC-08 | Projects endpoint return value | PASS | LOW (0.33) |
| TC-09 | Deployment environment setup | PASS | LOW (0.17) |
| TC-10 | Contributing — open a pull request | PASS | MEDIUM (0.63) |

**Overall: 10/10 tests pass when both doc folders are loaded. Average confidence: 0.45.**

**Key observations:**
- TC-07 (payment processing) correctly returns no results and confidence is 0.00 — the system correctly identifies out-of-scope queries
- TC-09 and TC-10 (deployment, contributing) correctly route to `custom_docs/` files when the extended corpus is loaded
- TC-05 and TC-08 score LOW confidence because the IDF scorer surfaces intro paragraphs before schema-specific paragraphs — the correct file is retrieved but the best paragraph is ranked second or third
- Pass rate is determined by file match (correct source retrieved), not content match, which is more appropriate for paragraph-level retrieval evaluation

---

## 8. Limitations and Future Improvements

**Current limitations:**
1. Keyword-only retrieval cannot handle synonyms or paraphrases
2. The self-critique judge is the same model as the generator — risk of self-validation bias
3. Confidence calibration is heuristic and not validated against a ground-truth annotation set
4. No rate limiting or authentication — not suitable for public deployment as-is

**Future improvements:**
1. Embedding-based retrieval (e.g. Gemini embeddings API) for semantic similarity matching
2. A minimum confidence threshold below which the system refuses to answer rather than returning low-quality snippets
3. A separate, smaller judge model for the self-critique step to reduce self-validation bias
4. Section header context in returned snippets so developers can navigate directly to the right part of the documentation

---

## 9. Responsible Use

**Where could this system cause harm?**  
In Naive LLM mode, Gemini fabricates plausible-sounding but incorrect function names, endpoint paths, and configuration values. A developer who acts on these without verification could introduce security vulnerabilities or waste significant debugging time. In RAG mode, if the source documentation is outdated or incorrect, the system faithfully amplifies those errors.

**Preventing misuse:**  
- Never use Naive LLM mode for production decisions
- Treat every answer as a pointer to the documentation, not a final answer
- Keep the `docs/` and `custom_docs/` folders up to date — the system is only as accurate as its sources
- Verify security-sensitive answers (auth tokens, database credentials, environment variables) against the actual source files

**AI collaboration reflection:**  
- **Helpful:** When designing the score gap signal, normalising by the top score rather than the range (max - min) prevented the metric from being inflated on queries with many medium-scoring results — a non-obvious calibration detail that measurably improved confidence accuracy
- **Flawed:** An early approach suggested using the Gemini `function_calling` API to structure the self-critique response, which produced unstable JSON in roughly 20% of calls. Switching to a plain-text prompt requesting JSON with regex-based fence stripping was more reliable and required no API schema changes
