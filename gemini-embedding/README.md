# Multimodal RAG — Gemini Embedding 2 + Supabase + OpenAI Codex

A local RAG application that indexes **text, images, audio, video and PDFs** into a
single shared vector space using Google's `gemini-embedding-2`, stores the vectors in
**Supabase / pgvector**, and answers questions over the retrieved passages with an
**OpenAI Codex-line model** (`gpt-5.6-terra`) on the Responses API.

Because `gemini-embedding-2` is natively multimodal, every modality lands in the *same*
embedding space — so a plain text question can retrieve a photo, a slice of a video, or
a page range of a PDF.

```
documents/  ──▶  chunker  ──▶  gemini-embedding-2  ──▶  Supabase pgvector
                                                              │
                     question ──▶ gemini-embedding-2 ──▶ match_chunks
                                                              │
                                                    gpt-5.6-terra ──▶ answer + citations
```

---

## 1. Setup

### 1.1 Install

```bash
npm install
```

`ffmpeg` ships with the project via `ffmpeg-static` — nothing to install system-wide.

### 1.2 Configure secrets

```bash
cp .env.example .env.local
```

Then fill in `.env.local`:

| Variable | Where to get it |
| --- | --- |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `SUPABASE_URL` | Supabase dashboard → Project Settings → Data API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase dashboard → Project Settings → API Keys → `service_role` (secret) |

`.env.local` is gitignored by the existing `.env*` rule. **No key is ever sent to the
browser** — every secret is read inside server-only modules (`src/lib/*` all start with
`import "server-only"`, so an accidental client import is a build error), and the browser
only ever calls this app's own `/api/*` routes.

Run `npm run check:secrets` at any time to verify nothing credential-shaped has been
committed.

### 1.3 Database

The schema is already applied to the Supabase project. To recreate it elsewhere, apply
`supabase/migrations/0001_rag_schema.sql`. It creates:

- `documents` — one row per source file (path, media kind, sha256, status, chunk count)
- `chunks` — one row per embeddable unit, with `embedding vector(1536)` and an HNSW
  cosine index
- `match_chunks(...)` — the similarity-search function used by the app
- RLS enabled on both tables **with no policies**, so anon/publishable keys are denied
  outright; only the server's service-role key can read or write.

### 1.4 Run

```bash
npm run dev      # http://localhost:3000
```

---

## 2. Where to put your documents

**Put files in the `documents/` folder at the repo root.** Subfolders are fine and are
preserved as part of the document's identity.

There are two equivalent ways to get them there:

1. **Drag and drop onto the GUI** — the upload zone in the left sidebar writes straight
   into `documents/`.
2. **Copy them in yourself** — `cp ~/whatever.pdf documents/`, then click **Rescan** in
   the GUI (or just run `npm run ingest`).

The folder is the single source of truth. The `documents` table is reconciled against it
on every scan: new files appear as `pending`, edited files (changed SHA-256) are reset to
`pending` and their stale vectors dropped, and files you delete from disk have their rows
and vectors removed automatically.

`documents/` contents are gitignored, so nothing you index gets committed.

### Supported formats

| Kind | Extensions |
| --- | --- |
| text | `.txt .md .csv .json .jsonl .yaml .html .xml .log` and common source-code extensions |
| image | `.png .jpg .jpeg .webp .gif` (PNG and JPEG are the formats the model documents explicitly) |
| audio | `.mp3 .wav .m4a .aac .ogg .flac` |
| video | `.mp4 .mov .webm .mkv .avi` |
| pdf | `.pdf` |

Anything else is recorded with `status = error` and a message saying why, rather than
being silently ignored.

---

## 3. How documents are processed and embedded

Trigger it from the GUI's **Embed** button, or headlessly:

```bash
npm run ingest              # embed everything pending
npm run ingest -- --force   # drop all vectors and re-embed from scratch
```

### 3.1 Chunking

`gemini-embedding-2` has hard per-request limits, and those limits *are* the chunking
strategy:

| Modality | Model limit per request | How the app splits |
| --- | --- | --- |
| Text | 8,192 tokens | ~1,200-token windows with 15% overlap, broken on paragraph → sentence → whitespace boundaries |
| Images | 6 per request | one image = one chunk |
| Video | 120 s | ffmpeg segment muxer cuts ~115 s clips; mp4/mov are stream-copied, other containers transcoded to H.264/AAC |
| Audio | 180 s | ffmpeg cuts ~175 s segments; mp3/wav stream-copied, others transcoded to mp3 |
| PDF | 1 file, 6 pages | `pdf-lib` slices the document into 6-page PDFs, each embedded **natively as a PDF** so the model sees page layout, not just text |

For video and audio the exact start/end timestamp of every segment comes from ffmpeg's
own segment list, so the GUI can seek the preview player straight to the matching moment.

A stream copy can only cut on keyframes, so a file with a long GOP can produce a segment
*longer* than the model's cap — which the model would silently truncate, dropping the tail
of the clip from the index. The pipeline therefore targets 5 s under the cap, measures the
real segment lengths afterwards, and if any still overshoots it re-runs that file with a
transcode that pins a keyframe at every boundary. Segment lengths are guaranteed under the
cap or the document fails loudly.
For PDFs, `unpdf` extracts a text layer alongside the visual embedding — purely so results
are readable and so the reasoning model has something to quote.

### 3.2 Task prefixes

Unlike `gemini-embedding-001`, `gemini-embedding-2` has **no `task_type` parameter**. Task
intent is expressed as a text prefix instead, and the same convention has to be applied on
both sides:

- indexing: `title: {rel_path} | text: {content}`
- querying: `task: question answering | query: {question}`

For media chunks that prefix is sent as a text part *alongside* the media in one `contents`
array. The model aggregates a single `parts` array into one vector, so the filename and
segment position get folded into the same embedding as the pixels or audio.

### 3.3 Embedding

Each chunk becomes one `embedContent` call with `outputDimensionality: 1536` (Matryoshka
truncation of the model's native 3,072 — Google's recommended efficiency point, and inside
pgvector's 2,000-dimension native HNSW limit). Segments under 15 MB go inline as base64;
larger ones are uploaded via the Files API and deleted afterwards. Requests run three at a
time with exponential backoff on 429/5xx.

### 3.4 What lands in the database

- `documents` gets one row per file with `status` moving `pending → processing → ready`
  (or `error`, with the message shown in the GUI) and a final `chunk_count`.
- `chunks` gets one row per chunk: `modality`, a displayable `content` string, `meta`
  (`page_start`/`page_end`, `start_sec`/`end_sec`, `char_start`/`char_end`), and the
  1536-dim `embedding`.

Re-running ingestion is cheap: files whose SHA-256 is unchanged and whose status is
`ready` are skipped entirely.

---

## 4. How to run queries

### 4.1 In the GUI

Type a question in the query panel and hit **Search** (or Ctrl+Enter). You can tune:

- **Results** — how many passages to retrieve (top-K)
- **Min similarity** — drop weak matches
- **Filter** — restrict to certain media kinds (`pdf`, `image`, …)
- **Reasoning effort** — `low` / `medium` / `high` / `xhigh` for the Codex model
- **+ image query** — attach an image and search *by* it instead of by text
  (cross-modal retrieval: the image is embedded into the same space)

Results appear as the model's answer with clickable `[n]` citations, followed by the
retrieved passages — each with its similarity score and a modality-appropriate preview
(inline image, video/audio player seeked to the segment, PDF link opening at the right
page, or the text snippet).

### 4.2 From the command line

```bash
npm run query -- "what does the contract say about termination?"
npm run query -- "show me the diagram of the pipeline" --kinds=image --top-k=5
npm run query -- "summarise the demo video" --min=0.3 --raw   # retrieval only, no LLM call
```

### 4.3 Directly against the database

`match_chunks` is a normal Postgres function — anything that can reach the database can
query it:

```sql
select rel_path, media_kind, meta, similarity, left(content, 200)
from match_chunks(
  query_embedding := $1,      -- a 1536-dim vector from gemini-embedding-2
  match_count      := 10,
  min_similarity   := 0.25,
  filter_kinds     := array['pdf','image']   -- or null for everything
);
```

Note the embedding must come from the same model, at the same dimensionality, with the
`task: question answering | query: ...` prefix — otherwise the vectors are not comparable.

---

## 5. Project layout

```
documents/                  your source files (gitignored)
supabase/migrations/        the SQL schema
src/lib/
  env.ts                    server-only, zod-validated configuration
  supabase.ts               service-role client
  gemini.ts                 embedContent wrapper: prefixes, dimensions, Files API, retries
  openai.ts                 Responses API call + the answer prompt
  retrieve.ts               embed question -> match_chunks
  media.ts                  file-type classification + the model's per-request limits
  paths.ts                  documents-folder path resolution (traversal-guarded)
  ingest/                   scanner, chunkers (text/pdf/media), orchestrator
src/app/api/                upload, ingest (SSE), documents, query, file serving
src/components/             the GUI
scripts/                    ingest / query CLIs, secret checker
```

## 6. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Invalid environment configuration` | `.env.local` is missing or incomplete — compare against `.env.example` |
| A document sits in `error` with `ffmpeg exited with code ...` | The container or codec is unreadable; re-encode to mp4/mp3 and re-upload |
| `Expected 1536-dim embedding, got N` | `EMBEDDING_DIMENSIONS` no longer matches the `vector(N)` column — change it back or write a new migration |
| Queries return nothing | Lower **Min similarity**, clear the media-kind filter, and confirm documents show `ready` with a chunk count |
| Retrieval quality feels off after changing `EMBEDDING_DIMENSIONS` or the prefixes | Run `npm run ingest -- --force`; old vectors are not comparable to new ones |
