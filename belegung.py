#!/usr/bin/env python3
"""Belegungsübersicht DHM – erstellt die wöchentliche Belegungsübersicht als PDF.

Aufruf ohne Argumente startet einen Dialog (tkinter).
Aufruf mit Argumenten läuft ohne Dialog (geeignet für Server/Cron):

  python belegung.py --modus letzte-woche
  python belegung.py --modus kw --jahr 2026 --kw 45
  python belegung.py --modus zeitraum --von 2026-11-02 --bis 2026-11-08

Optionen:
  --input ORDNER    Ordner mit den Exportdateien (Default: ./input neben diesem Skript)
  --output ORDNER   Zielordner für die PDF (Default: ./output)
  --config DATEI    Stations-Konfiguration (Default: ./config/stations.json)
  --xlsx            zusätzlich eine Excel-Wochensicht schreiben
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from belegung import app_base
from belegung.bericht import build_bericht, dateien_name, resolve_period
from belegung.config import default_config_path, load_config
from belegung.eingang import scan_input_folder
from belegung.pdf_ausgabe import write_pdf

BASE = app_base()


def _parse_date(s: str) -> dt.date:
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


def run(modus, jahr=None, kw=None, von=None, bis=None, input_dir=None, output_dir=None,
        config_path=None, xlsx=False) -> Path:
    config = load_config(config_path or default_config_path())
    input_dir = Path(input_dir) if input_dir else BASE / "input"
    output_dir = Path(output_dir) if output_dir else BASE / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_input_folder(input_dir, config.sperrgruende_sheet_praferenz)
    start, ende, subtitel = resolve_period(modus, jahr=jahr, kw=kw, von=von, bis=bis)
    bericht = build_bericht(config, scan, start, ende, subtitel)

    pdf_path = output_dir / dateien_name(bericht, start, ende, modus, jahr, kw)
    write_pdf(bericht, pdf_path, logo_path=config.logo_path)

    if xlsx:
        from belegung.xlsx_ausgabe import write_xlsx
        write_xlsx(bericht, output_dir / "Belegung Wochensicht.xlsx", start)

    for w in bericht.warnungen:
        print(f"Hinweis: {w}", file=sys.stderr)
    print(f"PDF erstellt: {pdf_path}")
    print(f"Zeitraum: {start.strftime('%d.%m.%Y')} - {ende.strftime('%d.%m.%Y')} ({subtitel})")
    return pdf_path


def main_cli(argv=None) -> int:
    p = argparse.ArgumentParser(description="Belegungsübersicht DHM erstellen")
    p.add_argument("--modus", choices=["letzte-woche", "kw", "zeitraum"],
                   help="letzte-woche: KW der Vorwoche; kw: --jahr/--kw; zeitraum: --von/--bis")
    p.add_argument("--jahr", type=int)
    p.add_argument("--kw", type=int)
    p.add_argument("--von", type=_parse_date)
    p.add_argument("--bis", type=_parse_date)
    p.add_argument("--input", dest="input_dir")
    p.add_argument("--output", dest="output_dir")
    p.add_argument("--config", dest="config_path")
    p.add_argument("--xlsx", action="store_true")
    args = p.parse_args(argv)
    if not args.modus:
        return main_gui()
    run(args.modus, jahr=args.jahr, kw=args.kw, von=args.von, bis=args.bis,
        input_dir=args.input_dir, output_dir=args.output_dir,
        config_path=args.config_path, xlsx=args.xlsx)
    return 0


def main_gui() -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("Belegungsübersicht DHM")

    modus = tk.StringVar(value="letzte-woche")
    jahr = tk.StringVar(value=str(dt.date.today().isocalendar()[0]))
    kw = tk.StringVar(value=str(dt.date.today().isocalendar()[1]))
    von = tk.StringVar(value=(dt.date.today() - dt.timedelta(days=7)).strftime("%Y-%m-%d"))
    bis = tk.StringVar(value=dt.date.today().strftime("%Y-%m-%d"))
    input_dir = tk.StringVar(value=str(BASE / "input"))
    output_dir = tk.StringVar(value=str(BASE / "output"))
    xlsx_var = tk.BooleanVar(value=False)

    def frame(text):
        f = ttk.LabelFrame(root, text=text, padding=8)
        f.pack(fill="x", padx=8, pady=4)
        return f

    f1 = frame("Zeitraum")
    ttk.Radiobutton(f1, text="Letzte Woche (Kalenderwoche der Vorwoche)", variable=modus, value="letzte-woche").pack(anchor="w")
    kwrow = ttk.Frame(f1)
    kwrow.pack(anchor="w", fill="x")
    ttk.Radiobutton(kwrow, text="Kalenderwoche:", variable=modus, value="kw").pack(side="left")
    ttk.Entry(kwrow, textvariable=jahr, width=6).pack(side="left", padx=(4, 0))
    ttk.Label(kwrow, text="KW").pack(side="left", padx=(4, 0))
    ttk.Entry(kwrow, textvariable=kw, width=4).pack(side="left", padx=(4, 0))
    zrow = ttk.Frame(f1)
    zrow.pack(anchor="w", fill="x", pady=(2, 0))
    ttk.Radiobutton(zrow, text="Zeitraum von", variable=modus, value="zeitraum").pack(side="left")
    ttk.Entry(zrow, textvariable=von, width=12).pack(side="left", padx=(4, 0))
    ttk.Label(zrow, text="bis").pack(side="left", padx=(4, 0))
    ttk.Entry(zrow, textvariable=bis, width=12).pack(side="left", padx=(4, 0))
    ttk.Label(zrow, text="(JJJJ-MM-TT)").pack(side="left", padx=(4, 0))

    f2 = frame("Ordner")
    ttk.Label(f2, text="Eingangsordner (Exporte + Sperrgründe):").pack(anchor="w")
    ttk.Entry(f2, textvariable=input_dir).pack(fill="x")
    ttk.Label(f2, text="Zielordner für die PDF:").pack(anchor="w")
    ttk.Entry(f2, textvariable=output_dir).pack(fill="x")
    ttk.Checkbutton(f2, text="zusätzlich Excel-Wochensicht schreiben", variable=xlsx_var).pack(anchor="w")

    def erstellen():
        try:
            m = modus.get()
            path = run(
                m,
                jahr=int(jahr.get()) if jahr.get().strip() else None,
                kw=int(kw.get()) if kw.get().strip() else None,
                von=_parse_date(von.get()) if m == "zeitraum" else None,
                bis=_parse_date(bis.get()) if m == "zeitraum" else None,
                input_dir=input_dir.get(), output_dir=output_dir.get(),
                xlsx=xlsx_var.get(),
            )
            messagebox.showinfo("Fertig", f"PDF erstellt:\n{path}")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Fehler", str(exc))

    ttk.Button(root, text="PDF erstellen", command=erstellen).pack(pady=8)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
