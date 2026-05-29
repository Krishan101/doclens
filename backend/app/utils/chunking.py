from dataclasses import dataclass


@dataclass
class ChunkData:
    content: str
    chunk_type: str      # "text" or "table"
    chunk_index: int
    page_number: int | None
    char_start: int
    char_end: int
    token_count: int


def chunk_text(
    raw_text: str,
    tables: list[dict],
    chunk_size: int = 2048,      # ~512 tokens in chars
    chunk_overlap: int = 200,     # ~50 tokens in chars
    page_breaks: list[int] | None = None,
) -> list[ChunkData]:
    """
    Split document text into chunks with character offsets.
    Tables are treated as atomic chunks (never split).
    """
    chunks: list[ChunkData] = []
    chunk_index = 0

    # Add table chunks first (atomic, not split)
    table_texts_added = set()
    for table in tables:
        content = table["content_md"]
        if content in table_texts_added:
            continue
        table_texts_added.add(content)

        # Find table position in raw text (approximate)
        # Tables might not appear verbatim in raw_text, so we use page info
        chunks.append(ChunkData(
            content=content,
            chunk_type="table",
            chunk_index=chunk_index,
            page_number=table.get("page"),
            char_start=0,
            char_end=0,
            token_count=len(content.split()),
        ))
        chunk_index += 1

    # Split remaining text into chunks
    if not raw_text.strip():
        return chunks

    separators = ["\n\n", "\n", ". ", " "]
    text_chunks = _recursive_split(raw_text, separators, chunk_size, chunk_overlap)

    for text, start, end in text_chunks:
        if not text.strip():
            continue

        # Estimate page number from character position
        page_num = _estimate_page(start, raw_text)

        chunks.append(ChunkData(
            content=text.strip(),
            chunk_type="text",
            chunk_index=chunk_index,
            page_number=page_num,
            char_start=start,
            char_end=end,
            token_count=len(text.split()),
        ))
        chunk_index += 1

    return chunks


def _recursive_split(
    text: str,
    separators: list[str],
    chunk_size: int,
    overlap: int,
) -> list[tuple[str, int, int]]:
    """Split text recursively, tracking character offsets."""
    if len(text) <= chunk_size:
        return [(text, 0, len(text))]

    # Find the best separator
    sep = separators[0] if separators else " "
    for s in separators:
        if s in text:
            sep = s
            break

    parts = text.split(sep)
    results = []
    current_chunk = ""
    current_start = 0
    pos = 0

    for i, part in enumerate(parts):
        part_with_sep = part + (sep if i < len(parts) - 1 else "")

        if len(current_chunk) + len(part_with_sep) > chunk_size and current_chunk:
            results.append((current_chunk, current_start, current_start + len(current_chunk)))

            # Calculate overlap start
            overlap_text = current_chunk[-overlap:] if overlap > 0 else ""
            current_start = current_start + len(current_chunk) - len(overlap_text)
            current_chunk = overlap_text + part_with_sep
        else:
            if not current_chunk:
                current_start = pos
            current_chunk += part_with_sep

        pos += len(part_with_sep)

    if current_chunk.strip():
        results.append((current_chunk, current_start, current_start + len(current_chunk)))

    return results


def _estimate_page(char_pos: int, raw_text: str) -> int:
    """Estimate page number from character position (pages separated by double newlines)."""
    # Simple heuristic: count double-newline-separated blocks before this position
    prefix = raw_text[:char_pos]
    pages = prefix.count("\n\n") // 3 + 1  # rough: ~3 paragraphs per page
    return max(1, pages)
