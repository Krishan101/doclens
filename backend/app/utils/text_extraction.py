import pdfplumber
import io
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    raw_text: str
    page_count: int
    tables: list[dict]  # {page, content_md}
    page_offsets: list[int]  # char offset where each page starts in raw_text
    is_image_only: bool
    error: str | None = None


def extract_text_from_pdf(file_bytes: bytes) -> ExtractionResult:
    """Extract text and tables from PDF using pdfplumber."""
    try:
        pages_text = []
        tables = []
        page_count = 0
        page_offsets = []
        current_offset = 0

        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            page_count = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                page_offsets.append(current_offset)

                # Extract tables first
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) > 1:
                        md = _table_to_markdown(table)
                        if md.strip():
                            tables.append({"page": i + 1, "content_md": md})

                # Extract text
                text = page.extract_text() or ""
                pages_text.append(text)
                current_offset += len(text) + 2  # +2 for "\n\n" separator

        raw_text = "\n\n".join(pages_text)

        # Check if image-only
        total_chars = sum(len(t.strip()) for t in pages_text)
        is_image_only = page_count > 0 and (total_chars / max(page_count, 1)) < 50

        return ExtractionResult(
            raw_text=raw_text,
            page_count=page_count,
            tables=tables,
            page_offsets=page_offsets,
            is_image_only=is_image_only,
        )

    except Exception as e:
        return ExtractionResult(
            raw_text="",
            page_count=0,
            tables=[],
            page_offsets=[],
            is_image_only=False,
            error=str(e),
        )


def extract_text_from_txt(file_bytes: bytes) -> ExtractionResult:
    """Extract text from a plain text file."""
    try:
        text = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
        except Exception as e:
            return ExtractionResult(raw_text="", page_count=0, tables=[], page_offsets=[], is_image_only=False, error=str(e))

    return ExtractionResult(
        raw_text=text,
        page_count=1,
        tables=[],
        page_offsets=[0],
        is_image_only=False,
    )


def _table_to_markdown(table: list[list]) -> str:
    """Convert a pdfplumber table to markdown format."""
    if not table or len(table) < 2:
        return ""

    # Clean cells
    cleaned = []
    for row in table:
        cleaned.append([str(cell).strip() if cell else "" for cell in row])

    # Build markdown
    header = "| " + " | ".join(cleaned[0]) + " |"
    separator = "| " + " | ".join(["---"] * len(cleaned[0])) + " |"
    rows = []
    for row in cleaned[1:]:
        # Pad row if needed
        while len(row) < len(cleaned[0]):
            row.append("")
        rows.append("| " + " | ".join(row[:len(cleaned[0])]) + " |")

    return "\n".join([header, separator] + rows)
