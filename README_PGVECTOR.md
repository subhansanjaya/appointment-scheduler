# PostgreSQL + pgvector RAG

## Install

```bash
pip install pgvector
```

Add `pgvector` to the project's `requirements.txt`.

## Enable the extension

Run once against the application's PostgreSQL database:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

The ingestion code also attempts this automatically, but production databases
may require a database administrator to enable extensions.

## Build the policy index

```bash
python scripts/build_policy_index.py
```

This creates/upserts `policy_chunks`, stores `text-embedding-3-small`
embeddings, and creates an HNSW cosine index.

## Environment variables

```env
RAG_EMBEDDING_MODEL=text-embedding-3-small
RAG_TOP_K=4
RAG_SCORE_THRESHOLD=0.55
RAG_ANSWER_MODEL=gpt-4o-mini
```

The existing `OPENAI_API_KEY` and `SessionLocal` database configuration are reused.

## Test

```bash
python -m pytest -q
```

Then test:

- What is the cancellation policy?
- Can I reschedule an appointment?
- Is an email required to book?
- What is the default appointment duration?
- Do you give refunds for cancelled appointments?

The last question should not invent a refund policy.
