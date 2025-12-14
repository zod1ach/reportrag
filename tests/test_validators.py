"""Tests for evidence validators."""

from app.services.validators import validate_evidence_quote


def test_validate_exact_match():
    """Test validation with exact match."""
    chunk_text = "This is a test chunk with some content."
    quote = "test chunk"
    start = 10
    end = 20

    assert validate_evidence_quote(chunk_text, quote, start, end)


def test_validate_mismatch():
    """Test validation with mismatched quote."""
    chunk_text = "This is a test chunk."
    quote = "wrong text"
    start = 0
    end = 10

    assert not validate_evidence_quote(chunk_text, quote, start, end)


def test_validate_out_of_bounds():
    """Test validation with out of bounds offsets."""
    chunk_text = "Short text."
    quote = "text"
    start = 100
    end = 104

    assert not validate_evidence_quote(chunk_text, quote, start, end)


def test_validate_invalid_range():
    """Test validation with invalid range."""
    chunk_text = "Some text."
    quote = "text"
    start = 5
    end = 2

    assert not validate_evidence_quote(chunk_text, quote, start, end)
