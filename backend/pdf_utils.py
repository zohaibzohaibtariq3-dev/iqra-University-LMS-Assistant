"""PDF text extraction with PyMuPDF."""
import pymupdf  # PyMuPDF

MAX_CHARS = 400_000  # safety cap per document


def extract_text(data: bytes):
    """Return (text, page_count). Raises ValueError with a friendly message."""
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception:
        raise ValueError("This file could not be read as a PDF.")
    with doc:
        if doc.needs_pass:
            raise ValueError("This PDF is password protected. Remove the password and try again.")
        parts = []
        for number, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                parts.append(f"[Page {number}]\n{text}")
        pages = doc.page_count
    text = "\n\n".join(parts)
    if not text.strip():
        raise ValueError(
            "No text found. This looks like a scanned PDF (images only), which is not supported."
        )
    return text[:MAX_CHARS], pages
