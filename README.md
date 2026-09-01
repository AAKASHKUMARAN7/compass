# Compass — Internal Policy Intelligence

An internal tool that lets employees ask questions about company policy in plain
language, and answers them **only** from documents an HR administrator has
published — with a citation on every claim.

Two surfaces, two personas:

| Surface | Persona | What it does |
| --- | --- | --- |
| **Ask Compass** (`/`) | Employee | Asks a question, gets a grounded answer with inline citations they can open and verify. |
| **Knowledge Base** (`/admin`) | HR / Policy owner | Uploads, versions, publishes and archives the documents the assistant is allowed to use. |
| **Insights** (`/insights`) | HR / Policy owner | Usage, answer rate, and the questions the assistant could not answer — a ranked content backlog. |

---

## The seeded corpus

`python -m scripts.seed` loads seven policy documents, one per policy area, so
every filter in the UI has real content behind it:

| Document | Area | Owner |
| --- | --- | --- |
| Leave and Time Off Policy | Leave & Time Off | People Operations |
| Compensation Policy | Compensation | People Operations |
| Employee Benefits Policy | Benefits | People Operations |
| Expense and Travel Policy | Expenses & Travel | Finance |
| Information Security Policy | Security & IT | Information Security |
| Code of Conduct and Compliance Policy | Conduct & Compliance | Legal and Compliance |
| Workplace and Remote Work Policy | Workplace | Workplace Operations |

"Other" is a fallback bucket for uploads that do not fit an area, not a policy
area in its own right, so nothing is seeded against it.

---

## The design decision that matters

An assistant that confidently invents an answer about parental leave or expense
limits is worse than no assistant at all. Three mechanisms address that:

**1. A grounding gate.** Retrieval below a calibrated relevance floor returns
`status: no_coverage` and no answer. Refusing is a correct, first-class outcome,
not an error path.

**2. Server-bound citations.** The model is given numbered excerpts and returns
*indices*. Document title, section, page and version are attached server-side
from the index. The model has no way to spell a source, so it cannot fabricate
one.

**3. Refusals become the roadmap.** Every declined question is logged and
surfaced in Insights, ranked by frequency. The failure mode of a RAG system
becomes its content feedback loop.

The gate threshold is calibrated against the active embedding model rather than
guessed. Re-measure when changing embedding models — the absolute scale differs
per model. `eval/run.sh` is the regression harness for this.

## Retrieval is hybrid, because embeddings alone were not enough

The first version used dense retrieval only, and a real question broke it:

> *"list total leaves available"* → refused, score **0.20**

`all-MiniLM-L6-v2` scores `annual leave` at **0.70** against the leave policy but
`annual leaves` at **0.23** — the plural collides with the verb and foliage
senses. The threshold had been calibrated only on well-formed sentences, so
terse and pluralised phrasing (which is how people actually type) fell straight
through the gate. Two measured fixes:

**Query normalisation.** The question is also embedded in a singularised form,
and a chunk keeps the best similarity any variant achieved. Taking the maximum
means normalisation can only rescue a query the model mishandles — it can never
make a well-formed question score worse.

**A lexical arm.** An IDF-weighted measure of how much of the question's
vocabulary literally appears in a chunk, over a lightly stemmed index, bounded
to [0, 1] so it shares the same relevance floor. Fused as
`max(vector, (1-w)·vector + w·lexical)` with `w = LEXICAL_WEIGHT`, so the lexical
signal can only rescue a chunk that dense retrieval under-ranked, never demote
one it ranked well.

One thing measurement settled rather than intuition: unseen query terms are kept
in the IDF denominator. Dropping them rescued terse queries but let *"sabbatical
after five years of service"* score **0.63** on the incidental words "years" and
"service" alone — three false positives. Keeping them costs some recall on very
terse fragments and is the right trade for a tool that must not invent
entitlements.

Measured on `eval/run.sh` against the seeded corpus (7 documents, 99 chunks),
at a floor of **0.48**:

| | dense only | hybrid |
| --- | --- | --- |
| In-policy answered | 24/36 | **36/36** |
| Out-of-policy refused | 7/7 | **7/7** |

Three cases still fail and are tracked in `eval/known_gaps.txt` rather than
deleted, so the weakness stays visible:

- `leaves balance`, `my remaining leaves` — two-word fragments where the only
  other words ("balance", "remaining") appear nowhere in the corpus. They fail
  *closed*, which is the safe direction.
- `what is the company policy on space travel` — answered at 0.53, because the
  question contains a genuinely covered topic word. Retrieval scoring alone
  cannot separate business travel from space travel; only reading the excerpt
  can, which is the model layer's job.

Worth stating plainly: the separation is tight. The lowest true positive scores
0.483 and the highest true negative 0.439, a margin of 0.044. That is thin
enough that the floor must be re-measured against any corpus or model change
rather than assumed to transfer — adding documents changes IDF, so the corpus
counts as a change.

---

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, react-hook-form + zod |
| Backend | FastAPI, Pydantic v2, uvicorn |
| Vector store | ChromaDB (persistent, local) |
| Orchestration | LangChain (`ChatPromptTemplate`, `RecursiveCharacterTextSplitter`) |
| Models | Google Gemini or OpenAI, with a local embedding fallback |
| Storage | JSON registry with atomic writes — no SQL database to operate |

---

## Running it

Prerequisites: Python 3.11+, Node 18+.

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
copy .env.example .env          # cp on macOS / Linux
```

Add a `GOOGLE_API_KEY` to `.env` ([get one here](https://aistudio.google.com/apikey)).
The service also runs without a key — see *Degraded modes* below.

Seed the sample policies and some demo traffic:

```bash
python -m scripts.seed --demo-queries
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8010
```

- API: http://localhost:8010
- Interactive docs: http://localhost:8010/docs

> Port 8010 rather than 8000, because 8000 was already held by another service
> on the development machine. Change `PORT` in `.env` and
> `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` to move it.

### 2. Frontend

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev
```

Open http://localhost:3000.

`RUNNING.txt` is a plain-text runbook covering the same steps in more detail,
including troubleshooting, for anyone setting this up without the shortcuts.

`DEMO_QUESTIONS.md` holds 70 verified questions — ten per policy area, each
checked to return a citation to the correct section — plus the refusal set worth
demonstrating.

### 3. Checking retrieval quality

With the API seeded and running:

```bash
bash eval/run.sh
```

Prints a pass/fail line per question and a total. Run it after any change to
retrieval, chunking, or the relevance floor.

---

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Service status, resolved providers, index size |
| `POST` | `/api/documents` | Upload, parse, chunk, embed and publish a document |
| `GET` | `/api/documents` | List with status / category / search filters |
| `GET` | `/api/documents/{id}` | Detail, including indexed chunk previews |
| `PATCH` | `/api/documents/{id}/status` | Publish or archive |
| `DELETE` | `/api/documents/{id}` | Delete document and its embeddings |
| `POST` | `/api/chat/ask` | Ask a question, get a cited answer |
| `GET` | `/api/chat/history` | Audit trail of questions asked |
| `POST` | `/api/chat/{id}/feedback` | Record whether an answer was useful |
| `GET` | `/api/analytics/overview` | KPIs, coverage gaps, category breakdown |

Errors use a single envelope, with a request id that also appears in the logs:

```json
{
  "error": {
    "code": "unsupported_file_type",
    "message": "Unsupported file type: .exe",
    "detail": "Accepted formats are PDF, TXT and Markdown.",
    "request_id": "req_e28b322197b6"
  }
}
```

---

## How ingestion produces citable sources

Citation quality is decided at ingestion, not at answer time. A chunk that does
not know its own section can never produce a verifiable citation.

1. **Parse** — PDF via `pypdf` (page numbers retained), or text/Markdown.
2. **Detect headings** — Markdown (`## 2.1 Carryover`), numbered (`4.2 Generative AI Tools`),
   labelled (`Section 3 — Expenses`) and block-capital headings.
3. **Segment** — lines are grouped under the most recent heading.
4. **Split** — `RecursiveCharacterTextSplitter`, 1100 chars with 160 overlap,
   each chunk carrying its section and page.
5. **Embed and index** — batched into Chroma with document metadata attached.

The result is citations like *Information Security Policy — 4.2 Generative AI
Tools — v4.0*, rather than an undifferentiated page reference.

---

## Degraded modes

The application is designed to stay demonstrable when a provider is missing, and
to say so rather than pretend. `/api/health` reports the resolved mode, and the
sidebar shows it live.

| Condition | Behaviour |
| --- | --- |
| No LLM key | **Extractive mode** — answers are assembled from the highest-overlap sentences in retrieved chunks, still with real citations. Labelled `extractive` end to end. |
| LLM call fails at runtime | Falls back to extractive for that request, labelled `extractive_fallback`. |
| No embedding API key | Falls back to Chroma's bundled `all-MiniLM-L6-v2` ONNX model (local, no key). |
| No embedding model available at all | Deterministic hashed bag-of-words. Lexical recall only; reported as `hashing-fallback`. |

Collections are namespaced by embedding model, so switching providers cannot
silently mix incompatible vector spaces.

---

## Project layout

```
backend/
  app/
    main.py               ASGI app, request-id middleware, lifespan
    config.py             Typed settings, one source of truth
    dependencies.py       Composition root
    api/routes/           documents · chat · analytics · health
    core/                 logging, error envelope
    schemas/              Pydantic contracts
    services/
      ingestion.py        Parsing, heading detection, chunking
      embeddings.py       Provider resolution with fallbacks
      vectorstore.py      ChromaDB wrapper, filtered search
      llm.py              LangChain chain + extractive fallback
      rag.py              Retrieve → gate → generate → cite → log
      documents.py        Document lifecycle
      analytics.py        KPIs and coverage-gap ranking
      registry.py         Atomic JSON metadata store
      lexical.py          Query normalisation + IDF term index
  data/samples/           Seven realistic policy documents, one per area
  scripts/seed.py         Seeding and demo traffic

eval/
  run.sh                  Retrieval gate regression harness
  should_answer.txt       In-policy questions that must be answered
  should_refuse.txt       Out-of-policy questions that must be refused

frontend/
  app/                    /  ·  /admin  ·  /insights
  components/
    ask/                  Answer rendering, citations
    admin/                Upload form, document table
    layout/               Shell, live system status
    ui/                   Button, Badge, Card, Field, Toast
  lib/api.ts              Typed client, single error path
  types/api.ts            Contracts mirrored from the backend
```

---

## Known limitations

Scoped out deliberately for a one-day build:

- **No authentication.** Both surfaces are open. Production would need SSO plus
  a role check on the admin routes, and document-level access control in the
  retrieval filter.
- **Single-process storage.** The JSON registry is guarded by an in-process
  lock, which is correct for one uvicorn worker and wrong for several. Multiple
  workers need Postgres or Redis for the registry.
- **Scanned PDFs are rejected.** There is no OCR; a PDF with no text layer
  returns `empty_document` rather than failing silently.
- **No re-index on model change.** Switching embedding provider starts a new
  collection; existing documents need re-uploading.
- **The gate is retrieval-only in extractive mode.** Without an LLM key the
  gate is the sole defence, and retrieval scoring alone cannot tell that
  *"pet bereavement leave"* is not covered by a bereavement section written for
  family members — it scores in the answerable band and is answered at low
  confidence. With a key configured the model reads the excerpt and returns
  `answered: false`, which is precisely the second layer the design relies on.
  Raising the floor to cover this would reject legitimate questions in the same
  band; the fix is the model layer, not a stricter threshold.
- **Retrieval is tuned on one small corpus.** The floor, the lexical weight and
  the stopword list were measured against seven policy documents and 99 chunks.
  They are starting points, not universal constants.
- **`npm audit` reports a transitive `postcss` advisory** inside Next 15's own
  dependency tree. It affects the build toolchain, not the served application,
  and clearing it requires a Next 16 upgrade.
