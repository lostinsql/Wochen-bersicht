"""Aufbau des Wochen-/Zeitraum-Berichtsmodells aus den eingelesenen Daten."""

import datetime as dt
from dataclasses import dataclass, field

from .config import Config

WOCHENTAGE = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Modell-Keys der Sperrungsspalten (Reihenfolge wie in der PDF-/Excel-Ausgabe)
SPERRUNG_KEYS = [
    "Sperrung Bau",
    "Sperrung Personal Pflege",
    "Sperrung Sonstiges Pflege",
    "Sperrung ärztliches Personl",
    "Sperrung Isolation",
    "Sperrung Feiertag",
    "Begleitperson",
]


@dataclass
class TagesZeile:
    datum: dt.date
    aufgestellt: int | None = None
    sperrungen: dict = field(default_factory=dict)
    belegbar: int | None = None
    belegte: int | None = None
    auslastung: float | None = None


@dataclass
class StationBlock:
    label: str
    aufgestellt: int | None
    zeilen: list = field(default_factory=list)


@dataclass
class Bericht:
    titel: str
    subtitel: str
    datenstand: dt.date | None
    stationen: list
    gesamt: list
    warnungen: list = field(default_factory=list)


def _kw_datum(jahr: int, kw: int) -> tuple[dt.date, dt.date]:
    montag = dt.date.fromisocalendar(jahr, kw, 1)
    return montag, montag + dt.timedelta(days=6)


def resolve_period(modus: str, jahr: int | None = None, kw: int | None = None,
                   von: dt.date | None = None, bis: dt.date | None = None,
                   heute: dt.date | None = None) -> tuple[dt.date, dt.date, str]:
    """Ermittelt Start/Ende des Berichtszeitraums und den Untertitel."""
    heute = heute or dt.date.today()
    if modus == "letzte-woche":
        ziel = heute - dt.timedelta(days=7)
        start, ende = _kw_datum(ziel.isocalendar()[0], ziel.isocalendar()[1])
        return start, ende, f"KW {ziel.isocalendar()[1]} / {ziel.isocalendar()[0]}"
    if modus == "kw":
        if jahr is None or kw is None:
            raise ValueError("Für Modus 'kw' werden --jahr und --kw benötigt")
        start, ende = _kw_datum(jahr, kw)
        return start, ende, f"KW {kw} / {jahr}"
    if modus == "zeitraum":
        if von is None or bis is None:
            raise ValueError("Für Modus 'zeitraum' werden --von und --bis benötigt")
        if bis < von:
            raise ValueError("--bis liegt vor --von")
        return von, bis, f"Zeitraum: {von.strftime('%d.%m.%Y')} - {bis.strftime('%d.%m.%Y')}"
    raise ValueError(f"Unbekannter Modus: {modus}")


def _sperrgrund_kategorie(grund: str, config: Config, warnungen: list) -> str | None:
    g = grund.strip().lower()
    if g in config.sperrgrund_ausschluss:
        return None
    for kategorie, gruende in config.sperrgrund_mapping.items():
        for gr in gruende:
            if gr.strip().lower() == g:
                return kategorie
    if config.sperrgrund_default_kategorie:
        warnungen.append(f"Unbekannter Sperrgrund '{grund}' -> '{config.sperrgrund_default_kategorie}'")
        return config.sperrgrund_default_kategorie
    warnungen.append(f"Unbekannter Sperrgrund '{grund}' wird ignoriert")
    return None


def build_bericht(config: Config, scan: dict, start: dt.date, ende: dt.date, subtitel: str) -> Bericht:
    warnungen = list(scan.get("warnungen", []))
    lookup = config.station_lookup

    exporte = scan.get("exporte", {})
    sperrungen = scan.get("sperrungen", {})

    # Stationen aus Config plus ggf. unbekannte Stationen aus den Daten
    blocks = {st.label: StationBlock(label=st.label, aufgestellt=st.aufgestellte_betten) for st in config.stations}
    extra = {}

    def _block_fuer(raw_station: str) -> StationBlock:
        st = lookup.get(raw_station)
        if st is not None:
            return blocks[st.label]
        if raw_station not in extra:
            extra[raw_station] = StationBlock(label=f"Station {raw_station}", aufgestellt=None)
            warnungen.append(f"Unbekannte Station '{raw_station}' in den Exportdaten ergänzt (aufgestellte Betten unbekannt)")
        return extra[raw_station]

    tage = []
    d = start
    while d <= ende:
        tage.append(d)
        d += dt.timedelta(days=1)

    gesamt = []
    for datum in tage:
        exp = exporte.get(datum)
        sperr = sperrungen.get(datum)
        if exp is None:
            warnungen.append(f"Kein Belegungsexport für {datum.strftime('%d.%m.%Y')} vorhanden")
        if sperr is None:
            warnungen.append(f"Keine Sperrgründe für {datum.strftime('%d.%m.%Y')} vorhanden")

        zeilen_pro_block = {label: TagesZeile(datum=datum) for label in blocks}
        for label in extra:
            zeilen_pro_block[label] = TagesZeile(datum=datum)

        if exp:
            for raw, counts in exp["station_counts"].items():
                block = _block_fuer(raw)
                z = zeilen_pro_block[block.label]
                z.belegte = (z.belegte or 0) + counts["patienten"]
                if config.bgl_als_begleitperson_zaehlen:
                    z.sperrungen["Begleitperson"] = z.sperrungen.get("Begleitperson", 0) + counts["bgl"]

        if sperr:
            for raw, gruende in sperr["sperrungen"].items():
                block = _block_fuer(raw)
                z = zeilen_pro_block[block.label]
                for grund, betten in gruende.items():
                    kat = _sperrgrund_kategorie(grund, config, warnungen)
                    if kat is None:
                        continue
                    z.sperrungen[kat] = z.sperrungen.get(kat, 0) + betten

        g = TagesZeile(datum=datum)
        for label, block in list(blocks.items()) + list(extra.items()):
            z = zeilen_pro_block[label]
            block.zeilen.append(z)
            auf = block.aufgestellt
            if z.aufgestellt is None:
                z.aufgestellt = auf
            sperr_sum = sum(z.sperrungen.get(k, 0) for k in config.sperrung_spalten)
            if auf is not None:
                z.belegbar = auf - sperr_sum
            if z.belegbar is not None and z.belegbar > 0 and z.belegte is not None:
                z.auslastung = z.belegte / z.belegbar
            g.aufgestellt = (g.aufgestellt or 0) + (auf or 0)
            for k in config.sperrung_spalten:
                g.sperrungen[k] = g.sperrungen.get(k, 0) + z.sperrungen.get(k, 0)
            g.belegbar = (g.belegbar or 0) + (z.belegbar or 0)
            g.belegte = (g.belegte or 0) + (z.belegte or 0)
        if g.belegbar and g.belegbar > 0 and g.belegte is not None:
            g.auslastung = g.belegte / g.belegbar
        gesamt.append(g)

    alle_stationen = list(blocks.values()) + list(extra.values())
    datenstand = None
    if exporte:
        datenstand = max(exporte.keys())
    elif sperrungen:
        datenstand = max(sperrungen.keys())

    return Bericht(
        titel=config.report_title,
        subtitel=subtitel,
        datenstand=datenstand,
        stationen=alle_stationen,
        gesamt=gesamt,
        warnungen=warnungen,
    )


def dateien_name(bericht: Bericht, start: dt.date, ende: dt.date, modus: str, jahr=None, kw=None) -> str:
    if modus == "kw" and jahr and kw:
        return f"Belegungsübersicht DHM_{jahr}_KW {kw}.pdf"
    return f"Belegungsübersicht DHM_{start.strftime('%Y-%m-%d')}_bis_{ende.strftime('%Y-%m-%d')}.pdf"
