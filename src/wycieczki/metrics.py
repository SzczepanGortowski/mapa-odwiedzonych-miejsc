"""Statystyki liczone na oczyszczonym zbiorze wizyt."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .geo import EARTH_RADIUS_KM, haversine_km

__all__ = [
    "EARTH_RADIUS_KM",
    "Summary",
    "cumulative_places",
    "extremes",
    "haversine_km",
    "max_span_km",
    "route_distance_by_year",
    "summarize",
    "top_places",
    "unesco_places",
    "unesco_sites",
    "visits_per_country",
    "visits_per_year",
]


@dataclass(frozen=True)
class Summary:
    """Zestaw liczb pokazywanych w nagłówku aplikacji."""

    visits: int
    unique_places: int
    years: int
    first_year: int
    last_year: int
    return_visits: int
    span_km: float
    countries: int
    unesco_places: int
    unesco_sites: int
    """Unikalne wpisy z Listy UNESCO — Wieliczka i Bochnia to jeden, Padwa dwa."""


def max_span_km(frame: pd.DataFrame) -> float:
    """Rozpiętość zbioru: odległość między skrajnymi narożnikami bounding boxa."""
    if frame.empty:
        return 0.0
    return float(
        haversine_km(
            frame["lat"].min(), frame["lon"].min(), frame["lat"].max(), frame["lon"].max()
        )
    )


def _inscriptions(frame: pd.DataFrame) -> set[str]:
    """Zbiór nazw wpisów z Listy UNESCO występujących w danych."""
    if frame.empty:
        return set()
    return {name for entry in frame["unesco_obiekty"] for name in entry}


def summarize(frame: pd.DataFrame) -> Summary:
    if frame.empty:
        return Summary(0, 0, 0, 0, 0, 0, 0.0, 0, 0, 0)
    places = int(frame["miejsce_id"].nunique())
    return Summary(
        visits=len(frame),
        unique_places=places,
        years=int(frame["rok"].nunique()),
        first_year=int(frame["rok"].min()),
        last_year=int(frame["rok"].max()),
        return_visits=len(frame) - places,
        span_km=max_span_km(frame),
        countries=int(frame["panstwo"].nunique()),
        unesco_places=int(frame.loc[frame["unesco"], "miejsce_id"].nunique()),
        unesco_sites=len(_inscriptions(frame)),
    )


def visits_per_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Liczba wizyt w każdym roku, z podziałem na nowe miejsca i powroty."""
    if frame.empty:
        return pd.DataFrame(columns=["rok", "typ", "liczba"])
    counts = (
        frame.assign(typ=np.where(frame["powrot"], "Powrót", "Nowe miejsce"))
        .groupby(["rok", "typ"], as_index=False)
        .size()
        .rename(columns={"size": "liczba"})
    )
    return counts.sort_values(["rok", "typ"])


def cumulative_places(frame: pd.DataFrame) -> pd.DataFrame:
    """Narastająca liczba unikalnych miejsc na koniec każdego roku."""
    if frame.empty:
        return pd.DataFrame(columns=["rok", "miejsca"])
    debuts = frame.drop_duplicates(subset=["miejsce_id"], keep="first")
    per_year = debuts.groupby("rok", as_index=False).size().rename(columns={"size": "nowe"})
    all_years = pd.DataFrame({"rok": range(int(frame["rok"].min()), int(frame["rok"].max()) + 1)})
    per_year = all_years.merge(per_year, on="rok", how="left").fillna({"nowe": 0})
    per_year["miejsca"] = per_year["nowe"].cumsum().astype(int)
    return per_year[["rok", "miejsca"]]


def top_places(frame: pd.DataFrame, limit: int = 12) -> pd.DataFrame:
    """Miejsca odwiedzone więcej niż raz, od najczęstszych."""
    if frame.empty:
        return pd.DataFrame(columns=["nazwa", "wizyty", "lata"])
    grouped = frame.groupby("miejsce_id").agg(
        nazwa=("nazwa", "first"),
        wizyty=("rok", "size"),
        lata=("rok", lambda years: ", ".join(str(year) for year in sorted(set(years)))),
    )
    grouped = grouped[grouped["wizyty"] > 1].sort_values("wizyty", ascending=False)
    return grouped.head(limit).reset_index(drop=True)


def visits_per_country(frame: pd.DataFrame) -> pd.DataFrame:
    """Wizyty, miejsca i dziedzictwo UNESCO w rozbiciu na państwa.

    `unesco_miejsca` liczy miejsca, a `unesco_wpisy` — wpisy na Liście. Wpis
    transgraniczny (Park Mużakowski) liczy się w obu państwach.
    """
    columns = ["panstwo", "wizyty", "miejsca", "lata", "unesco_miejsca", "unesco_wpisy"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    grouped = frame.groupby("panstwo").agg(
        wizyty=("rok", "size"),
        miejsca=("miejsce_id", "nunique"),
        lata=("rok", "nunique"),
    )
    heritage = frame[frame["unesco"]]
    grouped["unesco_miejsca"] = (
        heritage.groupby("panstwo")["miejsce_id"].nunique().reindex(grouped.index).fillna(0)
    )
    grouped["unesco_wpisy"] = (
        heritage.explode("unesco_obiekty")
        .groupby("panstwo")["unesco_obiekty"]
        .nunique()
        .reindex(grouped.index)
        .fillna(0)
    )
    grouped[["unesco_miejsca", "unesco_wpisy"]] = grouped[
        ["unesco_miejsca", "unesco_wpisy"]
    ].astype(int)
    grouped = grouped.reset_index()
    return grouped.sort_values("wizyty", ascending=False)[columns].reset_index(drop=True)


def unesco_places(frame: pd.DataFrame) -> pd.DataFrame:
    """Odwiedzone miejsca, w których jest obiekt z Listy UNESCO."""
    columns = ["nazwa", "panstwo", "unesco_obiekt", "wizyty", "lata"]
    if frame.empty or not frame["unesco"].any():
        return pd.DataFrame(columns=columns)
    grouped = (
        frame[frame["unesco"]]
        .groupby("miejsce_id")
        .agg(
            nazwa=("nazwa", "first"),
            panstwo=("panstwo", "first"),
            unesco_obiekt=("unesco_obiekt", "first"),
            wizyty=("rok", "size"),
            lata=("rok", lambda years: ", ".join(str(year) for year in sorted(set(years)))),
        )
    )
    return grouped.sort_values(["panstwo", "nazwa"])[columns].reset_index(drop=True)


def unesco_sites(frame: pd.DataFrame) -> pd.DataFrame:
    """Unikalne wpisy z Listy UNESCO — jeden wiersz na wpis, nie na miejsce.

    Wieliczka i Bochnia dzielą jeden wpis i dają jeden wiersz z dwoma
    miejscami; Padwa ma dwa wpisy i daje dwa wiersze.
    """
    columns = ["obiekt", "miejsca", "panstwa", "wizyty", "lata"]
    if frame.empty or not frame["unesco"].any():
        return pd.DataFrame(columns=columns)
    exploded = frame[frame["unesco"]].explode("unesco_obiekty")
    grouped = exploded.groupby("unesco_obiekty").agg(
        miejsca=("nazwa", lambda names: ", ".join(sorted(set(names)))),
        panstwa=("panstwo", lambda names: ", ".join(sorted(set(names)))),
        wizyty=("rok", "size"),
        lata=("rok", lambda years: ", ".join(str(year) for year in sorted(set(years)))),
    )
    grouped.index.name = "obiekt"
    return grouped.reset_index().sort_values(["panstwa", "obiekt"])[columns].reset_index(drop=True)


def route_distance_by_year(frame: pd.DataFrame) -> pd.DataFrame:
    """Szacunkowy dystans w linii prostej między kolejnymi punktami roku.

    Kolejność bierzemy z `lp`, czyli z kolejności wpisów w oryginalnym pliku.
    To przybliżenie — nie zna dróg ani przerw między osobnymi wyjazdami.
    """
    if frame.empty:
        return pd.DataFrame(columns=["rok", "km"])
    ordered = frame.sort_values(["rok", "lp"])
    rows = []
    for year, group in ordered.groupby("rok"):
        if len(group) < 2:
            rows.append({"rok": int(year), "km": 0.0})
            continue
        legs = haversine_km(
            group["lat"].to_numpy()[:-1],
            group["lon"].to_numpy()[:-1],
            group["lat"].to_numpy()[1:],
            group["lon"].to_numpy()[1:],
        )
        rows.append({"rok": int(year), "km": float(legs.sum())})
    return pd.DataFrame(rows)


def extremes(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Najdalej wysunięty punkt w każdą stronę świata."""
    if frame.empty:
        return {}
    return {
        "Najdalej na północ": frame.loc[frame["lat"].idxmax()],
        "Najdalej na południe": frame.loc[frame["lat"].idxmin()],
        "Najdalej na zachód": frame.loc[frame["lon"].idxmin()],
        "Najdalej na wschód": frame.loc[frame["lon"].idxmax()],
    }
