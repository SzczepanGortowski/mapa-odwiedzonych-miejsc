"""Jednorazowa migracja danych z ery R do kanonicznego CSV projektu.

Stare pliki (`Pozycje — kopia*.csv`) były zapisane w Windows-1250, miały
średnik jako separator, cztery puste kolumny na końcu i sporadyczne twarde
spacje (U+00A0) sklejone ze współrzędną. Skrypt czyta wszystkie warianty,
scala je, czyści i zapisuje jeden plik `data/pozycje.csv` w UTF-8.

Skrypt został w repozytorium jako dokumentacja pochodzenia danych — same pliki
źródłowe z ery R nie są jego częścią, więc katalog trzeba wskazać ręcznie.

Uruchomienie:
    python scripts/migrate_from_r.py --source <katalog> --output data/pozycje.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wycieczki.data import REQUIRED_COLUMNS, clean_frame  # noqa: E402

LEGACY_ENCODING = "cp1250"
LEGACY_SEPARATOR = ";"
# Nagłówki w plikach z R -> nazwy kanoniczne używane w projekcie.
LEGACY_HEADER_MAP = {
    "Lp": "lp",
    "Rok": "rok",
    "X": "lat",  # w danych z R X trzymał szerokość geograficzną...
    "Y": "lon",  # ...a Y długość, wbrew konwencji nazw
    "Opis": "nazwa",
    "Color": "kolor",
}


def read_legacy_csv(path: Path) -> pd.DataFrame:
    """Wczytuje pojedynczy plik CSV w formacie z projektu R."""
    frame = pd.read_csv(
        path,
        sep=LEGACY_SEPARATOR,
        encoding=LEGACY_ENCODING,
        dtype=str,
        keep_default_na=False,
    )
    frame = frame[[column for column in LEGACY_HEADER_MAP if column in frame.columns]]
    return frame.rename(columns=LEGACY_HEADER_MAP)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Katalog ze starymi plikami CSV z projektu R.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "pozycje.csv",
        help="Docelowy plik CSV w UTF-8.",
    )
    args = parser.parse_args()

    legacy_files = sorted(args.source.glob("*.csv"))
    if not legacy_files:
        parser.error(f"Nie znaleziono plików CSV w {args.source}")

    frames = []
    for path in legacy_files:
        frame = read_legacy_csv(path)
        print(f"  {path.name}: {len(frame)} wierszy")
        frames.append(frame)

    merged = pd.concat(frames, ignore_index=True)
    cleaned, issues = clean_frame(merged)

    # Scalanie kilku kopii tego samego zbioru — ta sama wizyta może wystąpić
    # w każdym z plików źródłowych.
    before = len(cleaned)
    cleaned = cleaned.drop_duplicates(subset=["rok", "nazwa", "lat", "lon"])
    duplicates = before - len(cleaned)

    cleaned = cleaned.sort_values(["rok", "lp"]).reset_index(drop=True)
    cleaned["lp"] = range(1, len(cleaned) + 1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Państwo i UNESCO dokłada dopiero scripts/enrich_places.py.
    cleaned[REQUIRED_COLUMNS].to_csv(
        args.output,
        sep=";",
        index=False,
        encoding="utf-8-sig",  # BOM, żeby Excel PL otwierał plik bez kombinowania
    )

    print(f"\nZapisano {len(cleaned)} wizyt do {args.output}")
    print(f"  duplikaty między plikami: {duplicates}")
    for issue in issues:
        print(f"  uwaga: {issue}")
    print("\nNastępny krok: python scripts/enrich_places.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
