# Applied AI Documentation Assistant

A production-grade developer documentation assistant built on top of DocuBot (Module 4). The system answers developer questions by combining keyword-based retrieval with Gemini-powered generation, confidence scoring, output guardrails, and an agentic self-critique loop.

---

## Base Project

**Original project:** DocuBot (Module 4 — Retrieval-Augmented Generation)

DocuBot was a lightweight RAG prototype that answered developer questions by searching a small set of project documentation files using an IDF-weighted inverted index. It demonstrated three modes: naive LLM generation, retrieval-only, and RAG. Its core limitation was that it had no way to measure how confident the retrieval was, no guardrails to block unsafe or out-of-scope queries, and no mechanism to detect or recover from ungrounded answers.

This project extends DocuBot into a full applied AI system by adding confidence scoring, input/output guardrails with logging, an agentic self-critique loop, multi-source document retrieval, and an automated test harness.

---

## What the System Does

Given a developer's natural language question, the assistant:

1. Validates the input against guardrails (length, blocked patterns, out-of-scope detection)
2. Retrieves the most relevant paragraph-level snippets from a multi-source document corpus using IDF-weighted scoring
3. Computes a confidence score based on retrieval signal strength, query term coverage, and snippet quality
4. Answers in one of four modes:
   - **Naive LLM** — Gemini answers from training knowledge only (baseline comparison)
   - **Retrieval** — returns ranked snippets with confidence score, no LLM
   - **RAG** — Gemini synthesises a grounded answer from retrieved snippets, with output grounding check
   - **Agentic RAG** — RAG with a self-critique loop: the LLM evaluates its own answer for groundedness and retries with broader retrieval if it fails
5. Logs every interaction to `logs/docubot.log`

---

## System Architecture

The diagram below shows how data flows through the system. A rendered PNG version is in [`assets/architecture.md`](assets/architecture.md) (Mermaid source included for export).

```
User Query
    │
    ▼
┌─────────────────────────────┐
│  Input Guardrails           │  guardrails.py
│  length · blocked patterns  │◄── blocks harmful/out-of-scope queries
│  out-of-scope detection     │
└──────────────┬──────────────┘
               │ valid
               ▼
┌─────────────────────────────┐
│  Multi-Source Retrieval     │  docubot.py
│  docs/ + custom_docs/       │◄── 7 documentation files
│  IDF-weighted paragraph     │
│  scoring + prefix matching  │
└──────────────┬──────────────┘
               │ top-k snippets
               ▼
┌─────────────────────────────┐
│  Confidence Scoring         │  confidence.py
│  score gap · term coverage  │
│  · snippet length factor    │
└──────────────┬──────────────┘
               │
       ┌───────┼────────────────┐
       ▼       ▼                ▼
   Retrieval  RAG           Agentic RAG
   Only       │             │
              ▼             ▼
           Gemini       Gemini → Self-Critique
           generate     ┌──────────────────┐
                        │ grounded? YES → done
                        │ grounded? NO  → retry
                        │   (increase top_k)
                        └──────────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Output Guardrail           │  guardrails.py
│  grounding check            │
└──────────────┬──────────────┘
               │
               ▼
         Answer + Confidence
               │
               ▼
         logs/docubot.log
```

**Components:**
- `docubot.py` — retrieval pipeline (index, scoring, paragraph splitting, multi-source loading)
- `confidence.py` — confidence scoring (score gap, term coverage, length factor)
- `guardrails.py` — input validation, output grounding check, interaction logging
- `agent.py` — agentic self-critique loop with automatic retry
- `llm_client.py` — Gemini API wrapper for naive and RAG generation
- `main.py` — CLI entry point for all four modes
- `test_harness.py` — automated test suite with pass/fail reporting
- `evaluation.py` — retrieval hit-rate evaluation against expected sources
- `dataset.py` — sample queries and fallback corpus
- `docs/` — primary documentation corpus (AUTH, API, DATABASE, SETUP)
- `custom_docs/` — extended corpus (DEPLOYMENT, CONTRIBUTING, ERRORS)
- `logs/` — generated interaction log files

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your Gemini API key

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_api_key_here
```

Get a key at [aistudio.google.com/app/apikeys](https://aistudio.google.com/app/apikeys).  
Without a key, Retrieval mode (Mode 2) still works fully.

---

## Running the Assistant

```bash
python main.py
```

Choose a mode:

- **1** — Naive LLM (Gemini answers with no docs, from training knowledge)
- **2** — Retrieval only (no LLM, returns ranked snippets + confidence score)
- **3** — RAG (retrieval + Gemini, grounded answer with output guardrail)
- **4** — Agentic RAG (RAG + self-critique loop with observable retry steps)

Press Enter to run all built-in sample queries, or type a custom question.

---

## Running the Test Harness

```bash
python test_harness.py
```

Runs 10 predefined test cases covering retrieval accuracy, confidence scoring, and out-of-scope handling. Prints per-test PASS/FAIL results and aggregate statistics.

---

## Running Retrieval Evaluation

```bash
python evaluation.py
```

Prints per-query hit/miss results and an overall hit rate against expected source files.

---

## Sample Interactions

### Mode 2 — Retrieval Only

**Input:** `Where is the auth token generated?`

```
Confidence: 0.82 [HIGH]

Retrieved snippets:
[AUTH.md]
Tokens are created by the generate_access_token function inside auth_utils.py.
They are signed using the AUTH_SECRET_KEY environment variable.
```

---

### Mode 3 — RAG

**Input:** `Which fields are stored in the users table?`

```
Confidence: 0.79 [HIGH]

Answer:
Based on DATABASE.md, the users table contains the following fields:
- user_id
- email
- password_hash
- joined_at
```

---

### Mode 4 — Agentic RAG (self-critique)

**Input:** `How does a client refresh an access token?`

```
  [Agent] Attempt 1 — retrieving top_k=3
  [Agent] Answer generated (241 chars)
  [Agent] Running self-critique...
  [Agent] Groundedness check: PASS — Answer accurately cites the /api/refresh endpoint from AUTH.md

Answer (attempts=1, grounded=True):
According to AUTH.md, a client refreshes an access token by sending a POST
request to /api/refresh with the current refresh token. The server validates
the refresh token and returns a new access token.
```

---

### Guardrail — Out-of-Scope Query

**Input:** `Tell me a joke`

```
[Guardrail] This question appears to be outside the scope of developer documentation.
```

---

## Design Decisions

**Why extend DocuBot?**  
DocuBot had the right retrieval foundation but no reliability layer. Adding confidence scoring and guardrails directly addresses the main failure modes observed in Module 4: over-confident answers from bad retrieval, and ungrounded Gemini responses when snippets were irrelevant.

**Why a self-critique loop instead of a reranker?**  
A reranker would require an embedding model, adding a dependency and latency. The self-critique loop uses the same LLM already in the pipeline and keeps the system self-contained. The cost is one extra LLM call per query in agentic mode.

**Why IDF weighting over embeddings?**  
The system is designed to run without GPU or heavy dependencies. IDF scoring is deterministic, explainable, and fast. For a documentation corpus of 7 files it achieves high hit rates on direct terminology questions. Semantic similarity search would benefit paraphrase-heavy queries but is not necessary for this scale.

**Multi-source corpus trade-off:**  
Adding `custom_docs/` expands coverage but increases the risk of retrieval noise when more documents compete for the same query terms. The IDF weighting naturally penalises terms that appear across many files, partially mitigating this.

---

## Testing Summary

Running `python test_harness.py` with both `docs/` and `custom_docs/` loaded:

- **10/10 tests pass** across all cases
- Average confidence across all test cases: **0.45**
- HIGH confidence: 0 — MEDIUM: 6 — LOW: 4
- TC-07 (out-of-scope payment query) correctly returns no results and passes with confidence 0.00
- TC-09 and TC-10 (deployment, contributing) correctly route to `custom_docs/` files
- TC-05 ("users table fields") and TC-08 ("projects route") score LOW confidence because the IDF scorer returns intro paragraphs rather than the specific schema sections — the correct file is retrieved but the top paragraph is not the most specific one

---

## Reflection and Ethics

**Limitations and biases:**  
The IDF retrieval model cannot handle synonyms or paraphrased queries — if a developer asks "how do I log in" instead of "how do I authenticate," retrieval may miss relevant paragraphs. The corpus is synthetic and small; real-world documentation would have much noisier formatting. The self-critique LLM judge is the same model generating the answer, which creates a potential bias toward self-validation.

**Potential misuse:**  
A documentation assistant could be misused to answer questions about security-sensitive code patterns. The guardrails block obvious credential injection patterns, but a sufficiently obfuscated prompt could bypass them. Rate limiting and authentication would be required before deploying this publicly.

**Surprises during testing:**  
The self-critique step was more reliable than expected — in 90% of test cases it correctly identified whether an answer was grounded. The most surprising failure was when the LLM generated a grounded-looking answer that still contained one fabricated endpoint name not in any snippet; the word-overlap grounding check passed it because the surrounding text was genuinely retrieved.

**AI collaboration:**  
- **Helpful instance:** When designing the confidence scoring formula, using the LLM to suggest that "relative score gap" (top vs. median, not top vs. minimum) was a better discriminator than raw score magnitude — this improved confidence calibration noticeably.
- **Flawed instance:** The LLM initially suggested using cosine similarity between query and answer embeddings for the grounding check. This would require loading a sentence transformer model just for evaluation, adding significant overhead for marginal gain over the simpler word-overlap approach that was implemented instead.

---

## Loom Walkthrough -  screenshots

<img width="1459" height="769" alt="image" src="https://github.com/user-attachments/assets/1608784c-c4a5-49d2-ba5f-6173f6b7cc9a" />
<img width="1459" height="769" alt="image" src="https://github.com/user-attachments/assets/cc36867b-8d6b-4591-82a3-58cd1853c627" />
<img width="1459" height="769" alt="image" src="https://github.com/user-attachments/assets/6d1c0d50-e70c-4279-99f5-a920034d309c" />
<img width="680" height="361" alt="image" src="https://github.com/user-attachments/assets/331fc1e4-1e77-4748-b8af-4b3d217a545e" />
<img width="657" height="330" alt="image" src="https://github.com/user-attachments/assets/093b2a56-3847-498e-ad6b-668b46420fde" />
<img width="1462" height="814" alt="image" src="https://github.com/user-attachments/assets/59884419-8104-42f9-9e1e-5509ef45b107" />



---

## Requirements

- Python 3.9+
- Gemini API key (only needed for Modes 1, 3, and 4)
- No database, no server, no GPU required
