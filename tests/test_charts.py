"""Testy dymne wykresów i mapy.

Wykresy Altaira budują się leniwie, więc literówka w specyfikacji wychodzi
dopiero przy renderowaniu w przeglądarce. Te testy wymuszają budowę na kilku
wariantach danych — pełnym, przefiltrowanym i pustym.
"""

from __future__ import annotations

import pytest

from wycieczki import charts
from wycieczki.mapview import COLOR_BY_GROUP, COLOR_BY_YEAR, MapOptions, build_map

CHART_BUILDERS = [
    charts.visits_per_year,
    charts.cumulative_places,
    charts.distance_per_year,
    charts.top_places,
    charts.visits_by_country,
    charts.latitude_drift,
]


@pytest.fixture(
    params=["wszystko", "tylko UNESCO", "jedno państwo", "jeden rok"],
)
def subset(request, dataset):
    """Wycinki danych, które da się wyklikać filtrami w aplikacji."""
    if request.param == "tylko UNESCO":
        return dataset[dataset["unesco"]]
    if request.param == "jedno państwo":
        # Państwo obecne i w prawdziwych danych, i w pliku przykładowym.
        return dataset[dataset["panstwo"] == "Chorwacja"]
    if request.param == "jeden rok":
        return dataset[dataset["rok"] == dataset["rok"].min()]
    return dataset


@pytest.mark.parametrize("builder", CHART_BUILDERS, ids=lambda f: f.__name__)
def test_chart_builds(builder, subset):
    assert not subset.empty, "wycinek testowy nie powinien być pusty"
    chart = builder(subset)
    # to_dict() rozwija pełną specyfikację Vega-Lite i wykrywa złe odwołania.
    assert chart.to_dict()["$schema"].startswith("https://vega.github.io/schema/vega-lite")


@pytest.mark.parametrize(
    "options",
    [
        MapOptions(),
        MapOptions(color_by=COLOR_BY_GROUP, cluster=True),
        MapOptions(color_by=COLOR_BY_YEAR, show_routes=True, show_heatmap=True),
    ],
    ids=["domyślna", "grupy i klastry", "trasy i mapa cieplna"],
)
def test_map_builds(options, dataset):
    assert build_map(dataset, options)._repr_html_()


def test_map_handles_empty_frame(dataset):
    assert build_map(dataset.iloc[0:0], MapOptions())._repr_html_()
