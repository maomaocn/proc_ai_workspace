import pytest

from app.core.errors import AppError
from app.rag.chunker import chunk_pages
from app.rag.embedding import MockHashEmbeddingProvider
from app.rag.loader import extract_pages, validate_file


def test_text_loader_and_chunker_preserve_page_number() -> None:
    content = ("采购制度要求申请人说明用途、数量和预算。" * 80).encode()
    filename, mime_type = validate_file("制度.md", "text/markdown", content, 1024 * 1024)
    pages = extract_pages(filename, content)
    chunks = chunk_pages(pages, chunk_size=500, overlap=80)

    assert mime_type == "text/markdown"
    assert len(chunks) > 1
    assert all(chunk.page_number == 1 for chunk in chunks)
    assert all(0 < len(chunk.content) <= 500 for chunk in chunks)
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize(
    ("filename", "mime_type", "content", "expected_code"),
    [
        ("payload.exe", "application/octet-stream", b"unsafe", "UNSUPPORTED_MEDIA_TYPE"),
        ("fake.pdf", "application/pdf", b"not a pdf", "UNSUPPORTED_MEDIA_TYPE"),
        ("empty.txt", "text/plain", b"", "VALIDATION_ERROR"),
        ("large.txt", "text/plain", b"x" * 11, "FILE_TOO_LARGE"),
    ],
)
def test_file_validation_rejects_unsafe_uploads(
    filename: str,
    mime_type: str,
    content: bytes,
    expected_code: str,
) -> None:
    with pytest.raises(AppError) as error:
        validate_file(filename, mime_type, content, max_bytes=10)

    assert error.value.code == expected_code


@pytest.mark.asyncio
async def test_mock_embeddings_are_reproducible_and_keyword_sensitive() -> None:
    provider = MockHashEmbeddingProvider(dimensions=256)

    first = await provider.embed_query("笔记本审批额度")
    second = await provider.embed_query("笔记本审批额度")
    related = await provider.embed_query("笔记本需要财务审批")
    unrelated = await provider.embed_query("员工食堂菜单")

    assert first == second
    related_score = sum(left * right for left, right in zip(first, related, strict=True))
    unrelated_score = sum(left * right for left, right in zip(first, unrelated, strict=True))
    assert related_score > unrelated_score


def test_invalid_utf8_text_is_rejected() -> None:
    with pytest.raises(AppError) as error:
        extract_pages("制度.txt", b"\xff\xfe")

    assert error.value.code == "DOCUMENT_PARSE_FAILED"
