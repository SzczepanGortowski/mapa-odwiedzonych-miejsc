"""Wykresy Altaira dla zakładki ze statystykami."""

from __future__ import annotations

import altair as alt
import pandas as pd

from . import metrics
from .palette import year_colors

NEW_PLACE_COLOR = "#2e8bc0"
RETURN_COLOR = "#f0b429"
LINE_COLOR = "#e8590c"
UNESCO_COLOR = "#c9930b"


def _base(chart: alt.Chart, height: int = 260) -> alt.Chart:
    return chart.properties(height=height).configure_view(strokeWidth=0).configure_axis(
        grid=True, gridOpacity=0.15, domain=False, tickSize=0, labelPadding=6
    )


def visits_per_year(frame: pd.DataFrame) -> alt.Chart:
    data = metrics.visits_per_year(frame)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("rok:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("liczba:Q", title="Liczba wizyt", stack="zero"),
            color=alt.Color(
                "typ:N",
                title=None,
                scale=alt.Scale(
                    domain=["Nowe miejsce", "Powrót"],
                    range=[NEW_PLACE_COLOR, RETURN_COLOR],
                ),
                legend=alt.Legend(orient="top", offset=4),
            ),
            tooltip=[
                alt.Tooltip("rok:O", title="Rok"),
                alt.Tooltip("typ:N", title="Typ"),
                alt.Tooltip("liczba:Q", title="Wizyt"),
            ],
        )
    )
    return _base(chart)


def cumulative_places(frame: pd.DataFrame) -> alt.Chart:
    data = metrics.cumulative_places(frame)
    area = (
        alt.Chart(data)
        .mark_area(
            line={"color": LINE_COLOR, "strokeWidth": 2},
            color=alt.Gradient(
                gradient="linear",
                stops=[
                    alt.GradientStop(color="#e8590c", offset=1),
                    alt.GradientStop(color="#e8590c00", offset=0),
                ],
                x1=1, x2=1, y1=1, y2=0,
            ),
            interpolate="monotone",
        )
        .encode(
            x=alt.X("rok:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("miejsca:Q", title="Unikalne miejsca (narastająco)"),
            tooltip=[
                alt.Tooltip("rok:O", title="Rok"),
                alt.Tooltip("miejsca:Q", title="Miejsc łącznie"),
            ],
        )
    )
    return _base(area)


def distance_per_year(frame: pd.DataFrame) -> alt.Chart:
    data = metrics.route_distance_by_year(frame)
    colors = year_colors(data["rok"].tolist())
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("rok:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("km:Q", title="Dystans w linii prostej [km]"),
            color=alt.Color(
                "rok:O",
                scale=alt.Scale(domain=list(colors), range=list(colors.values())),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("rok:O", title="Rok"),
                alt.Tooltip("km:Q", title="Dystans [km]", format=".0f"),
            ],
        )
    )
    return _base(chart)


def top_places(frame: pd.DataFrame, limit: int = 12) -> alt.Chart:
    data = metrics.top_places(frame, limit=limit)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3, color=NEW_PLACE_COLOR)
        .encode(
            y=alt.Y("nazwa:N", title=None, sort="-x"),
            x=alt.X("wizyty:Q", title="Liczba wizyt", axis=alt.Axis(tickMinStep=1)),
            tooltip=[
                alt.Tooltip("nazwa:N", title="Miejsce"),
                alt.Tooltip("wizyty:Q", title="Wizyt"),
                alt.Tooltip("lata:N", title="Lata"),
            ],
        )
    )
    return _base(chart, height=max(160, 26 * max(len(data), 1)))


def visits_by_country(frame: pd.DataFrame) -> alt.Chart:
    """Miejsca w rozbiciu na państwa, z wyróżnieniem obiektów UNESCO."""
    data = metrics.visits_per_country(frame)
    data = data.assign(pozostale=data["miejsca"] - data["unesco_miejsca"]).melt(
        id_vars=["panstwo", "wizyty", "miejsca", "unesco_wpisy"],
        value_vars=["unesco_miejsca", "pozostale"],
        var_name="rodzaj",
        value_name="liczba",
    )
    labels = {"unesco_miejsca": "z obiektem UNESCO", "pozostale": "pozostałe"}
    data["rodzaj"] = data["rodzaj"].map(labels)
    chart = (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopRight=3, cornerRadiusBottomRight=3)
        .encode(
            y=alt.Y("panstwo:N", title=None, sort=alt.EncodingSortField("miejsca", op="sum",
                                                                        order="descending")),
            x=alt.X("liczba:Q", title="Odwiedzone miejsca", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "rodzaj:N",
                title=None,
                scale=alt.Scale(
                    domain=[labels["unesco_miejsca"], labels["pozostale"]],
                    range=[UNESCO_COLOR, NEW_PLACE_COLOR],
                ),
                legend=alt.Legend(orient="top", offset=4),
            ),
            tooltip=[
                alt.Tooltip("panstwo:N", title="Państwo"),
                alt.Tooltip("rodzaj:N", title="Rodzaj"),
                alt.Tooltip("liczba:Q", title="Miejsc"),
                alt.Tooltip("wizyty:Q", title="Wizyt łącznie"),
                alt.Tooltip("unesco_wpisy:Q", title="Wpisów UNESCO"),
            ],
        )
    )
    return _base(chart, height=max(180, 28 * max(data["panstwo"].nunique(), 1)))


def latitude_drift(frame: pd.DataFrame) -> alt.Chart:
    """Rozrzut geograficzny wizyt w czasie — jak daleko od domu w danym roku."""
    chart = (
        alt.Chart(frame)
        .mark_circle(size=55, opacity=0.55)
        .encode(
            x=alt.X("lon:Q", title="Długość geograficzna", scale=alt.Scale(zero=False)),
            y=alt.Y("lat:Q", title="Szerokość geograficzna", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "rok:O",
                title="Rok",
                scale=alt.Scale(scheme="viridis"),
                legend=alt.Legend(orient="right", symbolLimit=20),
            ),
            tooltip=[
                alt.Tooltip("nazwa:N", title="Miejsce"),
                alt.Tooltip("rok:O", title="Rok"),
            ],
        )
    )
    return _base(chart, height=340)
