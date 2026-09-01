# Compass — Interview Brief

Everything you need to explain this project from scratch. Read sections 1, 2, 5
and 6 if you only have ten minutes.

---

## 1. The 30-second pitch

> "I built an internal policy assistant. Employees ask questions in plain
> language — 'how many leave days can I carry over?' — and it answers from the
> company's actual policy documents, with a citation on every claim that you can
> click and verify.
>
> The part I care about most is that it refuses. If the policy set doesn't cover
> the question, it says so instead of guessing, and that refusal gets logged as
> a content gap for the HR team to fix. So the failure mode of the system becomes
> its feedback loop."

If they only remember one sentence, make it the last one.

---

## 2. Why this product (the PM answer)

If asked *"why did you pick this?"*:

**It has two real users, not one.** An HR admin who owns the content, and an
employee who consumes it. That forced me to build an admin CRUD surface and an
end-user surface, which is more product than a single chat box.

**It has a believable business case.** HR fields the same 50 questions a week in
Slack. This deflects them and leaves an audit trail of what people actually ask.

**It has a real risk to design around.** An assistant that confidently invents an
answer about parental leave or expense limits is worse than no assistant —
that's a liability, not a bug. Designing for that risk is what makes it an
engineering problem rather than an API call.

---

## 3. The architecture

Two programs, talking over HTTP:

```
   Browser
      |
      v
   Next.js 15 frontend  (port 3000)
      |  fetch()
      v
   FastAPI backend      (port 8010)
      |
      +--> ChromaDB          vector index, on disk
      +--> JSON registry     document metadata + question log
      +--> Gemini / OpenAI   answer generation (optional)
```

**Stack and why:**

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | Next.js 15, TypeScript, Tailwind | App Router, typed end to end |
| Forms | react-hook-form + zod | Validation rules declared once, as a schema |
| Backend | FastAPI, Pydantic v2 | Types become the API contract and the docs |
| Vectors | ChromaDB | Local, no server to run, persists to disk |
| Orchestration | LangChain | Prompt templating and text splitting |
| Metadata | A single JSON file | No SQL to operate; correct for one process |

**Why no SQL database:** the constraint was to avoid one. The vector store owns
embeddings; a JSON file written atomically (temp file + rename, under a lock)
owns everything relational. For a few hundred policy chunks that's the right
size of solution. I know exactly where it breaks — see section 9.

---

## 4. What happens when someone asks a question

Learn this path. It's the most likely question you'll get.

```
question
   |
   1. RETRIEVE   hybrid search over published documents only
   |
   2. GATE       is the best match strong enough?
   |             no  -> refuse, log a coverage gap, STOP
   |             yes -> continue
   |
   3. GENERATE   LLM gets numbered excerpts, returns an answer
   |             plus which excerpt numbers it used
   |
   4. BIND       server attaches document title / section / page
   |             from the index, using those numbers
   |
   5. LOG        question, score, confidence, latency recorded
   |
   v
answer + citations
```

Code: [`backend/app/services/rag.py`](backend/app/services/rag.py)

**Step 4 is the one to emphasise.** The model never writes a source name. It
returns *indices* — `[1]`, `[2]` — and the server looks up the real metadata
from the index. A model cannot fabricate a citation it has no way to spell.
That is a structural guarantee, not a prompt instruction.

---

## 5. The three decisions that make it defensible

### Decision 1 — The grounding gate

Retrieval returns a similarity score. Below a calibrated floor (**0.48**), the
system returns `status: no_coverage` and refuses.

Refusing is a *first-class outcome*, not an error path. It has its own UI state,
its own colour, and its own place in the analytics.

### Decision 2 — Server-bound citations

Described above. The model picks *which* excerpts; the server says *what they
are*.

### Decision 3 — Refusals become the roadmap

Every refused question is logged, deduplicated, and ranked by frequency on the
Insights page. If eight people ask about sabbaticals this month and the
assistant declines every time, HR sees "sabbatical policy" at the top of a
content backlog.

**This is the answer to "so what happens when it doesn't know?"** — most RAG
demos have no answer to that. Yours turns it into the product loop.

---

## 6. The story to lead with

This is your strongest material. It shows engineering judgement, not just wiring.

**What happened:**

I demoed my own app and typed a normal question:

> `list total leaves available??`

It **refused**, scoring 0.20. The leave policy obviously covers this.

**How I diagnosed it — by measuring, not guessing:**

I ran the same intent through different phrasings:

| query | score |
| --- | --- |
| `total leave available` | **0.587** answered |
| `total leaves available` | **0.256** refused |

One letter. So I tested the embedding model directly on bare terms:

| term | similarity to the leave policy |
| --- | --- |
| `annual leave` | **0.699** |
| `annual leaves` | **0.231** |

**The root cause:** `all-MiniLM-L6-v2` reads "leaves" as the verb ("he leaves")
or foliage — not time off. And "leaves" is exactly how most people, especially
in Indian English, phrase it. My threshold had been calibrated only on
well-formed full sentences, so real phrasing fell straight through the gate.
That was my calibration gap, not a bad question.

**The fix — two parts:**

1. **Query normalisation.** The question is also embedded in a singularised
   form, and each chunk keeps the *best* similarity any variant achieved.
   Taking the maximum means normalisation can only rescue a query the model
   mishandles — it can never make a good question score worse.

2. **A lexical arm.** Dense embeddings are weak on morphology and rare terms, so
   I added an IDF-weighted measure of how much of the question's vocabulary
   literally appears in a chunk, over a stemmed index. Bounded to [0,1] so it
   shares the same relevance floor, and fused as
   `max(vector, 0.55·vector + 0.45·lexical)` — so it can only rescue a chunk
   dense retrieval under-ranked, never demote one it ranked well.

**The part that shows real rigour — I measured a regression and reverted:**

My first attempt at the lexical arm dropped unseen query terms from the IDF
denominator. It fixed the terse queries. But when I re-ran the full evaluation,
*"Do we offer a sabbatical after five years of service?"* had jumped from 0.42
to **0.63** — it was now being answered, purely on the incidental words "years"
and "service". Three new false positives.

So I reverted that half and kept the query normalisation. Keeping unseen terms
in the denominator costs some recall on very terse fragments, and that's the
right trade for a tool that must not invent entitlements.

**The result, measured on a 43-question evaluation set:**

| | dense only | hybrid |
| --- | --- | --- |
| In-policy answered | 24/36 | **36/36** |
| Out-of-policy refused | 7/7 | **7/7** |

**And the honest part — say this, don't hide it:**

> "The separation is tight. My lowest true positive scores 0.483 and my highest
> true negative 0.439 — a margin of 0.044. That's thin enough that the threshold
> has to be re-measured against any corpus or model change, not assumed to
> transfer. Adding documents changes IDF, so adding documents counts as a
> change."

Volunteering that is worth more than the fix itself.

---

## 7. Five-minute demo script

**Open on the refusal, not the answer.** Everyone demos a working answer.

1. **Ask something out of scope** — *"Do we offer a sabbatical after five years
   of service?"*
   It declines. Point at the score and the wording: it says it won't guess.

2. **Go to Insights.** That question is already sitting in the coverage-gap
   table, ranked by how often it's been asked.
   Say: *"The failure just became a content backlog item."*

3. **Now ask a real one** — *"How much parental leave does a secondary caregiver
   get?"*
   Answer appears. Click the `[1]` marker — it scrolls to the source card
   showing document, section 4, version, and the exact quote.

4. **Go to Knowledge Base.** Archive the Leave policy. Ask the same question
   again — it now refuses.
   Say: *"Retrieval is scoped to published documents. Archiving takes a policy
   out of circulation instantly without destroying it."*
   Republish it.

5. **Upload a document live.** Drag in a Markdown file, fill the form, submit.
   Watch it parse, chunk, embed, and become answerable in about a second.

**Backup if the UI misbehaves:** `http://localhost:8010/docs` — the
auto-generated API docs let you call every endpoint from the browser.

---

## 8. Likely questions and how to answer

**"How do you stop it hallucinating?"**
Three layers. Retrieval is scoped to published documents only. A relevance gate
refuses below a calibrated floor. And citations are bound server-side, so the
model returns indices and the server supplies the metadata — it can't invent a
source. Then add: the gate is calibrated by measurement, and I have an eval set
that proves it.

**"Why ChromaDB and not Pinecone/pgvector?"**
The brief said no heavy database and one day of work. Chroma is embedded, needs
no server, and persists to disk. I namespace collections by embedding model, so
switching providers can't silently mix incompatible vector spaces. At real scale
I'd move to pgvector to get transactional consistency between metadata and
vectors, which I don't have today.

**"How do you chunk?"**
Section-aware. I detect headings — markdown, numbered like `4.2`, labelled
`Section 3`, and block capitals — then group lines under the nearest heading
before splitting at 1100 characters with 160 overlap. Every chunk carries its
section and page. That's decided at ingestion because a chunk that doesn't know
its own section can never produce a verifiable citation.

**"What if the LLM API is down?"**
It degrades to extractive mode and says so. Answers are assembled from the
highest-overlap sentences in the retrieved chunks, citations still real, and the
response is labelled `extractive_fallback` end to end. `/api/health` reports the
mode and the UI shows it in the sidebar. The app is never a blank screen because
a vendor is down.

**"How would you add authentication?"**
SSO in front of both surfaces, a role check on the admin routes, and — the part
people forget — document-level access control pushed into the *retrieval filter*,
not just the UI. Retrieval already filters to published documents; that same
`where` clause is where an ACL belongs, so a user can never be cited a document
they aren't allowed to read.

**"How do you know it works?"**
`bash eval/run.sh` — 43 questions split into must-answer and must-refuse, plus a
`known_gaps.txt` of expected failures I deliberately kept visible rather than
deleted. I run it after any change to retrieval, chunking, or the corpus.

**"What was hardest?"**
The retrieval bug in section 6. Give the whole story: found it, measured it,
fixed it, measured a regression from my own fix, reverted the wrong half.

---

## 9. Limitations — state these before they find them

- **No authentication.** Both surfaces are open. Production needs SSO and an ACL
  in the retrieval filter.
- **Single process only.** The JSON registry is guarded by an in-process lock.
  Correct for one uvicorn worker, wrong for several — that needs Postgres or
  Redis.
- **No OCR.** A scanned PDF with no text layer is rejected with a clear error
  rather than indexed as empty.
- **Three known retrieval gaps**, tracked in `eval/known_gaps.txt`:
  `leaves balance` and `my remaining leaves` fail closed (refused — the safe
  direction); `what is the company policy on space travel` is answered at 0.53
  because it contains a genuinely covered topic word. Retrieval scoring can't
  separate business travel from space travel — only reading the excerpt can,
  which is what the model layer is for.
- **Tuned on one small corpus.** Seven documents, 99 chunks. The threshold and
  lexical weight are starting points, not universal constants.

---

## 10. What I'd build next

1. **Auth and document-level ACLs** in the retrieval filter.
2. **A better embedding model.** `text-embedding-004` would widen that 0.044
   margin considerably — and the eval harness is already there to prove it.
3. **Answer versioning.** When a policy is updated, show which previously-given
   answers are now stale.
4. **Slack integration**, so people ask where they already are instead of
   visiting a portal.
5. **Postgres for the registry**, to run more than one worker.

---

## 11. Facts you should have straight

| | |
| --- | --- |
| Documents seeded | 7, one per policy area |
| Chunks indexed | 99 |
| Relevance floor | 0.48 (calibrated, not guessed) |
| Lexical weight | 0.45 |
| Eval result | 36/36 answer, 7/7 refuse, 3 known gaps |
| Embedding model | `all-MiniLM-L6-v2`, runs locally |
| API port | 8010 (8000 was taken by Splunk) |
| Endpoints | 10 across 4 routers |
| Chunk size | 1100 chars, 160 overlap |

**Files worth opening if they ask to see code:**

- [`backend/app/services/rag.py`](backend/app/services/rag.py) — the pipeline and the gate
- [`backend/app/services/lexical.py`](backend/app/services/lexical.py) — the retrieval fix from section 6
- [`backend/app/services/ingestion.py`](backend/app/services/ingestion.py) — heading detection and chunking
- [`frontend/components/ask/AnswerPanel.tsx`](frontend/components/ask/AnswerPanel.tsx) — citation rendering

---

## One last thing

If you're unsure of an answer tomorrow, say what you measured and what you
didn't. "I measured that on seven documents; I don't know how it holds at seven
hundred" is a stronger answer than a confident guess — and it's the same
instinct the product itself is built on.
