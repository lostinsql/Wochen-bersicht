"""Optionale Ausgabe als Excel-Wochensicht (Aufbau wie die bisherige 'Belegung Wochensicht.xlsx')."""

import datetime as dt

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .bericht import SPERRUNG_KEYS, WOCHENTAGE

HEADER = [
    "Station", "Datum", "Tag", "Aufgestellte Betten", "Sperrung Bau",
    "Sperrung Personal Pflege", "Sperrung Sonstiges Pflege", "Sperrung ärztliches Personl",
    "Sperrung Isolation", "Sperrung Feiertag", "Begleit-person",
    "Belegbare Betten", "Belegte Betten", "Auslastung",
]


class _GesamtBlock:
    label = "Gesamt"

    def __init__(self, zeilen):
        self.zeilen = zeilen


def write_xlsx(bericht, path, start: dt.date) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    kw = start.isocalendar()[1]
    jahr = start.isocalendar()[0]
    ws = wb.create_sheet(f"KW {kw}")
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="D9D9D9")
    for c, h in enumerate(HEADER, start=1):
        cell = ws.cell(row=1, column=c, value=h)
        cell.font = bold
        cell.fill = fill
    r = 2
    for block in list(bericht.stationen) + [_GesamtBlock(bericht.gesamt)]:
        for i, z in enumerate(block.zeilen):
            ws.cell(row=r, column=1, value=block.label if i == 0 else None)
            dcell = ws.cell(row=r, column=2, value=dt.datetime(z.datum.year, z.datum.month, z.datum.day))
            dcell.number_format = "DD.MM.YYYY"
            ws.cell(row=r, column=3, value=WOCHENTAGE[z.datum.weekday()])
            ws.cell(row=r, column=4, value=z.aufgestellt)
            for k, name in enumerate(SPERRUNG_KEYS):
                ws.cell(row=r, column=5 + k, value=z.sperrungen.get(name) or None)
            ws.cell(row=r, column=12, value=z.belegbar)
            ws.cell(row=r, column=13, value=z.belegte)
            acell = ws.cell(row=r, column=14, value=z.auslastung)
            acell.number_format = "0.0%"
            r += 1
    for col, width in zip(range(1, 15), [12, 12, 6] + [10] * 7 + [13, 12, 10]):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = width
    wb.save(str(path))
