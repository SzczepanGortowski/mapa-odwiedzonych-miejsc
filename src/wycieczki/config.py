"""Ścieżki, paleta i stałe współdzielone przez cały projekt."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_FILE = DATA_DIR / "pozycje.csv"
# Plik z kilkoma miejscami, trzymany w repozytorium zamiast prywatnych danych.
EXAMPLE_FILE = DATA_DIR / "pozycje.example.csv"

APP_TITLE = "Mapa wycieczek"
APP_ICON = "🗺️"

# Sekwencyjna paleta dla lat: od chłodnego granatu (najstarsze wyjazdy)
# do ciepłego bursztynu (najnowsze). Interpolowana na liczbę lat w danych.
YEAR_GRADIENT = ["#1d4e89", "#2e8bc0", "#3fbfa3", "#f0b429", "#e8590c"]

# Kolory z pliku źródłowego to nazwy markerów Leaflet z projektu R —
# tutaj tylko ich odpowiedniki HEX, żeby zachować dotychczasowe grupowanie.
LEGACY_COLORS = {
    "blue": "#2e6fdb",
    "red": "#dc3545",
    "green": "#2f9e44",
    "orange": "#f76707",
    "purple": "#845ef7",
    "white": "#adb5bd",
}
FALLBACK_COLOR = "#495057"

TILE_LAYERS = {
    "Jasna (CartoDB Positron)": "cartodbpositron",
    "Ciemna (CartoDB Dark Matter)": "cartodbdark_matter",
    "Klasyczna (OpenStreetMap)": "openstreetmap",
}
