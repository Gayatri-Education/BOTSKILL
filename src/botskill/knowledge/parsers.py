"""BOTSKILL — Safe Document Parsers and Intake Pipeline.

Supports PDF (pypdf/fitz), DOCX, TXT, Markdown, and CSV with strict size and security bounds.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("botskill.knowledge.parsers")

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB limit
MAX_PAGE_COUNT = 300


class DocumentParseResult:
    """Extracted text and structural coordinates from an enterprise document."""

    def __init__(
        self,
        document_id: str,
        filename: str,
        content_hash: str,
        file_type: str,
        text_content: str,
        sections: List[Dict[str, Any]],
        page_count: int = 1,
        is_success: bool = True,
        error_message: Optional[str] = None,
    ):
        self.document_id = document_id
        self.filename = filename
        self.content_hash = content_hash
        self.file_type = file_type
        self.text_content = text_content
        self.sections = sections
        self.page_count = page_count
        self.is_success = is_success
        self.error_message = error_message


class SafeDocumentParser:
    """Safe parser registry with bounded resource consumption and content inspection."""

    @staticmethod
    def compute_sha256(file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    def parse_file(self, file_path: str) -> DocumentParseResult:
        path = Path(file_path)
        if not path.exists():
            return DocumentParseResult(
                document_id="error",
                filename=path.name,
                content_hash="",
                file_type="unknown",
                text_content="",
                sections=[],
                is_success=False,
                error_message=f"File not found: {file_path}",
            )

        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            return DocumentParseResult(
                document_id="oversized",
                filename=path.name,
                content_hash="",
                file_type="oversized",
                text_content="",
                sections=[],
                is_success=False,
                error_message=f"File size {file_size} exceeds safety limit of {MAX_FILE_SIZE_BYTES} bytes",
            )

        with open(path, "rb") as f:
            raw_bytes = f.read()

        content_hash = self.compute_sha256(raw_bytes)
        doc_id = f"doc_{content_hash[:16]}"
        ext = path.suffix.lower()

        try:
            if ext == ".txt" or ext == ".md":
                return self._parse_text(doc_id, path.name, content_hash, raw_bytes)
            elif ext == ".pdf":
                return self._parse_pdf(doc_id, path.name, content_hash, raw_bytes)
            elif ext == ".docx":
                return self._parse_docx(doc_id, path.name, content_hash, raw_bytes)
            elif ext == ".csv":
                return self._parse_csv(doc_id, path.name, content_hash, raw_bytes)
            else:
                return DocumentParseResult(
                    document_id=doc_id,
                    filename=path.name,
                    content_hash=content_hash,
                    file_type="unsupported",
                    text_content="",
                    sections=[],
                    is_success=False,
                    error_message=f"Unsupported format: {ext}",
                )
        except Exception as ex:
            logger.error("Parser failure on %s: %s", path.name, ex)
            return DocumentParseResult(
                document_id=doc_id,
                filename=path.name,
                content_hash=content_hash,
                file_type=ext,
                text_content="",
                sections=[],
                is_success=False,
                error_message=f"Extraction failure: {str(ex)}",
            )

    def _parse_text(self, doc_id: str, name: str, hsh: str, data: bytes) -> DocumentParseResult:
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        sections = [
            {"section_idx": idx + 1, "page": 1, "text": p}
            for idx, p in enumerate(paragraphs)
        ]
        return DocumentParseResult(
            document_id=doc_id,
            filename=name,
            content_hash=hsh,
            file_type="text",
            text_content=text,
            sections=sections,
            page_count=1,
            is_success=True,
        )

    def _parse_pdf(self, doc_id: str, name: str, hsh: str, data: bytes) -> DocumentParseResult:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        total_pages = min(len(reader.pages), MAX_PAGE_COUNT)
        full_text_parts = []
        sections = []

        for p_idx in range(total_pages):
            page_text = reader.pages[p_idx].extract_text() or ""
            full_text_parts.append(page_text)
            sections.append({
                "section_idx": p_idx + 1,
                "page": p_idx + 1,
                "text": page_text.strip(),
            })

        return DocumentParseResult(
            document_id=doc_id,
            filename=name,
            content_hash=hsh,
            file_type="pdf",
            text_content="\n\n".join(full_text_parts),
            sections=sections,
            page_count=total_pages,
            is_success=True,
        )

    def _parse_docx(self, doc_id: str, name: str, hsh: str, data: bytes) -> DocumentParseResult:
        import docx
        doc = docx.Document(io.BytesIO(data))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        sections = [
            {"section_idx": idx + 1, "page": 1, "text": p}
            for idx, p in enumerate(paragraphs)
        ]
        return DocumentParseResult(
            document_id=doc_id,
            filename=name,
            content_hash=hsh,
            file_type="docx",
            text_content="\n\n".join(paragraphs),
            sections=sections,
            page_count=1,
            is_success=True,
        )

    def _parse_csv(self, doc_id: str, name: str, hsh: str, data: bytes) -> DocumentParseResult:
        text = data.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = [" | ".join(row) for row in reader if row]
        sections = [
            {"section_idx": idx + 1, "page": 1, "text": r}
            for idx, r in enumerate(rows)
        ]
        return DocumentParseResult(
            document_id=doc_id,
            filename=name,
            content_hash=hsh,
            file_type="csv",
            text_content="\n".join(rows),
            sections=sections,
            page_count=1,
            is_success=True,
        )
