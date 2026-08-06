"""Testy statystyk."""

from __future__ import annotations

import pandas as pd
import pytest

from wycieczki import metrics
from wycieczki.data import clean_frame, enrich


@pytest.fixture
def sample() -> pd.DataFrame:
    frame, _ = clean_frame(
        pd.DataFrame(
            {
                "lp": ["1", "2", "3", "4"],
                "rok": ["2020", "2020", "2021", "2022"],
                "lat": ["52.2297", "50.0647", "52.2297", "54.3520"],
                "lon": ["21.0122", "19.9450", "21.0122", "18.6466"],
                "nazwa": ["Warszawa", "Kraków", "Warszawa", "Gdańsk"],
                "kolor": ["blue", "blue", "red", "green"],
                "panstwo": ["Polska", "Polska", "Polska", "Polska"],
                "unesco": ["tak", "tak", "tak", "nie"],
                "unesco_obiekt": [
                    "Historyczne centrum Warszawy",
                    "Historyczne centrum Krakowa",
                    "Historyczne centrum Warszawy",
                    "",
                ],
            }
        )
    )
    return enrich(frame)


@pytest.fixture
def shared_and_split() -> pd.DataFrame:
    """Wieliczka i Bochnia dzielą jeden wpis, Padwa ma dwa własne."""
    salt = "Królewskie Kopalnie Soli w Wieliczce i Bochni"
    frame, _ = clean_frame(
        pd.DataFrame(
            {
                "lp": ["1", "2", "3"],
                "rok": ["2019", "2019", "2025"],
                "lat": ["49.9874", "49.9691", "45.4080"],
                "lon": ["20.0647", "20.4303", "11.8859"],
                "nazwa": ["Wieliczka", "Bochnia", "Padwa"],
                "kolor": ["blue", "blue", "white"],
                "panstwo": ["Polska", "Polska", "Włochy"],
                "unesco": ["tak", "tak", "tak"],
                "unesco_obiekt": [
                    salt,
                    salt,
                    "Ogród botaniczny w Padwie | Padwa urbs picta",
                ],
            }
        )
    )
    return enrich(frame)


def test_haversine_matches_known_distance():
    # Warszawa - Kraków to około 252 km w linii prostej.
    distance = metrics.haversine_km(52.2297, 21.0122, 50.0647, 19.9450)
    assert distance == pytest.approx(252, abs=5)


def test_summary(sample):
    summary = metrics.summarize(sample)
    assert summary.visits == 4
    assert summary.unique_places == 3
    assert summary.return_visits == 1
    assert (summary.first_year, summary.last_year) == (2020, 2022)
    assert summary.countries == 1
    # Warszawa liczy się raz, mimo dwóch wizyt.
    assert summary.unesco_places == 2


def test_summary_on_empty_frame():
    summary = metrics.summarize(pd.DataFrame(columns=["rok", "nazwa", "lat", "lon"]))
    assert summary.visits == 0
    assert summary.span_km == 0.0
    assert summary.countries == 0
    assert summary.unesco_places == 0


def test_visits_per_country(sample):
    countries = metrics.visits_per_country(sample)
    assert countries["panstwo"].tolist() == ["Polska"]
    assert countries.loc[0, "wizyty"] == 4
    assert countries.loc[0, "miejsca"] == 3
    assert countries.loc[0, "unesco_miejsca"] == 2  # Warszawa i Kraków
    assert countries.loc[0, "unesco_wpisy"] == 2


def test_unesco_places_lists_each_place_once(sample):
    places = metrics.unesco_places(sample)
    assert places["nazwa"].tolist() == ["Kraków", "Warszawa"]
    assert places.loc[places["nazwa"] == "Warszawa", "wizyty"].item() == 2
    assert places.loc[places["nazwa"] == "Warszawa", "lata"].item() == "2020, 2021"


def test_unesco_places_empty_when_nothing_matches(sample):
    assert metrics.unesco_places(sample[~sample["unesco"]]).empty
    assert metrics.unesco_sites(sample[~sample["unesco"]]).empty


def test_shared_inscription_counts_once(shared_and_split):
    """Wieliczka i Bochnia to trzy miejsca... ale jeden wpis na Liście."""
    summary = metrics.summarize(shared_and_split)
    assert summary.unesco_places == 3
    assert summary.unesco_sites == 3  # 1 wspólny (sól) + 2 własne (Padwa)

    sites = metrics.unesco_sites(shared_and_split)
    salt = sites[sites["obiekt"].str.startswith("Królewskie")]
    assert len(salt) == 1
    assert salt["miejsca"].item() == "Bochnia, Wieliczka"
    assert salt["wizyty"].item() == 2


def test_place_with_two_inscriptions_gives_two_rows(shared_and_split):
    sites = metrics.unesco_sites(shared_and_split)
    padua = sites[sites["miejsca"] == "Padwa"]
    assert len(padua) == 2
    assert set(padua["obiekt"]) == {"Ogród botaniczny w Padwie", "Padwa urbs picta"}


def test_transnational_inscription_counted_in_both_countries(shared_and_split):
    countries = metrics.visits_per_country(shared_and_split).set_index("panstwo")
    assert countries.loc["Polska", "unesco_wpisy"] == 1  # jeden wpis, dwa miejsca
    assert countries.loc["Polska", "unesco_miejsca"] == 2
    assert countries.loc["Włochy", "unesco_wpisy"] == 2  # dwa wpisy, jedno miejsce
    assert countries.loc["Włochy", "unesco_miejsca"] == 1


def test_cumulative_places_never_decreases(sample):
    cumulative = metrics.cumulative_places(sample)
    assert cumulative["miejsca"].is_monotonic_increasing
    assert cumulative["miejsca"].iloc[-1] == 3


def test_route_distance_only_within_year(sample):
    distances = metrics.route_distance_by_year(sample)
    assert set(distances["rok"]) == {2020, 2021, 2022}
    assert distances.set_index("rok").loc[2020, "km"] == pytest.approx(252, abs=5)
    assert distances.set_index("rok").loc[2021, "km"] == 0.0


def test_top_places_lists_only_repeats(sample):
    top = metrics.top_places(sample)
    assert top["nazwa"].tolist() == ["Warszawa"]
    assert top["lata"].iloc[0] == "2020, 2021"


def test_extremes(sample):
    points = metrics.extremes(sample)
    assert points["Najdalej na północ"]["nazwa"] == "Gdańsk"
    assert points["Najdalej na południe"]["nazwa"] == "Kraków"
