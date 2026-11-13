"""PDF-Ausgabe der Belegungsübersicht (Querformat A4, Aufbau wie die bisherige PDF-Vorlage)."""

import datetime as dt
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .bericht import SPERRUNG_KEYS, WOCHENTAGE, Bericht

BASE = Path(__file__).resolve().parent.parent

HEADER = [
    "Station", "Datum", "Tag", "Aufgestellte<br/>Betten", "Sperrung Bau",
    "Sperrung Personal Pflege", "Sperrung Sonstiges Pflege", "Sperrung ärztliches Personal",
    "Sperrung Isolation", "Sperrung Feiertag", "Begleitperson",
    "Belegbare<br/>Betten", "Belegte<br/>Betten", "Auslastung",
]

SPERRUNG_OFFSET = 4  # Index der ersten Sperrungsspalte in HEADER (Anzeige)

_style_cell = ParagraphStyle("cell", fontName="Helvetica", fontSize=7.5, leading=9)
_style_header = ParagraphStyle("hdr", fontName="Helvetica-Bold", fontSize=7, leading=8.5)
_style_label = ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=8, leading=10)
_style_title = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=14, leading=17)
_style_kw = ParagraphStyle("kw", fontName="Helvetica-Bold", fontSize=16, leading=19, alignment=TA_CENTER)
_style_sub = ParagraphStyle("sub", fontName="Helvetica", fontSize=9, leading=12, alignment=TA_CENTER)


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
    style = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]
    r = 1
    for block in blocks:
        first = r
        for i, row in enumerate(_block_rows(block)):
            cells = []
            for j, c in enumerate(row):
                if j == 0 and i == 0 and c != "":
                    cells.append(Paragraph(str(c), _style_label))
                else:
                    cells.append(_cell(c) if not isinstance(c, Paragraph) else c)
            data.append(cells)
            r += 1
        last = r - 1
        # Abhebung zwischen den Stationen: Label spannen + fett auf grau, dicke Trennlinie darunter
        if last > first:
            style.append(("SPAN", (0, first), (0, last)))
        style.append(("BACKGROUND", (0, first), (0, last), colors.HexColor("#D9D9D9")))
        style.append(("LINEBELOW", (0, last), (-1, last), 1.2, colors.black))
        if _is_gesamt(block):
            style.append(("BACKGROUND", (1, first), (-1, last), colors.HexColor("#F2F2F2")))
            style.append(("LINEABOVE", (0, first), (-1, first), 1.2, colors.black))
    widths = [70, 62, 26, 52, 46, 54, 54, 56, 48, 48, 56, 56, 50, 50]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t


def _resolve_logo(logo_path) -> Path | None:
    if not logo_path:
        return None
    p = Path(logo_path)
    if not p.is_absolute():
        p = BASE / p
    return p if p.is_file() else None


def write_pdf(bericht: Bericht, path, logo_path=None) -> None:
    page_w, page_h = landscape(A4)
    top_margin = 24 * mm  # Platz für das Logo oben rechts
    bottom_margin = 10 * mm
    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
        title=bericht.titel,
    )
    story = []
    datenstand = bericht.datenstand.strftime("%d.%m.%Y") if bericht.datenstand else "unbekannt"

    logo = _resolve_logo(logo_path)
    if logo_path and logo is None:
        bericht.warnungen.append(f"Logo-Datei nicht gefunden: {logo_path} – PDF wird ohne Logo erstellt")
    logo_w = logo_h = 0
    logo_img = None
    if logo is not None:
        logo_img = ImageReader(str(logo))
        iw, ih = logo_img.getSize()
        logo_h = 14 * mm
        logo_w = logo_h * iw / ih

    def _draw_page(canvas, _doc):
        if logo_img is not None:
            x = page_w - _doc.rightMargin - logo_w
            y = page_h - 6 * mm - logo_h
            canvas.drawImage(logo_img, x, y, width=logo_w, height=logo_h, mask="auto")

    blocks = list(bericht.stationen) + [_GesamtBlock(bericht.gesamt)]

    # Blöcke seitenweise packen (mindestens 1 Block pro Seite)
    title_flowables = [
        Paragraph(bericht.titel, _style_title),
        Paragraph(bericht.subtitel, _style_kw),
        Paragraph(f"Datenstand: {datenstand}", _style_sub),
        Spacer(1, 2),
        HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#999999")),
        Spacer(1, 4),
    ]
    avail_h = page_h - top_margin - bottom_margin - 66  # Seitenränder + Titelfluss
    row_h = 13.5
    header_h = 30
    rows_per_page = max(7, int((avail_h - header_h) // row_h))
    rows_per_block = max(len(b.zeilen) for b in blocks)
    per_page = max(1, rows_per_page // rows_per_block)

    chunks = []
    for i in range(0, len(blocks), per_page):
        chunks.append(blocks[i:i + per_page])

    for idx, chunk in enumerate(chunks):
        if idx > 0:
            story.append(PageBreak())
        story.extend(title_flowables)
        story.append(_table_for(chunk))

    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
