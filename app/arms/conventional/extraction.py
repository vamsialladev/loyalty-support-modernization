"""The non-AI document baseline: rules over a PDF's text layer and a plain-text email (D22; Appendix H; DOC-02 to
DOC-04).

What's on a page is evidence only. It can point at a stay, the same as a number typed in a message, and nothing more:
it never overwrites a record, sets an amount or gets past an approval. A value's standing comes from checks code can
make (format, and agreement with the system of record), never from anyone's self-reported confidence, and no percentages
are shown.

Text inside a document is data. These rules look for labelled fields, so "ignore your instructions" is just text they
skip (S02).

Images aren't read here. Tesseract isn't installed in this project, so OCR on photos is blocked with that
prerequisite (matrix DOC-02), and noisy photos are for arm C's vision method.
"""

from __future__ import annotations

import email
import email.policy
import io
import re
from dataclasses import asdict, dataclass

from pypdf import PdfReader
from pypdf.errors import PyPdfError

MAX_BYTES = 5 * 1024 * 1024
MAX_PAGES = 5
MAX_TEXT_CHARS = 20000
ALLOWED = {".pdf": "application/pdf", ".eml": "message/rfc822", ".png": "image/png", ".jpg": "image/jpeg"}
_CONFIRMATION = re.compile(r"\b(?:BR|ML)-\d{4}\b")
_PARTNER = re.compile(r"\bTRV-\d{8}\b")
_MEMBER = re.compile(r"\bGR-\d{5}\b")
_ARRIVAL = re.compile(r"(?:check[- ]?in|arrival|arrive[d]?)\s*:?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_DEPARTURE = re.compile(r"(?:check[- ]?out|departure|depart(?:ed)?)\s*:?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
_NAME = re.compile(r"^\s*(?:guest(?: name)?|name)\s*:\s*([^\n]+?)\s*$", re.IGNORECASE | re.MULTILINE)
_TOTAL = re.compile(r"(?:total(?: paid)?)\s*:?\s*(?:USD|\$)?\s*(\d[\d,]*\.\d{2})", re.IGNORECASE)
_RATE = re.compile(r"(?:nightly rate|room rate|room charge|rate)\s*:?\s*(?:USD|\$)?\s*(\d[\d,]*\.\d{2})", re.IGNORECASE)


class UnsafeDocument(Exception):
    """Refused before parsing: the wrong type, too large, or not what it says it is."""


@dataclass(frozen=True)
class Extracted:
    method: str  # pdf_rules | email_rules | none
    reason: str = ""
    confirmation: str | None = None
    partner_confirmation: str | None = None
    member_number: str | None = None
    arrival: str | None = None
    departure: str | None = None
    name: str | None = None
    rate: str | None = None
    total: str | None = None

    def fields(self) -> dict[str, str | None]:
        data = asdict(self)
        return {k: v for k, v in data.items() if k not in ("method", "reason")}


def media_type_for(filename: str, content: bytes) -> str:
    """File-ingestion controls (C.7): an allowed extension, a size limit and the file's own first bytes must all
    agree."""
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED:
        raise UnsafeDocument(f"files of type '{suffix or 'unknown'}' aren't accepted")
    if len(content) > MAX_BYTES:
        raise UnsafeDocument("the file is larger than the limit")
    signatures = {".pdf": b"%PDF-", ".png": b"\x89PNG", ".jpg": b"\xff\xd8\xff"}
    if suffix in signatures and not content.startswith(signatures[suffix]):
        raise UnsafeDocument("the file's contents don't match its type")
    if suffix == ".eml" and b"\x00" in content[:4096]:
        raise UnsafeDocument("the file's contents don't match its type")
    return ALLOWED[suffix]


def pdf_text(content: bytes) -> str:
    """The text layer only: no scripts, forms or embedded files are opened."""
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise UnsafeDocument("encrypted files aren't accepted")
        pages = reader.pages[:MAX_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)[:MAX_TEXT_CHARS]
    except PyPdfError as exc:
        raise UnsafeDocument("the PDF can't be read") from exc


def email_text(content: bytes) -> str:
    message = email.message_from_bytes(content, policy=email.policy.default)
    body = message.get_body(preferencelist=("plain",))
    subject = str(message.get("subject", ""))
    text = body.get_content() if body is not None else ""
    return f"{subject}\n{text}"[:MAX_TEXT_CHARS]


def _first(pattern: re.Pattern[str], text: str) -> str | None:
    found = pattern.search(text)
    return (found.group(1) if found.groups() else found.group(0)) if found else None


def fields_from_text(text: str, method: str) -> Extracted:
    return Extracted(
        method,
        confirmation=_first(_CONFIRMATION, text),
        partner_confirmation=_first(_PARTNER, text),
        member_number=_first(_MEMBER, text),
        arrival=_first(_ARRIVAL, text),
        departure=_first(_DEPARTURE, text),
        name=_first(_NAME, text),
        rate=_first(_RATE, text),
        total=_first(_TOTAL, text),
    )


def document_text(filename: str, content: bytes) -> str:
    """The readable text, for arm C's model, inside a labelled data block. Empty when there's none."""
    try:
        media_type = media_type_for(filename, content)
        if media_type == "application/pdf":
            return pdf_text(content)
        if media_type == "message/rfc822":
            return email_text(content)
    except UnsafeDocument:
        return ""
    return ""


def extract(filename: str, content: bytes) -> Extracted:
    """Never raises for a document it can't use: that's a result, and the case asks a person."""
    try:
        media_type = media_type_for(filename, content)
        if media_type == "application/pdf":
            text = pdf_text(content)
            if not text.strip():
                return Extracted("none", "no_text_layer")
            return fields_from_text(text, "pdf_rules")
        if media_type == "message/rfc822":
            return fields_from_text(email_text(content), "email_rules")
    except UnsafeDocument as exc:
        return Extracted("none", str(exc))
    return Extracted("none", "image_needs_ocr_or_vision")


def check_against_record(found: Extracted, record_stay_id: str | None, arrival: str | None) -> dict[str, str]:
    """A value's standing, from checks code can make: `matches`, `differs` or `format_only`. No percentages."""
    out: dict[str, str] = {}
    if found.confirmation:
        out["confirmation"] = (
            "format_only"
            if record_stay_id is None
            else "matches"
            if found.confirmation == record_stay_id
            else "differs"
        )
    if found.arrival:
        out["arrival"] = "format_only" if arrival is None else "matches" if found.arrival == arrival else "differs"
    return out
