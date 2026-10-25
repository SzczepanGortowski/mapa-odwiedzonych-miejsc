"""Wczytywanie i czyszczenie danych o odwiedzonych miejscach."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import DATA_FILE, EXAMPLE_FILE
from .geo import haversine_km

REQUIRED_COLUMNS = ["lp", "rok", "lat", "lon", "nazwa", "kolor"]
# Kolumny dokładane przez `scripts/enrich_places.py`. Plik bez nich nadal się
# wczyta — państwo będzie nieznane, a UNESCO puste.
ENRICHED_COLUMNS = ["panstwo", "unesco", "unesco_obiekt"]
CANONICAL_COLUMNS = REQUIRED_COLUMNS + ENRICHED_COLUMNS
CSV_SEPARATOR = ";"
CSV_ENCODING = "utf-8-sig"

DEFAULT_GROUP = "blue"
UNKNOWN_COUNTRY = "nieznane"
TRUE_VALUES = {"tak", "true", "1", "yes", "y", "t"}
# Jedno miejsce bywa opisane kilkoma wpisami z Listy UNESCO (Padwa, Tivoli) —
# w CSV trzymamy je w jednej komórce rozdzielone tym separatorem.
SITE_SEPARATOR = " | "
# Dwa punkty o tej samej nazwie bliżej niż tyle kilometrów to to samo miejsce
# (np. dwa zapisy współrzędnych Gdańska); dalej — dwa różne (Wenecja pod
# Żninem i Wenecja we Włoszech).
SAME_PLACE_RADIUS_KM = 25.0
# Twarda spacja potrafi trafić do komórki przy kopiowaniu współrzędnych z
# Wikipedii albo Map Google i psuje konwersję na liczbę.
WHITESPACE_CHARS = "   \t\r\n "


@dataclass(frozen=True)
class Dataset:
    """Oczyszczone dane wraz z listą problemów napotkanych przy wczytywaniu."""

    frame: pd.DataFrame
    issues: list[str]

    def __len__(self) -> int:
        return len(self.frame)


def _strip_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip(WHITESPACE_CHARS)


def _to_number(series: pd.Series) -> pd.Series:
    """Konwersja na liczbę tolerująca przecinek dziesiętny i twarde spacje."""
    text = _strip_text(series).str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce")


def clean_frame(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalizuje surową ramkę do kanonicznego schematu.

    Zwraca oczyszczoną ramkę oraz listę komunikatów o odrzuconych wierszach,
    żeby żaden wiersz nie znikał z mapy po cichu.
    """
    issues: list[str] = []
    frame = raw.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"W danych brakuje kolumn: {', '.join(missing)}")

    for column in ENRICHED_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
            issues.append(
                f"brak kolumny `{column}` — uruchom `python scripts/enrich_places.py`"
            )

    frame = frame[CANONICAL_COLUMNS]
    frame["nazwa"] = _strip_text(frame["nazwa"])
    frame["kolor"] = _strip_text(frame["kolor"]).str.lower().fillna(DEFAULT_GROUP)
    frame["kolor"] = frame["kolor"].replace("", DEFAULT_GROUP)
    frame["panstwo"] = _strip_text(frame["panstwo"]).fillna("").replace("", UNKNOWN_COUNTRY)
    frame["unesco_obiekt"] = _strip_text(frame["unesco_obiekt"]).fillna("")
    frame["unesco"] = _strip_text(frame["unesco"]).str.lower().isin(TRUE_VALUES)
    for column in ("lp", "rok", "lat", "lon"):
        frame[column] = _to_number(frame[column])

    before = len(frame)
    frame = frame.dropna(subset=["rok", "lat", "lon", "nazwa"])
    frame = frame[frame["nazwa"] != ""]
    if dropped := before - len(frame):
        issues.append(f"pominięto {dropped} wierszy bez nazwy, roku lub współrzędnych")

    before = len(frame)
    in_range = frame["lat"].between(-90, 90) & frame["lon"].between(-180, 180)
    frame = frame[in_range]
    if dropped := before - len(frame):
        issues.append(f"pominięto {dropped} wierszy ze współrzędnymi poza zakresem")

    frame["rok"] = frame["rok"].astype(int)
    frame["lp"] = frame["lp"].fillna(0).astype(int)
    for column in ("nazwa", "kolor", "panstwo", "unesco_obiekt"):
        frame[column] = frame[column].astype(str)
    return frame.reset_index(drop=True), issues


def _place_ids(frame: pd.DataFrame) -> pd.Series:
    """Nadaje identyfikator miejsca — nazwa plus skupisko współrzędnych.

    Sama nazwa nie wystarcza: w danych są dwie Wenecje (pod Żninem i we
    Włoszech) oraz dwa Zagórowy. Z drugiej strony to samo miasto bywa zapisane
    z lekko innymi współrzędnymi, więc nie można ich porównywać dokładnie.
    """
    identifiers = pd.Series("", index=frame.index, dtype="object")
    for name, group in frame.groupby("nazwa", sort=False):
        anchors: list[tuple[float, float]] = []
        for index, row in group.iterrows():
            for number, (lat, lon) in enumerate(anchors):
                if haversine_km(lat, lon, row["lat"], row["lon"]) <= SAME_PLACE_RADIUS_KM:
                    break
            else:
                anchors.append((row["lat"], row["lon"]))
                number = len(anchors) - 1
            identifiers.at[index] = name if number == 0 else f"{name} #{number + 1}"
    return identifiers


def _split_sites(value: str) -> list[str]:
    return [name.strip() for name in value.split(SITE_SEPARATOR.strip()) if name.strip()]


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    """Dokłada kolumny pochodne wykorzystywane w UI."""
    frame = frame.sort_values(["rok", "lp"]).reset_index(drop=True)
    frame["miejsce_id"] = _place_ids(frame)
    frame["unesco_obiekty"] = frame["unesco_obiekt"].map(_split_sites)
    first_visit = frame.groupby("miejsce_id")["rok"].transform("min")
    frame["pierwsza_wizyta"] = first_visit
    frame["powrot"] = frame["rok"] > first_visit
    frame["wizyt_lacznie"] = frame.groupby("miejsce_id")["miejsce_id"].transform("size")
    frame["etykieta"] = frame["nazwa"] + " (" + frame["rok"].astype(str) + ")"
    return frame


def load_dataset(path: Path | str = DATA_FILE) -> Dataset:
    """Wczytuje kanoniczny plik CSV projektu."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Nie znaleziono pliku z danymi: {path}\n"
            "Prywatne dane nie są częścią repozytorium. Zacznij od kopii pliku "
            "przykładowego:\n"
            f"    copy {EXAMPLE_FILE.name} {path.name}   (w katalogu {path.parent})"
        )

    raw = pd.read_csv(
        path,
        sep=CSV_SEPARATOR,
        encoding=CSV_ENCODING,
        dtype=str,
        keep_default_na=False,
    )
    cleaned, issues = clean_frame(raw)
    return Dataset(frame=enrich(cleaned), issues=issues)
