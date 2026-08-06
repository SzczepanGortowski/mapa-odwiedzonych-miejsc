"""Dopisuje do `data/pozycje.csv` kolumny `panstwo`, `unesco` i `unesco_obiekt`.

Państwo wyznaczamy ze współrzędnych (offline, pakiet `reverse_geocoder`), więc
nie zależy od zapisu nazwy. Lista UNESCO jest kuratorowana ręcznie — trzyma się
wyłącznie **Listy światowego dziedzictwa** (obiekty), bez dziedzictwa
niematerialnego i bez listy informacyjnej (tentative list).

Skrypt jest idempotentny: można go puścić ponownie po dopisaniu nowych miejsc.

Uruchomienie:
    pip install reverse_geocoder
    python scripts/enrich_places.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wycieczki.config import DATA_FILE  # noqa: E402
from wycieczki.data import (  # noqa: E402
    CANONICAL_COLUMNS,
    CSV_ENCODING,
    CSV_SEPARATOR,
    REQUIRED_COLUMNS,
    SITE_SEPARATOR,
)

# Kod ISO -> nazwa po polsku. Gibraltar nie jest państwem (terytorium zamorskie
# Wielkiej Brytanii), ale w statystykach wygodniej trzymać go osobno.
COUNTRY_NAMES = {
    "AT": "Austria",
    "BA": "Bośnia i Hercegowina",
    "CZ": "Czechy",
    "DE": "Niemcy",
    "ES": "Hiszpania",
    "GI": "Gibraltar",
    "HR": "Chorwacja",
    "IE": "Irlandia",
    "IT": "Włochy",
    "LT": "Litwa",
    "PL": "Polska",
    "VA": "Watykan",
}

# Punkty, w których najbliższa miejscowość z bazy geonames leży po drugiej
# stronie granicy. Klucz: nazwa miejsca w danych, wartość: poprawny kod kraju.
COUNTRY_OVERRIDES = {
    "Grödig": "AT",  # baza podpowiada Marktschellenberg w Bawarii
}

# Obiekty z Listy światowego dziedzictwa UNESCO.
# Klucz: (nazwa miejsca w danych, kod kraju) — rozróżnia Wenecję pod Żninem
# od Wenecji w Wenecji Euganejskiej.
# Wartość: krotka wpisów z Listy. Jedno miejsce może mieć kilka wpisów (Padwa,
# Tivoli), a jeden wpis obejmować kilka miejsc — wtedy nazwa musi brzmieć
# DOKŁADNIE tak samo w każdym miejscu, bo po niej liczymy unikalne wpisy
# (Wieliczka i Bochnia, Jawor i Świdnica, Łęknica i Bad Muskau, Conegliano
# i Valdobbiadene).
UNESCO_SITES = {
    # --- Polska ---
    ("Kraków", "PL"): ("Historyczne centrum Krakowa",),
    ("Warszawa", "PL"): ("Historyczne centrum Warszawy",),
    ("Toruń", "PL"): ("Średniowieczny zespół miejski Torunia",),
    ("Malbork", "PL"): ("Zamek krzyżacki w Malborku",),
    ("Zamość", "PL"): ("Stare Miasto w Zamościu",),
    ("Wieliczka", "PL"): ("Królewskie Kopalnie Soli w Wieliczce i Bochni",),
    ("Bochnia", "PL"): ("Królewskie Kopalnie Soli w Wieliczce i Bochni",),
    ("Kalwaria Zebrzydowska", "PL"): (
        "Zespół pielgrzymkowo-parkowy w Kalwarii Zebrzydowskiej",
    ),
    ("Jawor", "PL"): ("Kościoły Pokoju w Jaworze i Świdnicy",),
    ("Świdnica", "PL"): ("Kościoły Pokoju w Jaworze i Świdnicy",),
    ("Wrocław", "PL"): ("Hala Stulecia we Wrocławiu",),
    ("Łęknica", "PL"): ("Park Mużakowski",),
    ("Wołosate", "PL"): ("Pradawne i pierwotne lasy bukowe Karpat",),
    # --- Niemcy ---
    ("Bad Muskau", "DE"): ("Park Mużakowski",),
    ("Berlin", "DE"): ("Wyspa Muzeów w Berlinie",),
    ("Lubeka", "DE"): ("Hanzeatyckie miasto Lubeka",),
    ("Wismar", "DE"): ("Historyczne centra Stralsundu i Wismaru",),
    ("Schwerin", "DE"): ("Zespół rezydencjonalny w Schwerinie",),
    # --- Austria ---
    ("Salzburg", "AT"): ("Historyczne centrum Salzburga",),
    ("Hallstatt", "AT"): ("Krajobraz kulturowy Hallstatt-Dachstein / Salzkammergut",),
    # --- Włochy ---
    ("Rzym", "IT"): ("Historyczne centrum Rzymu",),
    ("Tivoli", "IT"): ("Villa d'Este w Tivoli",),
    ("Cerveteri", "IT"): ("Nekropolie etruskie w Cerveteri i Tarquinii",),
    ("Akwileja", "IT"): ("Strefa archeologiczna i bazylika patriarchalna w Akwilei",),
    ("Palmanowa", "IT"): ("Weneckie dzieła obronne XVI-XVII w.",),
    ("Cividale del Friuli", "IT"): ("Longobardowie we Włoszech — miejsca władzy",),
    ("Conegliano", "IT"): ("Wzgórza Prosecco między Conegliano a Valdobbiadene",),
    ("Valdobbiadene", "IT"): ("Wzgórza Prosecco między Conegliano a Valdobbiadene",),
    ("Vicenza", "IT"): ("Vicenza i wille palladiańskie w Wenecji Euganejskiej",),
    ("Werona", "IT"): ("Miasto Werona",),
    ("Padwa", "IT"): (
        "Ogród botaniczny w Padwie",
        "Padwa urbs picta — XIV-wieczne cykle fresków",
    ),
    ("Wenecja", "IT"): ("Wenecja i jej laguna",),
    # --- Watykan ---
    ("Watykan", "VA"): ("Watykan",),
    # --- Chorwacja ---
    ("Split", "HR"): ("Zespół historyczny Splitu z pałacem Dioklecjana",),
    ("Trogir", "HR"): ("Historyczne miasto Trogir",),
    ("Stari Grad", "HR"): ("Równina Starego Gradu na Hvarze",),
    ("Szybenik", "HR"): ("Katedra św. Jakuba w Szybeniku",),
    # --- Bośnia i Hercegowina ---
    ("Mostar", "BA"): ("Stary Most i stare miasto w Mostarze",),
    # --- Hiszpania i Gibraltar ---
    ("Sewilla", "ES"): ("Katedra, Alkazar i Archiwum Indii w Sewilli",),
    ("Antequera", "ES"): ("Zespół dolmenów w Antequerze",),
    ("Gibraltar", "GI"): ("Kompleks jaskiń Gorhama",),
    # --- Litwa ---
    ("Wilno", "LT"): ("Historyczne centrum Wilna",),
    ("Kowno", "LT"): ("Modernistyczne Kowno 1919-1939",),
    ("Kiernów", "LT"): ("Rezerwat archeologiczny w Kiernowie",),
    # Jeden z trzech litewskich punktów Łuku Struvego wpisanych na Listę
    # (pozostałe dwa to Gireišiai i Paliepiukai).
    ("Meškonys", "LT"): ("Łuk geodezyjny Struvego",),
}

def resolve_countries(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Zwraca kody ISO i polskie nazwy państw dla każdego wiersza."""
    import reverse_geocoder  # import lokalny — pakiet potrzebny tylko tutaj

    matches = reverse_geocoder.search(
        [(float(lat), float(lon)) for lat, lon in zip(frame["lat"], frame["lon"])],
        mode=1,
    )
    codes = pd.Series([match["cc"] for match in matches], index=frame.index)
    codes = frame["nazwa"].map(COUNTRY_OVERRIDES).fillna(codes)

    unknown = sorted(set(codes) - set(COUNTRY_NAMES))
    if unknown:
        raise SystemExit(
            f"Brak polskiej nazwy dla kodów: {', '.join(unknown)}. "
            "Uzupełnij COUNTRY_NAMES w scripts/enrich_places.py."
        )
    return codes, codes.map(COUNTRY_NAMES)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DATA_FILE)
    args = parser.parse_args()

    frame = pd.read_csv(
        args.file, sep=CSV_SEPARATOR, encoding=CSV_ENCODING, dtype=str, keep_default_na=False
    )
    # Bierzemy tylko kolumny bazowe — resztę i tak nadpisujemy, a przy
    # ponownym uruchomieniu nie chcemy ich zdublować.
    frame = frame[REQUIRED_COLUMNS]

    codes, frame["panstwo"] = resolve_countries(frame)
    keys = list(zip(frame["nazwa"], codes))
    sites = [UNESCO_SITES.get(key, ()) for key in keys]
    frame["unesco_obiekt"] = [SITE_SEPARATOR.join(entry) for entry in sites]
    frame["unesco"] = ["tak" if entry else "nie" for entry in sites]

    frame[CANONICAL_COLUMNS].to_csv(
        args.file, sep=CSV_SEPARATOR, index=False, encoding=CSV_ENCODING
    )

    matched = {key for key in keys if key in UNESCO_SITES}
    unused = sorted(set(UNESCO_SITES) - matched)
    inscriptions = {name for entry in sites for name in entry}

    counts = frame["panstwo"].value_counts().to_dict()
    print(f"Zapisano {len(frame)} wierszy do {args.file}")
    print(f"  państwa: {len(counts)} — {counts}")
    print(f"  wizyty w miejscach z UNESCO: {(frame['unesco'] == 'tak').sum()}")
    print(f"  miejsc z UNESCO: {len(matched)}")
    print(f"  unikalnych wpisów na Liście: {len(inscriptions)}")
    for key in unused:
        print(f"  uwaga: wpis UNESCO {key} nie pasuje do żadnego miejsca w danych")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
