from backend.rag.policy_rag import chunk_markdown


def test_policy_chunking():
    chunks = chunk_markdown(
        "# Booking Policy\n\n"
        "## Email\n\nAn email is required.\n\n"
        "## Duration\n\nThe default duration is 30 minutes."
    )

    assert chunks
    assert all(chunk.strip() for chunk in chunks)


def test_policy_documents_exist():
    from pathlib import Path

    policy_dir = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "rag"
        / "policies"
    )

    assert len(list(policy_dir.glob("*.md"))) >= 5
