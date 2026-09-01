"""Document parsing and section-aware chunking.

Citation quality is decided here, not at answer time. A chunk that does not
know which section and page it came from can never produce a verifiable
citation, so heading structure is detected during parsing and carried through
as chunk metadata.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.errors import EmptyDocumentError, UnsupportedFileType
from app.core.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
}

# "3.2 Paid Time Off", "Section 4 - Expenses", "ARTICLE II", "## Benefits"
_NUMBERED_HEADING = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+([A-Z][^\n]{2,90})$")
_LABELLED_HEADING = re.compile(
    r"^\s*(?:SECTION|Section|ARTICLE|Article|APPENDIX|Appendix)\s+([\w.\-]+)\s*[:\-–]?\s*(.*)$"
)
_MARKDOWN_HEADING = re.compile(r"^\s{0,3}(#{1,4})\s+(.+?)\s*#*\s*$")
_UPPER_HEADING = re.compile(r"^\s*([A-Z][A-Z0-9 &/,'()\-]{4,70})\s*$")


@dataclass
class ParsedPage:
    number: int | None
    text: str


@dataclass
class ParsedDocument:
    pages: list[ParsedPage]
    page_count: int | None
    word_count: int


@dataclass
class Chunk:
    ordinal: int
    text: str
    section: str | None
    page: int | None


@dataclass
class ChunkedDocument:
    chunks: list[Chunk]
    sections: list[tuple[str, int]] = field(default_factory=list)


def validate_upload(filename: str, content_type: str | None) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            "Unsupported file type: " + (suffix or "unknown"),
            detail="Accepted formats are PDF, TXT and Markdown.",
        )
    if content_type and content_type.split(";")[0].strip() not in SUPPORTED_CONTENT_TYPES:
        logger.info("upload_content_type_unexpected value=%s", content_type)
    return suffix


def parse_document(payload: bytes, suffix: str) -> ParsedDocument:
    if suffix == ".pdf":
        parsed = _parse_pdf(payload)
    else:
        parsed = _parse_text(payload)

    if parsed.word_count == 0:
        raise EmptyDocumentError(
            "No extractable text found in the document.",
            detail="Scanned PDFs without an OCR text layer are not supported.",
        )
    return parsed


def _parse_pdf(payload: bytes) -> ParsedDocument:
    from io import BytesIO

    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(payload))
    except Exception as exc:  # pragma: no cover - depends on the uploaded file
        raise EmptyDocumentError("The PDF could not be read.", detail=str(exc)) from exc

    pages: list[ParsedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = _normalise_whitespace(text)
        if cleaned:
            pages.append(ParsedPage(number=index, text=cleaned))

    word_count = sum(len(page.text.split()) for page in pages)
    return ParsedDocument(pages=pages, page_count=len(reader.pages), word_count=word_count)


def _parse_text(payload: bytes) -> ParsedDocument:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = payload.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 accepts any byte sequence
        raise EmptyDocumentError("The file could not be decoded as text.")

    cleaned = _normalise_whitespace(text)
    return ParsedDocument(
        pages=[ParsedPage(number=None, text=cleaned)],
        page_count=None,
        word_count=len(cleaned.split()),
    )


def _normalise_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_heading(line: str) -> str | None:
    """Return a normalised section label when the line looks like a heading."""
    stripped = line.strip()
    if not stripped or len(stripped) > 110:
        return None

    match = _MARKDOWN_HEADING.match(stripped)
    if match:
        return match.group(2).strip()

    match = _LABELLED_HEADING.match(stripped)
    if match and match.group(2).strip():
        return f"Section {match.group(1)} {match.group(2)}".strip()

    match = _NUMBERED_HEADING.match(stripped)
    if match and not stripped.endswith((".", ";", ",")):
        return f"{match.group(1)} {match.group(2)}".strip()

    match = _UPPER_HEADING.match(stripped)
    if match and len(stripped.split()) <= 10:
        title = match.group(1).strip()
        return title.title() if title.isupper() else title

    return None


def chunk_document(
    parsed: ParsedDocument,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> ChunkedDocument:
    """Split into overlapping chunks while preserving heading and page context."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""],
        length_function=len,
    )

    chunks: list[Chunk] = []
    section_counts: dict[str, int] = {}
    ordinal = 0

    for page in parsed.pages:
        for block_text, section in _segment_by_section(page.text):
            for piece in splitter.split_text(block_text):
                body = piece.strip()
                if len(body) < 40:
                    continue
                chunks.append(
                    Chunk(ordinal=ordinal, text=body, section=section, page=page.number)
                )
                ordinal += 1
                if section:
                    section_counts[section] = section_counts.get(section, 0) + 1

    if not chunks:
        raise EmptyDocumentError("The document produced no indexable content.")

    sections = sorted(section_counts.items(), key=lambda item: item[1], reverse=True)
    return ChunkedDocument(chunks=chunks, sections=sections)


def _segment_by_section(text: str) -> list[tuple[str, str | None]]:
    """Group consecutive lines under the most recent detected heading."""
    segments: list[tuple[str, str | None]] = []
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            body = "\n".join(buffer).strip()
            if body:
                segments.append((body, current_section))
            buffer.clear()

    for line in text.split("\n"):
        heading = detect_heading(line)
        if heading:
            flush()
            current_section = heading
            # Keep the heading inside the body so retrieval can match on it.
            buffer.append(line.strip())
            continue
        buffer.append(line)

    flush()
    return segments or [(text, None)]
