"""Testy czyszczenia danych: twarde spacje, przecinek dziesiętny, braki, złe współrzędne."""

from __future__ import annotations

import pandas as pd
import pytest

from conftest import needs_private_data

from wycieczki.config import DATA_FILE, EXAMPLE_FILE
from wycieczki.data import (
    CANONICAL_COLUMNS,
    CSV_ENCODING,
    CSV_SEPARATOR,
    clean_frame,
    enrich,
    load_dataset,
)


def make_frame(**overrides) -> pd.DataFrame:
    """Dwuwierszowa ramka w formacie surowego CSV; `overrides` mogą ją wydłużyć."""
    base = {
        "lp": ["1", "2"],
        "rok": ["2020", "2021"],
        "lat": ["52.0", "53.0"],
        "lon": ["19.0", "20.0"],
        "nazwa": ["Toruń", "Gdańsk"],
        "kolor": ["blue", "red"],
    }
    rows = max((len(value) for value in overrides.values()), default=len(base["lp"]))
    frame = pd.DataFrame({key: (value * rows)[:rows] for key, value in base.items()})
    # Kolumny z enrich_places — domyślnie neutralne, testy nadpisują je wprost.
    frame["panstwo"] = "Polska"
    frame["unesco"] = "nie"
    frame["unesco_obiekt"] = ""
    for column, value in overrides.items():
        frame[column] = value
    return frame


def test_strips_nonbreaking_space_in_coordinates():
    frame, issues = clean_frame(make_frame(lat=["\xa054.6596783", "53.0"]))
    assert len(frame) == 2
    assert frame.loc[0, "lat"] == pytest.approx(54.6596783)
    assert issues == []


def test_accepts_decimal_comma():
    frame, _ = clean_frame(make_frame(lon=["19,4422", "20.0"]))
    assert frame.loc[0, "lon"] == pytest.approx(19.4422)


def test_drops_rows_without_coordinates():
    frame, issues = clean_frame(make_frame(lat=["", "53.0"]))
    assert len(frame) == 1
    assert "pominięto 1 wierszy" in issues[0]


def test_drops_coordinates_out_of_range():
    frame, issues = clean_frame(make_frame(lat=["952.0", "53.0"]))
    assert len(frame) == 1
    assert "poza zakresem" in issues[0]


def test_missing_column_raises():
    with pytest.raises(ValueError, match="brakuje kolumn"):
        clean_frame(make_frame().drop(columns=["kolor"]))


def test_missing_enriched_columns_are_tolerated():
    """Plik sprzed uruchomienia enrich_places nadal się wczytuje."""
    frame, issues = clean_frame(make_frame().drop(columns=["panstwo", "unesco"]))
    assert frame["panstwo"].tolist() == ["nieznane", "nieznane"]
    assert frame["unesco"].tolist() == [False, False]
    assert any("enrich_places" in issue for issue in issues)


def test_unesco_flag_is_parsed_as_boolean():
    frame, _ = clean_frame(make_frame(unesco=["tak", "nie"]))
    assert frame["unesco"].tolist() == [True, False]
    assert frame["unesco"].dtype == bool


def test_multiple_inscriptions_are_split():
    """Padwa ma dwa wpisy na Liście w jednej komórce CSV."""
    frame, _ = clean_frame(
        make_frame(unesco=["tak", "nie"], unesco_obiekt=["Ogród | Freski", ""])
    )
    enriched = enrich(frame)
    assert enriched.loc[0, "unesco_obiekty"] == ["Ogród", "Freski"]
    assert enriched.loc[1, "unesco_obiekty"] == []


def test_empty_group_falls_back_to_default():
    frame, _ = clean_frame(make_frame(kolor=["", "RED"]))
    assert frame["kolor"].tolist() == ["blue", "red"]


def test_enrich_marks_return_visits():
    frame, _ = clean_frame(
        make_frame(
            lp=["1", "2", "3"],
            rok=["2020", "2021", "2022"],
            lat=["52.0", "52.0", "53.0"],
            lon=["19.0", "19.0", "20.0"],
            nazwa=["Toruń", "Toruń", "Gdańsk"],
            kolor=["blue", "blue", "red"],
        )
    )
    enriched = enrich(frame)
    assert enriched["powrot"].tolist() == [False, True, False]
    assert enriched.loc[0, "wizyt_lacznie"] == 2
    assert enriched.loc[2, "etykieta"] == "Gdańsk (2022)"


def test_same_name_far_apart_is_a_different_place():
    """Wenecja pod Żninem to nie ta sama Wenecja co we Włoszech."""
    frame, _ = clean_frame(
        make_frame(
            lp=["1", "2"],
            rok=["2014", "2025"],
            lat=["52.8056", "45.4371"],
            lon=["17.7608", "12.3327"],
            nazwa=["Wenecja", "Wenecja"],
            panstwo=["Polska", "Włochy"],
        )
    )
    enriched = enrich(frame)
    assert enriched["miejsce_id"].nunique() == 2
    assert enriched["powrot"].tolist() == [False, False]
    assert enriched["wizyt_lacznie"].tolist() == [1, 1]


def test_same_name_nearby_is_the_same_place():
    """Dwa zapisy współrzędnych Gdańska to jedno miejsce, nie dwa."""
    frame, _ = clean_frame(
        make_frame(
            lp=["1", "2"],
            rok=["2016", "2018"],
            lat=["54.3520", "54.3617"],
            lon=["18.6466", "18.6552"],
            nazwa=["Gdańsk", "Gdańsk"],
        )
    )
    enriched = enrich(frame)
    assert enriched["miejsce_id"].nunique() == 1
    assert enriched["powrot"].tolist() == [False, True]


def test_csv_header_matches_schema(dataset_path):
    """Pilnuje, żeby enrich_places nie zdublował kolumn przy powtórnym uruchomieniu."""
    header = pd.read_csv(
        dataset_path, sep=CSV_SEPARATOR, encoding=CSV_ENCODING, nrows=0
    ).columns.tolist()
    assert header == CANONICAL_COLUMNS


def test_dataset_is_internally_consistent(dataset_path):
    """Reguły, które muszą zachodzić i dla prawdziwych danych, i dla przykładu."""
    dataset = load_dataset(dataset_path)
    assert len(dataset) > 0
    assert dataset.issues == []
    assert dataset.frame["lat"].between(-90, 90).all()
    assert dataset.frame["nazwa"].str.strip().eq(dataset.frame["nazwa"]).all()
    assert dataset.frame["panstwo"].ne("nieznane").all()
    # Każdy wpis z flagą UNESCO ma podaną nazwę obiektu i odwrotnie.
    has_site = dataset.frame["unesco_obiekt"].str.len() > 0
    assert has_site.equals(dataset.frame["unesco"])


def test_example_file_shows_off_the_tricky_cases():
    """Plik przykładowy ma pokazywać przypadki brzegowe, które obsługuje kod."""
    frame = load_dataset(EXAMPLE_FILE).frame
    # Dwie różne Wenecje — ta sama nazwa, inne miejsce.
    assert frame[frame["nazwa"] == "Wenecja"]["miejsce_id"].nunique() == 2
    # Jeden wpis UNESCO dzielony przez dwa miejsca.
    assert (frame["unesco_obiekt"] == "Królewskie Kopalnie Soli w Wieliczce i Bochni").sum() == 2
    # Jedno miejsce z dwoma wpisami.
    assert frame.loc[frame["nazwa"] == "Padwa", "unesco_obiekty"].item() == [
        "Ogród botaniczny w Padwie",
        "Padwa urbs picta — XIV-wieczne cykle fresków",
    ]
    # Powrót do tego samego miejsca w innym roku.
    assert frame["powrot"].any()


@needs_private_data
def test_private_dataset_is_complete():
    dataset = load_dataset(DATA_FILE)
    assert len(dataset) > 300
    assert dataset.frame["rok"].nunique() >= 15
