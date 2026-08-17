"""Create/update the pgvector policy index.

Run from the project root:

    python scripts/build_policy_index.py

The script creates the pgvector schema and upserts embeddings for all
Markdown files in backend/rag/policies.
"""

from backend.rag.policy_rag import ingest_policies


if __name__ == "__main__":
    count = ingest_policies()
    print(f"\nIndexed {count} policy chunks into PostgreSQL/pgvector.")
