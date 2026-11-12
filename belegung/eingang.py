"""Einlesen der KIS-Exportdateien und der Bettensperrgründe aus dem Eingangsordner."""

import csv
import datetime as dt
import io
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

DATE_PATTERNS = [
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),
    re.compile(r"(\d{2})\.(\d{2})\.(\d{4})"),
]

EXPORT_EXTS = {".xlsx", ".xlsm", ".csv"}
SPERR_EXTS = {".xlsx", ".xlsm", ".csv"}


def date_from_name(name: str) -> dt.date | None:
    for pat, order in ((DATE_PATTERNS[0], "ymd"), (DATE_PATTERNS[1], "dmy")):
        m = pat.search(name)
        if not m:
            continue
        a, b, c = (int(x) for x in m.groups())
        try:
            if order == "ymd":
                return dt.date(a, b, c)
            return dt.date(c, b, a)
        except ValueError:
            continue
    return None


def _parse_dt(value) -> dt.datetime | None:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return dt.datetime.strptime(s, fmt)
            except ValueError:
                continue
    return None


def _read_csv_rows(path: Path) -> list[list]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    return [row for row in reader]


def _read_xlsx_rows(path: Path) -> dict[str, list[list]]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = {}
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            rows.append(list(row))
            if len(rows) > 100000:
                break
        sheets[ws.title] = rows
    wb.close()
    return sheets


def _find_header(rows: list[list], required: set[str]) -> tuple[int, dict[str, int]] | None:
    norm = lambda v: str(v).strip().lower() if v is not None else ""
    for i, row in enumerate(rows[:30]):
        mapping = {}
        for j, cell in enumerate(row):
            mapping[norm(cell)] = j
        if required.issubset(mapping.keys()):
            return i, {k: v for k, v in mapping.items() if k}
    return None


def _classify_export(sheets: dict[str, list[list]]) -> dict[str, list[list]] | None:
    required = {"station", "abr.-art"}
    for rows in sheets.values():
        found = _find_header(rows, required)
        if found:
            return {"rows": rows}
    return None


def _classify_sperrgruende(sheets: dict[str, list[list]], prefer: list[str]) -> str | None:
    for name in prefer:
        if name in sheets:
            return name
    for name in sheets:
        if "bettensperrungen" in name.lower():
            return name
    return None


def read_export_file(path: Path) -> dict:
    """Liefert {'station_counts': {station: {'patienten': n, 'bgl': n}}, 'max_aufnahme': date|None}."""
    if path.suffix.lower() == ".csv":
        sheets = {"csv": _read_csv_rows(path)}
    else:
        sheets = _read_xlsx_rows(path)
    found = None
    rows = None
    for candidate in sheets.values():
        found = _find_header(candidate, {"station", "abr.-art"})
        if found:
            rows = candidate
            break
    if not found:
        raise ValueError(f"Keine Export-Kopfzeile (Station / Abr.-Art) in {path.name} gefunden")
    hdr_idx, colmap = found
    si, ai = colmap["station"], colmap["abr.-art"]
    aufn_i = colmap.get("aufnahmezeitpunkt")
    counts = defaultdict(lambda: {"patienten": 0, "bgl": 0})
    max_aufnahme = None
    for row in rows[hdr_idx + 1:]:
        station = row[si] if si < len(row) else None
        abr = row[ai] if ai < len(row) else None
        if station is None and abr is None:
            continue
        station = str(station).strip()
        abr = str(abr).strip().upper() if abr is not None else ""
        if aufn_i is not None and aufn_i < len(row):
            parsed = _parse_dt(row[aufn_i])
            if parsed and (max_aufnahme is None or parsed > max_aufnahme):
                max_aufnahme = parsed
        if abr == "BGL":
            counts[station]["bgl"] += 1
        else:
            counts[station]["patienten"] += 1
    return {"station_counts": dict(counts), "max_aufnahme": max_aufnahme.date() if max_aufnahme else None}


def read_sperrgruende_file(path: Path, sheet_preference: list[str]) -> dict:
    """Liefert {'sperrungen': {station: {grund: betten}}, 'ausfuehrungszeit': date|None}."""
    if path.suffix.lower() == ".csv":
        sheets = {"csv": _read_csv_rows(path)}
    else:
        sheets = _read_xlsx_rows(path)
    sheet_name = _classify_sperrgruende(sheets, sheet_preference)
    if sheet_name is None:
        raise ValueError(f"Kein Blatt mit Bettensperrungen in {path.name} gefunden")
    rows = sheets[sheet_name]
    found = _find_header(rows, {"station", "bettsperrgrundbezeichnung"})
    if not found:
        raise ValueError(f"Keine Kopfzeile der Bettensperrungen in {path.name} (Blatt {sheet_name})")
    hdr_idx, colmap = found
    si = colmap["station"]
    gi = colmap["bettsperrgrundbezeichnung"]
    bi = colmap.get("gesperrte betten um mitternacht")
    sperrungen = defaultdict(lambda: defaultdict(int))
    for row in rows[hdr_idx + 1:]:
        station = row[si] if si < len(row) else None
        grund = row[gi] if gi < len(row) else None
        if station is None and grund is None:
            continue
        station = str(station).strip()
        if station.lower() == "gesamtwert":
            continue
        grund = str(grund).strip() if grund is not None else ""
        betten = 0
        if bi is not None and bi < len(row) and isinstance(row[bi], (int, float)):
            betten = int(row[bi])
        elif bi is not None and bi < len(row) and row[bi] is not None:
            try:
                betten = int(float(str(row[bi]).replace(",", ".")))
            except ValueError:
                betten = 0
        sperrungen[station][grund] += betten
    ausfuehrungszeit = None
    for name, srows in sheets.items():
        if "berichtsinfos" in name.lower():
            for row in srows:
                for cell in row:
                    if isinstance(cell, str) and "Ausführungszeit" in cell:
                        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", cell)
                        if m:
                            ausfuehrungszeit = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    return {
        "sheet": sheet_name,
        "sperrungen": {k: dict(v) for k, v in sperrungen.items()},
        "ausfuehrungszeit": ausfuehrungszeit,
    }


def scan_input_folder(folder: Path, sperrgruende_sheet_praferenz: list[str]) -> dict:
    """Scannt den Eingangsordner.

    Rückgabe:
      {
        'exporte': {date: {'station_counts': {...}, 'quelle': filename}},
        'sperrungen': {date: {'sperrungen': {...}, 'quelle': filename, 'sheet': name}},
        'warnungen': [...],
      }
    """
    folder = Path(folder)
    result = {"exporte": {}, "sperrungen": {}, "warnungen": []}
    if not folder.is_dir():
        result["warnungen"].append(f"Eingangsordner nicht gefunden: {folder}")
        return result
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (EXPORT_EXTS | SPERR_EXTS):
            continue
        date = date_from_name(path.name)
        try:
            if path.suffix.lower() == ".csv":
                sheets = {"csv": _read_csv_rows(path)}
                is_export = _find_header(sheets["csv"], {"station", "abr.-art"}) is not None
                is_sperr = not is_export and _classify_sperrgruende(sheets, sperrgruende_sheet_praferenz) is not None
            else:
                sheets = _read_xlsx_rows(path)
                is_export = _classify_export(sheets) is not None
                is_sperr = (not is_export) and _classify_sperrgruende(sheets, sperrgruende_sheet_praferenz) is not None
            if is_export:
                data = read_export_file(path)
                if date is None:
                    date = data["max_aufnahme"]
                    if date is None:
                        result["warnungen"].append(f"Kein Datum im Dateinamen und keins in den Daten: {path.name} – übersprungen")
                        continue
                    result["warnungen"].append(f"Datum aus Daten ergänzt ({date.isoformat()}) für {path.name}")
                if date in result["exporte"]:
                    result["warnungen"].append(f"Mehrere Exporte für {date.isoformat()}: {path.name} überschreibt {result['exporte'][date]['quelle']}")
                result["exporte"][date] = {"station_counts": data["station_counts"], "quelle": path.name}
            elif is_sperr:
                data = read_sperrgruende_file(path, sperrgruende_sheet_praferenz)
                if date is None:
                    date = data["ausfuehrungszeit"]
                    if date is None:
                        result["warnungen"].append(f"Kein Datum im Dateinamen und keins in den Daten: {path.name} – übersprungen")
                        continue
                    result["warnungen"].append(f"Datum aus Berichtsinfos ergänzt ({date.isoformat()}) für {path.name}")
                if date in result["sperrungen"]:
                    result["warnungen"].append(f"Mehrere Sperrgründe-Dateien für {date.isoformat()}: {path.name} überschreibt {result['sperrungen'][date]['quelle']}")
                result["sperrungen"][date] = {"sperrungen": data["sperrungen"], "quelle": path.name, "sheet": data["sheet"]}
            else:
                result["warnungen"].append(f"Datei nicht erkannt (weder Export noch Sperrgründe): {path.name}")
        except Exception as exc:  # noqa: BLE001
            result["warnungen"].append(f"Fehler beim Lesen von {path.name}: {exc}")
    return result
