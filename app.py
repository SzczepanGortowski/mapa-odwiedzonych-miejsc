"""Mapa wycieczek — aplikacja Streamlit.

Uruchomienie:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from wycieczki import charts, metrics  # noqa: E402
from wycieczki.config import APP_ICON, APP_TITLE, DATA_FILE, TILE_LAYERS  # noqa: E402
from wycieczki.data import Dataset, load_dataset  # noqa: E402
from wycieczki.mapview import (  # noqa: E402
    COLOR_BY_GROUP,
    COLOR_BY_YEAR,
    UNESCO_RING,
    MapOptions,
    build_map,
    legend_items,
)

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .block-container {padding-top: 2.4rem; padding-bottom: 2rem; max-width: 1400px;}
    div[data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.08);
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 12px;
        padding: 14px 16px;
    }
    div[data-testid="stMetricLabel"] p {font-size: 0.78rem; letter-spacing: .04em;
        text-transform: uppercase; opacity: .7;}
    iframe {border-radius: 12px;}
    .legend {display: flex; flex-wrap: wrap; gap: 6px 14px; padding: 4px 0 10px;
        font-size: .78rem; opacity: .85;}
    .legend span.dot {display: inline-block; width: 10px; height: 10px;
        border-radius: 50%; margin-right: 5px;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner="Wczytuję dane…")
def get_dataset(path: str, mtime: float) -> Dataset:
    """Cache'owane wczytanie danych; `mtime` unieważnia cache po edycji pliku."""
    del mtime  # tylko klucz cache
    return load_dataset(path)


def load() -> Dataset:
    try:
        return get_dataset(str(DATA_FILE), DATA_FILE.stat().st_mtime)
    except FileNotFoundError as error:
        st.error(str(error))
        st.stop()


def sidebar_filters(frame: pd.DataFrame) -> tuple[pd.DataFrame, MapOptions]:
    """Panel boczny: filtry danych i ustawienia mapy."""
    st.sidebar.title(f"{APP_ICON} {APP_TITLE}")
    first_year, last_year = int(frame["rok"].min()), int(frame["rok"].max())
    st.sidebar.caption(f"Miejsca odwiedzone od {first_year} do {last_year} roku.")

    st.sidebar.subheader("Filtry")
    years = st.sidebar.slider(
        "Zakres lat",
        min_value=first_year,
        max_value=last_year,
        value=(first_year, last_year),
        step=1,
    )

    countries = sorted(frame["panstwo"].unique())
    selected_countries = st.sidebar.multiselect(
        "Państwo",
        options=countries,
        default=[],
        placeholder="wszystkie",
    )

    query = st.sidebar.text_input("Szukaj miejsca", placeholder="np. Gdańsk")
    only_new = st.sidebar.toggle(
        "Tylko pierwsze wizyty",
        value=False,
        help="Ukrywa ponowne wizyty w miejscu odwiedzonym już wcześniej.",
    )
    only_unesco = st.sidebar.toggle(
        "Tylko miejsca z UNESCO",
        value=False,
        help="Zostawia miejsca z obiektem z Listy światowego dziedzictwa.",
    )

    st.sidebar.subheader("Mapa")
    tile_label = st.sidebar.selectbox("Podkład", list(TILE_LAYERS), index=0)
    color_by = st.sidebar.radio("Koloruj według", [COLOR_BY_YEAR, COLOR_BY_GROUP], index=0)
    radius = st.sidebar.slider("Wielkość punktów", 3, 12, 6)
    cluster = st.sidebar.toggle("Grupuj bliskie punkty", value=False)
    show_routes = st.sidebar.toggle(
        "Pokaż trasy",
        value=False,
        help="Łączy punkty w kolejności wpisów w danym roku.",
    )
    show_heatmap = st.sidebar.toggle("Mapa cieplna", value=False)

    filtered = frame[frame["rok"].between(*years)]
    if selected_countries:
        filtered = filtered[filtered["panstwo"].isin(selected_countries)]
    if query:
        filtered = filtered[filtered["nazwa"].str.contains(query, case=False, na=False)]
    if only_new:
        filtered = filtered[~filtered["powrot"]]
    if only_unesco:
        filtered = filtered[filtered["unesco"]]

    options = MapOptions(
        tiles=TILE_LAYERS[tile_label],
        color_by=color_by,
        cluster=cluster,
        show_routes=show_routes,
        show_heatmap=show_heatmap,
        radius=radius,
    )
    return filtered, options


def render_kpis(frame: pd.DataFrame) -> None:
    summary = metrics.summarize(frame)
    columns = st.columns(6)
    columns[0].metric("Wizyty", f"{summary.visits}")
    columns[1].metric("Miejsca", f"{summary.unique_places}", help="Unikalne miejsca")
    columns[2].metric("Państwa", f"{summary.countries}")
    columns[3].metric(
        "Wpisy UNESCO",
        f"{summary.unesco_sites}",
        help=(
            f"Unikalne wpisy na Liście światowego dziedzictwa, odwiedzone "
            f"w {summary.unesco_places} miejscach. Wieliczka i Bochnia to jeden "
            "wspólny wpis, a Padwa ma dwa własne."
        ),
    )
    span = f"{summary.first_year}–{summary.last_year}"
    columns[4].metric("Lata", f"{summary.years}", help=span)
    columns[5].metric("Powroty", f"{summary.return_visits}")


def render_legend(frame: pd.DataFrame, color_by: str) -> None:
    items = legend_items(frame, color_by)
    chips = "" if len(items) > 24 else "".join(
        f"<span><span class='dot' style='background:{color}'></span>{label}</span>"
        for label, color in items
    )
    if frame["unesco"].any():
        chips += (
            f"<span><span class='dot' style='background:transparent;"
            f"border:2.5px solid {UNESCO_RING}'></span>obiekt UNESCO</span>"
        )
    if chips:
        st.markdown(f"<div class='legend'>{chips}</div>", unsafe_allow_html=True)


def render_map_tab(frame: pd.DataFrame, options: MapOptions) -> None:
    if frame.empty:
        st.info("Żadne miejsce nie pasuje do wybranych filtrów.")
        return
    render_legend(frame, options.color_by)
    st_folium(
        build_map(frame, options),
        use_container_width=True,
        height=620,
        returned_objects=[],  # mapa nie musi odsyłać stanu — brak przeładowań
    )


def render_unesco_section(frame: pd.DataFrame) -> None:
    """Dziedzictwo UNESCO w dwóch ujęciach: wpisy na Liście i odwiedzone miejsca."""
    sites = metrics.unesco_sites(frame)
    places = metrics.unesco_places(frame)

    st.subheader("UNESCO")
    if sites.empty:
        st.caption("W tym wyborze nie ma miejsca z obiektem UNESCO.")
        return

    st.caption(
        f"**{len(sites)}** unikalnych wpisów na Liście światowego dziedzictwa, "
        f"odwiedzonych w **{len(places)}** miejscach. Liczby się różnią, bo jeden "
        "wpis potrafi obejmować kilka miejsc (Wieliczka i Bochnia, Jawor "
        "i Świdnica), a jedno miejsce mieć kilka wpisów (Padwa, Tivoli)."
    )

    by_site, by_place = st.tabs([f"Wpisy ({len(sites)})", f"Miejsca ({len(places)})"])
    with by_site:
        st.dataframe(
            sites,
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={
                "obiekt": st.column_config.TextColumn("Wpis na Liście", width="large"),
                "miejsca": st.column_config.TextColumn("Odwiedzone miejsca", width="medium"),
                "panstwa": st.column_config.TextColumn("Państwo"),
                "wizyty": st.column_config.NumberColumn("Wizyt", format="%d"),
                "lata": st.column_config.TextColumn("Lata"),
            },
        )
    with by_place:
        st.dataframe(
            places,
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={
                "nazwa": st.column_config.TextColumn("Miejsce"),
                "panstwo": st.column_config.TextColumn("Państwo"),
                "unesco_obiekt": st.column_config.TextColumn("Wpis(y)", width="large"),
                "wizyty": st.column_config.NumberColumn("Wizyt", format="%d"),
                "lata": st.column_config.TextColumn("Lata"),
            },
        )


def render_stats_tab(frame: pd.DataFrame) -> None:
    if frame.empty:
        st.info("Brak danych do podsumowania.")
        return

    left, right = st.columns(2)
    with left:
        st.subheader("Wizyty w kolejnych latach")
        st.altair_chart(charts.visits_per_year(frame), use_container_width=True)
    with right:
        st.subheader("Nowe miejsca narastająco")
        st.altair_chart(charts.cumulative_places(frame), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Dystans w linii prostej")
        st.caption("Suma odcinków między punktami roku — szacunek, nie długość trasy.")
        st.altair_chart(charts.distance_per_year(frame), use_container_width=True)
    with right:
        st.subheader("Najczęściej odwiedzane")
        top = metrics.top_places(frame)
        if top.empty:
            st.caption("W tym wyborze nie ma miejsca odwiedzonego dwa razy.")
        else:
            st.altair_chart(charts.top_places(frame), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Państwa")
        st.altair_chart(charts.visits_by_country(frame), use_container_width=True)
    with right:
        st.subheader("Rozrzut geograficzny")
        st.altair_chart(charts.latitude_drift(frame), use_container_width=True)

    render_unesco_section(frame)

    st.subheader("Punkty skrajne")
    extremes = metrics.extremes(frame)
    for column, (label, row) in zip(st.columns(len(extremes)), extremes.items()):
        coordinates = f"{row['lat']:.3f}, {row['lon']:.3f}"
        column.metric(label, row["nazwa"], help=f"{row['rok']} · {coordinates}")


def render_data_tab(frame: pd.DataFrame, dataset: Dataset) -> None:
    st.subheader("Dane źródłowe")
    view = frame[
        [
            "rok",
            "nazwa",
            "panstwo",
            "unesco",
            "unesco_obiekt",
            "lat",
            "lon",
            "kolor",
            "powrot",
            "wizyt_lacznie",
        ]
    ]
    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        height=460,
        column_config={
            "rok": st.column_config.NumberColumn("Rok", format="%d"),
            "nazwa": st.column_config.TextColumn("Miejsce", width="medium"),
            "panstwo": st.column_config.TextColumn("Państwo"),
            "unesco": st.column_config.CheckboxColumn("UNESCO"),
            "unesco_obiekt": st.column_config.TextColumn("Obiekt UNESCO", width="large"),
            "lat": st.column_config.NumberColumn("Szerokość", format="%.5f"),
            "lon": st.column_config.NumberColumn("Długość", format="%.5f"),
            "kolor": st.column_config.TextColumn("Grupa"),
            "powrot": st.column_config.CheckboxColumn("Powrót"),
            "wizyt_lacznie": st.column_config.NumberColumn("Wizyt łącznie", format="%d"),
        },
    )
    st.download_button(
        "Pobierz widoczne dane (CSV)",
        data=view.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="wycieczki.csv",
        mime="text/csv",
    )
    st.caption(
        f"Źródło: `{DATA_FILE.name}` · {len(dataset)} wizyt po oczyszczeniu. "
        "Nowe miejsca dopisz do pliku CSV — aplikacja odświeży się sama. "
        "Państwo i UNESCO uzupełnia `python scripts/enrich_places.py`."
    )
    for issue in dataset.issues:
        st.warning(issue)


def main() -> None:
    dataset = load()
    filtered, options = sidebar_filters(dataset.frame)

    st.title(f"{APP_ICON} {APP_TITLE}")
    render_kpis(filtered)
    st.write("")

    map_tab, stats_tab, data_tab = st.tabs(["Mapa", "Statystyki", "Dane"])
    with map_tab:
        render_map_tab(filtered, options)
    with stats_tab:
        render_stats_tab(filtered)
    with data_tab:
        render_data_tab(filtered, dataset)


if __name__ == "__main__":
    main()
