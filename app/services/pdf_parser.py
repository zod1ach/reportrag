"""PDF parsing service."""

import io
import logging
from typing import Union

from pypdf import PdfReader

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_content: Union[bytes, io.BytesIO]) -> str:
    """
    Extract text from a PDF file.

    Args:
        pdf_content: PDF file content as bytes or BytesIO

    Returns:
        Extracted text as string

    Raises:
        ValueError: If PDF cannot be parsed
    """
    try:
        # Convert bytes to BytesIO if needed
        if isinstance(pdf_content, bytes):
            pdf_file = io.BytesIO(pdf_content)
        else:
            pdf_file = pdf_content

        # Read PDF
        reader = PdfReader(pdf_file)

        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text()
                if text.strip():
                    text_parts.append(text)
                    logger.debug(f"Extracted {len(text)} characters from page {page_num}")
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num}: {e}")
                continue

        if not text_parts:
            raise ValueError("No text could be extracted from PDF")

        full_text = "\n\n".join(text_parts)
        logger.info(f"Successfully extracted {len(full_text)} characters from {len(reader.pages)} pages")

        return full_text

    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        raise ValueError(f"Failed to parse PDF: {str(e)}")
