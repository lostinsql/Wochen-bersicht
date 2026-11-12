# Belegungsübersicht DHM

Erstellt die wöchentliche Belegungsübersicht (PDF, Layout wie die bisherige
„Belegungsübersicht DHM_YYYY_KW NN.pdf") teilautomatisiert aus den täglichen
KIS-Exporten und den tagesaktuellen Bettensperrgründen.

## Voraussetzungen

- Python 3.10 oder neuer (auf dem Zielrechner installiert)
- Abhängigkeiten installieren (einmalig pro Rechner):

  ```
  pip install -r requirements.txt
  ```

## Arbeitsablauf

1. Die Exportdatei des jeweiligen Tages aus dem KIS in den Ordner `input/`
   speichern. Das Datum muss im Dateinamen stehen, z. B.:

   ```
   input/2026-11-19_Belegungsexport.xlsx
   input/2026-11-19_CO-EL-tagesaktuelle Sperrgruende.xlsx
   ```

   `.xlsx` und `.csv` werden unterstützt. Datum im Namen: `JJJJ-MM-TT` oder
   `TT.MM.JJJJ`. Fehlt das Datum im Namen, wird bei Sperrgründen auf die
   „Ausführungszeit" im Blatt „Berichtsinfos und Filter" bzw. bei Exporten auf
   den Aufnahmezeitpunkt in den Daten zurückgegriffen.

2. Bericht erstellen – zwei Möglichkeiten:

   **Dialog (lokaler Rechner):** `python belegung.py` (ohne Argumente)
   startet einen Dialog. Dort wählen: *Letzte Woche*, *Kalenderwoche*
   (Jahr + KW) oder *Zeitraum von/bis*, plus Eingangs-/Zielordner, und dann
   „PDF erstellen". Die PDF landet im Zielordner (Default: `output/`).

   **Kommandozeile (Server/Cron, keine GUI nötig):**

   ```
   python belegung.py --modus letzte-woche
   python belegung.py --modus kw --jahr 2026 --kw 45
   python belegung.py --modus zeitraum --von 2026-11-02 --bis 2026-11-08
   python belegung.py --modus kw --jahr 2026 --kw 45 --xlsx   # zusätzlich Excel-Wochensicht
   ```

   Weitere Optionen: `--input ORDNER`, `--output ORDNER`, `--config DATEI`.

3. Die PDF heißt z. B. `Belegungsübersicht DHM_2026_KW 45.pdf` (bei KW-Auswahl)
   bzw. `Belegungsübersicht DHM_2026-11-02_bis_2026-11-08.pdf` (bei Zeitraum)
   und kann direkt gedruckt/versendet werden.

## Was gerechnet wird

- Pro Tag und Station: Anzahl Patienten aus dem Export, **Begleitpersonen
  (Abr.-Art „BGL") werden nicht als Patienten gezählt**, erscheinen aber in der
  Spalte „Begleit-person".
- Bettensperrungen aus der Sperrgründe-Datei, **„orig. umgewidmet" wird
  ausgeschlossen** (Blatt „Relevante Bettensperrungen" wird bevorzugt, sonst
  „Alle Bettensperrungen" ohne die ausgeschlossenen Gründe). Die Sperrgründe
  werden über `config/stations.json` den Spalten zugeordnet (Bau, Personal
  Pflege, Sonstiges Pflege, ärztliches Personal, Isolation, Feiertag,
  Begleitperson).
- Belegbare Betten = aufgestellte Betten − Sperrungen − Begleitpersonen;
  Auslastung = belegte / belegbare Betten; „Gesamt" summiert je Tag.
- Stationen 1.1 + 1.3 werden als „CCC" zusammengefasst, 0.5 als „CPU"
  (konfigurierbar in `config/stations.json`, inkl. der aufgestellten Betten
  je Station).
- „Datenstand" in der PDF ist das Datum des neuesten Exportes im Eingangsordner.
- Fehlt für einen Tag eine Datei, gibt es einen Hinweis auf der Konsole und die
  entsprechenden Zellen bleiben leer.

## Konfiguration

`config/stations.json` enthält Stationsliste/-zuordnung, aufgestellte Betten,
BGL-Abr.-Arten, das Sperrgrund-Mapping und die ausgeschlossenen Sperrgründe.
Anpassungen dort wirken sich auf alle Berichte aus.

## Übertragung auf andere Rechner / späterer Server

Der Ordner ist in sich abgeschlossen: Auf einem anderen Rechner den Ordner
kopieren, `pip install -r requirements.txt` ausführen, `input/` und `output/`
können z. B. auf einem Netzlaufwerk liegen (`--input`/`--output`). Auf einem
zentralen Server läuft das Skript ohne Dialog per Kommandozeile, z. B. cron:

```
0 7 * * 1  cd /pfad/belegungsbericht && python belegung.py --modus letzte-woche --input /pfad/input --output /pfad/output
```

## Aufbau

```
belegung.py            Einstieg: Dialog (ohne Argumente) oder CLI
belegung/eingang.py    Einlesen der Export- und Sperrgründe-Dateien
belegung/bericht.py    Berichtsmodell (Zeitraum, Stationen, Gesamt)
belegung/pdf_ausgabe.py  PDF-Ausgabe (Querformat A4)
belegung/xlsx_ausgabe.py Optionale Excel-Wochensicht
config/stations.json   Stationen, Betten, Sperrgrund-Mapping
input/                 hier landen die Tagesdateien (Datum im Dateinamen)
output/                hier landen die fertigen PDFs
```
