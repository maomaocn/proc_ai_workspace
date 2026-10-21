from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.core.errors import AppError

SUPPORTED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
    ".md": {"text/markdown", "text/plain", "application/octet-stream"},
}


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    content: str


def normalize_filename(filename: str | None) -> str:
    if not filename or "\x00" in filename:
        raise AppError(400, "VALIDATION_ERROR", "文件名无效")
    normalized = Path(filename).name.strip()
    if not normalized or len(normalized) > 255:
        raise AppError(400, "VALIDATION_ERROR", "文件名无效")
    return normalized


def validate_file(
    filename: str | None,
    content_type: str | None,
    content: bytes,
    max_bytes: int,
) -> tuple[str, str]:
    normalized_name = normalize_filename(filename)
    extension = Path(normalized_name).suffix.lower()
    allowed_mime_types = SUPPORTED_TYPES.get(extension)
    if allowed_mime_types is None:
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "仅支持 PDF、TXT 和 MD 文件")

    mime_type = (content_type or "application/octet-stream").split(";", maxsplit=1)[0].lower()
    if mime_type not in allowed_mime_types:
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "文件扩展名与 MIME 类型不匹配")
    if not content:
        raise AppError(400, "VALIDATION_ERROR", "上传文件不能为空")
    if len(content) > max_bytes:
        raise AppError(
            413,
            "FILE_TOO_LARGE",
            f"文件大小不能超过 {max_bytes // (1024 * 1024)}MB",
        )
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise AppError(415, "UNSUPPORTED_MEDIA_TYPE", "PDF 文件签名无效")
    return normalized_name, mime_type


def extract_pages(filename: str, content: bytes) -> list[ExtractedPage]:
    extension = Path(filename).suffix.lower()
    if extension == ".pdf":
        return _extract_pdf(content)
    return _extract_text(content)


def _extract_pdf(content: bytes) -> list[ExtractedPage]:
    try:
        reader = PdfReader(BytesIO(content))
        pages = [
            ExtractedPage(page_number=index, content=_clean_text(page.extract_text() or ""))
            for index, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:
        raise AppError(422, "DOCUMENT_PARSE_FAILED", "PDF 文本解析失败") from exc
    pages = [page for page in pages if page.content]
    if not pages:
        raise AppError(422, "DOCUMENT_EMPTY", "文档没有可索引文本；扫描件暂不支持 OCR")
    return pages


def _extract_text(content: bytes) -> list[ExtractedPage]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(422, "DOCUMENT_PARSE_FAILED", "文本文件必须使用 UTF-8 编码") from exc
    cleaned = _clean_text(text)
    if not cleaned:
        raise AppError(422, "DOCUMENT_EMPTY", "文档没有可索引文本")
    return [ExtractedPage(page_number=1, content=cleaned)]


def _clean_text(value: str) -> str:
    lines = [" ".join(line.split()) for line in value.replace("\r\n", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()
