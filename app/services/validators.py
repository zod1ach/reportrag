"""Evidence validation functions."""


def validate_evidence_quote(chunk_text: str, quote: str, start: int, end: int) -> bool:
    """
    Validate that a quote is an exact substring at the specified offsets.

    Args:
        chunk_text: The full chunk text
        quote: The quoted text to validate
        start: Start offset in chunk_text
        end: End offset in chunk_text

    Returns:
        True if quote matches exactly, False otherwise
    """
    if start < 0 or end > len(chunk_text) or start >= end:
        return False

    extracted = chunk_text[start:end]
    return extracted == quote


def generate_corrective_prompt(
    chunk_text: str, failed_quote: str, node_title: str
) -> str:
    """
    Generate a corrective prompt for evidence extraction retry.

    Args:
        chunk_text: The chunk text
        failed_quote: The quote that failed validation
        node_title: The node title for context

    Returns:
        Corrective prompt string
    """
    prompt = f"""VALIDATION ERROR: The previous quote was not an exact substring of the chunk text.

Failed quote:
{failed_quote[:200]}...

This quote MUST be corrected. Please extract evidence for "{node_title}" again from the following chunk.

CRITICAL REQUIREMENTS:
1. Quotes must be EXACT verbatim substrings
2. Do NOT paraphrase or modify the text
3. Character offsets must point to the exact location in the chunk
4. Test: chunk_text[start:end] must equal the quote exactly

Chunk text:
{chunk_text[:2000]}...

Return ONLY corrected evidence in JSON format:
{{"ev_id": "...", "chunk_pk": ..., "quote": "...", "start_in_chunk": ..., "end_in_chunk": ..., "tag": "..."}}
"""
    return prompt
