"""PostgreSQL + pgvector RAG for appointment policies."""

import json
import os
from pathlib import Path

from openai import OpenAI
from sqlalchemy import text

from backend.database import SessionLocal


EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_SCORE_THRESHOLD = float(
    os.getenv("RAG_SCORE_THRESHOLD", "0.55")
)
RAG_ANSWER_MODEL = os.getenv(
    "RAG_ANSWER_MODEL",
    os.getenv("AGENT_MODEL", "gpt-4o-mini"),
)

EMBEDDING_DIMENSIONS = 1536

POLICY_DIR = (
    Path(__file__).resolve().parent / "policies"
)


SCHEMA_SQL = f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_chunks (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(255) NOT NULL,
    chunk_id VARCHAR(255) NOT NULL UNIQUE,
    content TEXT NOT NULL,
    embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_policy_chunks_embedding_hnsw
ON policy_chunks
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS ix_policy_chunks_source
ON policy_chunks (source);
"""


def ensure_schema() -> None:
    """Create the pgvector extension and policy table if permitted."""

    db = SessionLocal()
    try:
        for statement in SCHEMA_SQL.split(";"):
            statement = statement.strip()
            if statement:
                db.execute(text(statement))
        db.commit()
    finally:
        db.close()


def _client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENAI_API_KEY")
    )


def _embedding_text(embedding: list[float]) -> str:
    return json.dumps(embedding, separators=(",", ":"))


def chunk_markdown(
    content: str,
    max_chars: int = 1200,
) -> list[str]:
    """Split policy markdown into small section-aware chunks."""

    sections = []
    current = []

    for line in content.strip().splitlines():
        if line.startswith("#") and current:
            sections.append("\n".join(current).strip())
            current = []
        current.append(line)

    if current:
        sections.append("\n".join(current).strip())

    chunks: list[str] = []

    for section in sections:
        if not section:
            continue

        if len(section) <= max_chars:
            chunks.append(section)
            continue

        paragraphs = [
            p.strip()
            for p in section.split("\n\n")
            if p.strip()
        ]

        current_text = ""

        for paragraph in paragraphs:
            candidate = (
                paragraph
                if not current_text
                else f"{current_text}\n\n{paragraph}"
            )

            if len(candidate) <= max_chars:
                current_text = candidate
            else:
                if current_text:
                    chunks.append(current_text)
                current_text = paragraph

        if current_text:
            chunks.append(current_text)

    return chunks


def ingest_policies() -> int:
    """Embed policy markdown and upsert chunks into pgvector."""

    ensure_schema()

    client = _client()
    db = SessionLocal()
    count = 0

    try:
        for policy_file in sorted(POLICY_DIR.glob("*.md")):
            content = policy_file.read_text(
                encoding="utf-8"
            )

            chunks = chunk_markdown(content)

            for chunk_index, chunk in enumerate(chunks):
                chunk_id = (
                    f"{policy_file.stem}-{chunk_index}"
                )

                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=chunk,
                )

                embedding = response.data[0].embedding

                db.execute(
                    text(
                        """
                        INSERT INTO policy_chunks
                            (source, chunk_id, content, embedding, metadata)
                        VALUES
                            (:source, :chunk_id, :content,
                             CAST(:embedding AS vector),
                             CAST(:metadata AS jsonb))
                        ON CONFLICT (chunk_id)
                        DO UPDATE SET
                            source = EXCLUDED.source,
                            content = EXCLUDED.content,
                            embedding = EXCLUDED.embedding,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW()
                        """
                    ),
                    {
                        "source": policy_file.name,
                        "chunk_id": chunk_id,
                        "content": chunk,
                        "embedding": _embedding_text(embedding),
                        "metadata": json.dumps(
                            {
                                "source": policy_file.name,
                                "chunk_index": chunk_index,
                            }
                        ),
                    },
                )

                count += 1
                print(
                    f"Indexed {policy_file.name} "
                    f"chunk {chunk_index}"
                )

        db.commit()
        return count

    finally:
        db.close()


def retrieve_policy_chunks(
    query: str,
    top_k: int = RAG_TOP_K,
    score_threshold: float = RAG_SCORE_THRESHOLD,
) -> list[dict]:
    """Retrieve policy chunks using pgvector cosine distance."""

    ensure_schema()

    response = _client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )

    query_embedding = _embedding_text(
        response.data[0].embedding
    )

    db = SessionLocal()

    try:
        rows = db.execute(
            text(
                """
                SELECT
                    source,
                    chunk_id,
                    content,
                    1 - (
                        embedding <=> CAST(:embedding AS vector)
                    ) AS similarity
                FROM policy_chunks
                ORDER BY embedding <=> CAST(:embedding AS vector)
                LIMIT :top_k
                """
            ),
            {
                "embedding": query_embedding,
                "top_k": top_k,
            },
        ).mappings().all()

        return [
            {
                "source": row["source"],
                "chunk_id": row["chunk_id"],
                "text": row["content"],
                "score": float(row["similarity"]),
            }
            for row in rows
            if float(row["similarity"]) >= score_threshold
        ]

    finally:
        db.close()


def answer_policy_question(
    question: str,
) -> str | None:
    """Generate an answer grounded strictly in retrieved policies."""

    try:
        chunks = retrieve_policy_chunks(question)
    except Exception as exc:
        print("RAG RETRIEVAL ERROR:", str(exc))
        return None

    if not chunks:
        return (
            "I couldn't find that information in the "
            "available appointment policies."
        )

    context = "\n\n".join(
        f"SOURCE: {chunk['source']}\n{chunk['text']}"
        for chunk in chunks
    )

    prompt = f"""
You are a policy assistant for an appointment scheduling system.

Answer the user's question using ONLY the policy context below.

Rules:
- Do not invent policies, fees, refunds, exceptions, or requirements.
- If the answer is not explicitly supported by the context, say that
  the information is not available in the current policies.
- Do not perform calendar actions.
- Keep the answer concise and clear.

POLICY CONTEXT
==============
{context}

USER QUESTION
=============
{question}
"""

    response = _client().chat.completions.create(
        model=RAG_ANSWER_MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": prompt,
            }
        ],
    )

    return (
        response.choices[0].message.content or ""
    ).strip() or None
