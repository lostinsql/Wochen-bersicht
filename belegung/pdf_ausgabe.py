"""PDF-Ausgabe der Belegungsübersicht (Querformat A4, Aufbau wie die bisherige PDF-Vorlage)."""

import datetime as dt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .bericht import SPERRUNG_KEYS, WOCHENTAGE, Bericht

HEADER = [
    "Station", "Datum", "Tag", "Aufgestellte Betten", "Sperrung Bau",
    "Sperrung Personal Pflege", "Sperrung Sonstiges Pflege", "Sperrung ärztliches Personl",
    "Sperrung Isolation", "Sperrung Feiertag", "Begleit-person",
    "Belegbare Betten", "Belegte Betten", "Auslastung",
]

SPERRUNG_OFFSET = 4  # Index der ersten Sperrungsspalte in HEADER (Anzeige)

_style_cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9)
_style_header = ParagraphStyle("hdr", fontName="Helvetica-Bold", fontSize=7, leading=8.5)
_style_title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=13, leading=16)
_style_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, leading=12)


def _fmt_pct(v) -> str:
    if v is None:
        return ""
    return f"{v * 100:.1f}%".replace(".", ",")


def _cell(text, header=False):
    return Paragraph(str(text), _style_header if header else _style_cell)


def _block_rows(block) -> list[list]:
    gesamt = _is_gesamt(block)
    rows = []
    for i, z in enumerate(block.zeilen):
        label = block.label if i == 0 else ""
        sperr = []
        for key in SPERRUNG_KEYS:
            val = z.sperrungen.get(key)
            if gesamt:
                sperr.append(val if val is not None else 0)
            else:
                sperr.append("" if val in (None, 0) else val)
        row = [
            label,
            z.datum.strftime("%d.%m.%Y"),
            WOCHENTAGE[z.datum.weekday()],
            "" if z.aufgestellt is None else z.aufgestellt,
            *sperr,
            "" if z.belegbar is None else z.belegbar,
            "" if z.belegte is None else z.belegte,
            _fmt_pct(z.auslastung),
        ]
        rows.append(row)
    return rows


def _is_gesamt(block) -> bool:
    return getattr(block, "label", "") == "Gesamt"


class _GesamtBlock:
    label = "Gesamt"

    def __init__(self, zeilen):
        self.zeilen = zeilen


def _table_for(blocks) -> Table:
    data = [[_cell(h, header=True) for h in HEADER]]
    for block in blocks:
        for row in _block_rows(block):
            data.append([_cell(c) if not isinstance(c, Paragraph) else c for c in row])
    widths = [62, 55, 22] + [46] * 7 + [52, 50, 44]
    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    t.setStyle(TableStyle(style))
    return t


def write_pdf(bericht: Bericht, path) -> None:
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=bericht.titel,
    )
    story = []
    datenstand = bericht.datenstand.strftime("%d.%m.%Y") if bericht.datenstand else "unbekannt"

    blocks = list(bericht.stationen) + [_GesamtBlock(bericht.gesamt)]

    # Blöcke seitenweise packen (mindestens 1 Block pro Seite)
    title_flowables = [
        Paragraph(bericht.titel, _style_title),
        Paragraph(f"Datenstand: {datenstand}", _style_sub),
        Paragraph(bericht.subtitel, _style_sub),
        Spacer(1, 4),
    ]
    avail_h = page_h - 20 * mm - 48  # Seitenränder + Titelfluss
    row_h = 13.5
    header_h = 30
    rows_per_page = max(7, int((avail_h - header_h) // row_h))
    rows_per_block = max(len(b.zeilen) for b in blocks)
    per_page = max(1, rows_per_page // rows_per_block)

    chunks = []
    for i in range(0, len(blocks), per_page):
        chunks.append(blocks[i:i + per_page])

    from reportlab.platypus import PageBreak

    for idx, chunk in enumerate(chunks):
        if idx > 0:
            story.append(PageBreak())
        story.extend(title_flowables)
        story.append(_table_for(chunk))

    doc.build(story)
