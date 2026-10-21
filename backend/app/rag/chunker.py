from dataclasses import dataclass

from app.rag.loader import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    page_number: int | None


def chunk_pages(
    pages: list[ExtractedPage],
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[TextChunk]:
    if not 500 <= chunk_size <= 800:
        raise ValueError("chunk_size must be between 500 and 800")
    if not 80 <= overlap <= 120 or overlap >= chunk_size:
        raise ValueError("overlap must be between 80 and 120 and smaller than chunk_size")

    chunks: list[TextChunk] = []
    for page in pages:
        start = 0
        while start < len(page.content):
            end = min(start + chunk_size, len(page.content))
            if end < len(page.content):
                end = _find_breakpoint(page.content, start, end, chunk_size)
            content = page.content[start:end].strip()
            if content:
                chunks.append(
                    TextChunk(index=len(chunks), content=content, page_number=page.page_number)
                )
            if end >= len(page.content):
                break
            start = max(end - overlap, start + 1)
    return chunks


def _find_breakpoint(text: str, start: int, end: int, chunk_size: int) -> int:
    lower_bound = start + int(chunk_size * 0.7)
    for separator in ("\n", "。", "；", ";", "！", "？", " "):
        position = text.rfind(separator, lower_bound, end)
        if position >= lower_bound:
            return position + len(separator)
    return end
