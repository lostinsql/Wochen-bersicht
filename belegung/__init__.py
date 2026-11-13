"""Belegungsübersicht DHM – wöchentliche Belegungsauswertung aus KIS-Exporten."""

import sys
from pathlib import Path

__version__ = "1.0.0"


def app_base() -> Path:
    """Basisverzeichnis der Anwendung.

   Als eingefrorene App (PyInstaller --onefile) entpackt sich das Programm bei
   jedem Start in ein temporäres Verzeichnis; __file__ zeigt dann dorthin.
    Für die Suche nach config/input/output/output zählt daher der Ort der Exe.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
