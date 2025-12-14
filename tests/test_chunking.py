"""Tests for chunking service."""

from app.services.chunking import chunk_document


def test_chunk_document():
    """Test basic document chunking."""
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    doc_id = "test-doc-123"

    chunks = chunk_document(text, doc_id)

    assert len(chunks) > 0
    assert chunks[0].chunk_index == 0
    assert chunks[0].chunk_id == f"{doc_id}::0"
    assert chunks[0].char_start == 0


def test_chunk_hash_consistency():
    """Test that identical chunks produce identical hashes."""
    text = "Same text.\n\nSame text."
    doc_id = "test-doc"

    chunks1 = chunk_document(text, doc_id)
    chunks2 = chunk_document(text, doc_id)

    assert chunks1[0].text_hash == chunks2[0].text_hash


def test_chunk_token_estimation():
    """Test token estimation."""
    text = "Short text."
    doc_id = "test-doc"

    chunks = chunk_document(text, doc_id)

    assert chunks[0].token_estimate > 0
    assert chunks[0].token_estimate == len(text) // 4
