-- Multimodal RAG schema for gemini-embedding-2 (1536-dim, Matryoshka-truncated).
--
-- Applied to the Supabase project via MCP as migration `enable_pgvector_and_rag_schema`.
-- Kept here so the database can be rebuilt from source.

create extension if not exists vector with schema extensions;

-- One row per source file under documents/.
create table public.documents (
  id uuid primary key default gen_random_uuid(),
  rel_path text not null unique,
  filename text not null,
  mime_type text not null,
  media_kind text not null check (media_kind in ('text','image','video','audio','pdf')),
  size_bytes bigint not null default 0,
  sha256 text not null,
  status text not null default 'pending' check (status in ('pending','processing','ready','error')),
  error text,
  chunk_count integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One row per embeddable unit. Every modality shares this table because
-- gemini-embedding-2 maps them all into the same vector space.
create table public.chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  chunk_index integer not null,
  modality text not null,
  content text not null default '',
  meta jsonb not null default '{}'::jsonb,
  embedding extensions.vector(1536) not null,
  created_at timestamptz not null default now(),
  unique (document_id, chunk_index)
);

create index chunks_document_id_idx on public.chunks (document_id);

-- 1536 dimensions fits pgvector's native 2000-dim HNSW limit, so no halfvec
-- casting is needed here.
create index chunks_embedding_hnsw_idx
  on public.chunks
  using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);

create index documents_status_idx on public.documents (status);
create index documents_media_kind_idx on public.documents (media_kind);

-- RLS on with no policies: anon/publishable keys are denied outright. The app
-- reaches the database only through its server-side service-role client.
alter table public.documents enable row level security;
alter table public.chunks enable row level security;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger documents_set_updated_at
  before update on public.documents
  for each row execute function public.set_updated_at();

-- Cosine similarity search across every modality, with optional media-kind filter.
create or replace function public.match_chunks(
  query_embedding extensions.vector(1536),
  match_count integer default 10,
  min_similarity double precision default 0.0,
  filter_kinds text[] default null
)
returns table (
  chunk_id uuid,
  document_id uuid,
  chunk_index integer,
  modality text,
  content text,
  meta jsonb,
  similarity double precision,
  filename text,
  rel_path text,
  mime_type text,
  media_kind text
)
language sql
stable
security invoker
set search_path = ''
as $$
  select
    c.id as chunk_id,
    c.document_id,
    c.chunk_index,
    c.modality,
    c.content,
    c.meta,
    1 - (c.embedding operator(extensions.<=>) query_embedding) as similarity,
    d.filename,
    d.rel_path,
    d.mime_type,
    d.media_kind
  from public.chunks c
  join public.documents d on d.id = c.document_id
  where (filter_kinds is null or d.media_kind = any(filter_kinds))
    and 1 - (c.embedding operator(extensions.<=>) query_embedding) >= min_similarity
  order by c.embedding operator(extensions.<=>) query_embedding
  limit match_count;
$$;
