import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Station:
    label: str
    source_stations: list
    aufgestellte_betten: int | None


@dataclass
class Config:
    report_title: str
    stations: list
    bgl_abrechnungsarten: list
    bgl_als_begleitperson_zaehlen: bool
    sperrgruende_sheet_praferenz: list
    sperrgrund_ausschluss: list
    sperrgrund_mapping: dict
    sperrgrund_default_kategorie: str
    sperrung_spalten: list

    @property
    def station_lookup(self):
        lookup = {}
        for st in self.stations:
            for src in st.source_stations:
                lookup[str(src).strip()] = st
        return lookup


def load_config(path: str | Path) -> Config:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    stations = [
        Station(
            label=s["label"],
            source_stations=[str(x) for x in s.get("source_stations", [s["label"]])],
            aufgestellte_betten=s.get("aufgestellte_betten"),
        )
        for s in raw["stations"]
    ]
    return Config(
        report_title=raw.get("report_title", "Belegung Wochensicht"),
        stations=stations,
        bgl_abrechnungsarten=[str(x).strip().upper() for x in raw.get("bgl_abrechnungsarten", ["BGL"])],
        bgl_als_begleitperson_zaehlen=bool(raw.get("bgl_als_begleitperson_zaehlen", True)),
        sperrgruende_sheet_praferenz=list(raw.get("sperrgruende_sheet_praferenz", [])),
        sperrgrund_ausschluss={str(x).strip().lower() for x in raw.get("sperrgrund_ausschluss", [])},
        sperrgrund_mapping={k: [str(v).strip() for v in vals] for k, vals in raw.get("sperrgrund_mapping", {}).items()},
        sperrgrund_default_kategorie=raw.get("sperrgrund_default_kategorie"),
        sperrung_spalten=list(raw.get("sperrung_spalten", [])),
    )


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "stations.json"
