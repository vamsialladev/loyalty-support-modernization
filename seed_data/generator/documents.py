"""Synthetic supporting documents (Appendix H1): folio PDFs, receipt images with noise, OTA confirmation emails.

Ground-truth fields come from the stay record (or a deliberate disagreement). Determinism is checked on content:
for images the SHA-256 of the pixels, for PDFs and emails the SHA-256 of the canonical field spec, because file
bytes can differ across zlib builds even with identical input.
"""

import hashlib
import json
import random
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from seed_data.generator.models import StayRecord
from seed_data.generator.text import INJECTION_LINES
from seed_data.generator.timeutil import business_date
from seed_data.generator.world import PROPERTIES, checkout_dt

ADDRESSES = {"beach-resort": "1 Shoreline Way, (fictional) FL", "mountain-lodge": "88 Ridge Road, (fictional) NC"}


def document_fields(stay: StayRecord, disagree: list[str]) -> dict[str, str]:
    """True field values printed on the document. `disagree` shifts fields away from the system of record."""
    departure = business_date(checkout_dt(stay))
    if "departure" in disagree:
        departure += timedelta(days=1)
    nightly = stay.room_revenue_cents // stay.nights
    return {
        "confirmation": stay.stay_id,
        "property": PROPERTIES[stay.property][0],
        "arrival": stay.arrival_date,
        "departure": departure.isoformat(),
        "rate": f"{nightly / 100:.2f}",
        "total": f"{(stay.room_revenue_cents + stay.taxes_cents + stay.fees_cents) / 100:.2f}",
        "name": stay.guest_name,
        "member": stay.member_number or "",
    }


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def folio_lines(stay: StayRecord, fields: dict[str, str], injection: str | None) -> list[str]:
    arrival = date.fromisoformat(fields["arrival"])
    lines = [
        f"{fields['property']}  -  GUEST FOLIO",
        ADDRESSES[stay.property],
        "",
        f"Guest: {fields['name']}",
        f"Guest Rewards no.: {fields['member'] or '-'}",
        f"Confirmation: {fields['confirmation']}",
        f"Arrival: {fields['arrival']}    Departure: {fields['departure']}",
        "",
    ]
    for n in range(stay.nights):
        lines.append(f"{(arrival + timedelta(days=n)).isoformat()}  Room charge        {fields['rate']}")
    lines += [
        f"Taxes                                  {stay.taxes_cents / 100:.2f}",
        f"Fees                                   {stay.fees_cents / 100:.2f}",
        f"TOTAL                                  {fields['total']}",
        "",
        "SYNTHETIC DOCUMENT - fictional hotel group - not a real folio",
    ]
    if injection:
        lines.insert(-1, f"Notes: {injection}")
    return lines


def write_folio_pdf(path: Path, stay: StayRecord, fields: dict[str, str], layout: str, injection: str | None) -> str:
    lines = folio_lines(stay, fields, injection)
    c = canvas.Canvas(str(path), pagesize=LETTER, invariant=1)
    c.setTitle(f"Folio {fields['confirmation']} (synthetic)")
    font, bold, size, x, y = {
        "A": ("Helvetica", "Helvetica-Bold", 11, 72, 720),
        "B": ("Courier", "Courier", 10, 54, 740),
        "C": ("Times-Roman", "Times-Bold", 12, 90, 700),
    }[layout]
    if layout == "B":
        c.rect(40, 300, 530, 470)
    for i, line in enumerate(lines):
        c.setFont(bold if i == 0 else font, size + (3 if i == 0 else 0))
        c.drawString(x, y - i * (size + 6), line)
    c.showPage()
    c.save()
    return digest({"kind": "folio_pdf", "layout": layout, "lines": lines})


def write_receipt_png(path: Path, stay: StayRecord, fields: dict[str, str], noise: list[str], r: random.Random) -> str:
    lines = folio_lines(stay, fields, None)
    font = ImageFont.load_default(size=20)
    img = Image.new("L", (760, 40 + 30 * len(lines)), 255)
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((30, 20 + 30 * i), line, fill=0, font=font)
    if "speckle" in noise:
        speckle = Image.frombytes("L", img.size, r.randbytes(img.size[0] * img.size[1]))
        img = Image.blend(img, speckle, 0.18)
    if "low_contrast" in noise:
        img = ImageEnhance.Contrast(img).enhance(0.45 + r.random() * 0.15)
    if "blur" in noise:
        img = img.filter(ImageFilter.GaussianBlur(radius=1.0 + r.random()))
    if "rotation" in noise:
        img = img.rotate(r.uniform(-7, 7), resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
    if "crop" in noise:
        w, h = img.size
        img = img.crop((r.randrange(0, 25), r.randrange(0, 15), w - r.randrange(0, 40), h - r.randrange(0, 25)))
    img.save(path, format="PNG", optimize=False, compress_level=1)
    return hashlib.sha256(img.tobytes()).hexdigest()


def write_ota_email(path: Path, stay: StayRecord, fields: dict[str, str], injection: str | None) -> str:
    msg = EmailMessage()
    msg["From"] = "bookings@wanderly-travel.example"
    msg["To"] = "guest@mail.test"
    msg["Subject"] = f"Your booking is confirmed: {fields['property']} ({stay.partner_confirmation})"
    msg["Date"] = "Mon, 01 Jun 2026 09:00:00 +0000"
    body = [
        "Wanderly Travel (fictional online travel agency) - booking confirmation",
        f"Wanderly reference: {stay.partner_confirmation}",
        f"Hotel: {fields['property']}",
        f"Guest: {fields['name']}",
        f"Loyalty number on booking: {fields['member'] or 'none'}",
        f"Check-in: {fields['arrival']}   Check-out: {fields['departure']}",
        f"Total paid: USD {fields['total']}",
        "SYNTHETIC EMAIL - not a real booking",
    ]
    if injection:
        body.append(injection)
    msg.set_content("\n".join(body))
    path.write_bytes(bytes(msg))
    return digest({"kind": "ota_email", "body": body})


def render(
    path: Path,
    kind: str,
    stay: StayRecord,
    layout: str,
    noise: list[str],
    disagree: list[str],
    injection: bool,
    r: random.Random,
) -> tuple[dict[str, str], str]:
    """Write one document; return its true fields and its content digest."""
    fields = document_fields(stay, disagree)
    note = r.choice(INJECTION_LINES) if injection else None
    if kind == "folio_pdf":
        return fields, write_folio_pdf(path, stay, fields, layout, note)
    if kind == "receipt_image":
        return fields, write_receipt_png(path, stay, fields, noise, r)
    return fields, write_ota_email(path, stay, fields, note)
