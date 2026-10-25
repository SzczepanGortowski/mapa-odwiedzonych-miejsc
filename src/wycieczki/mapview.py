"""Budowa mapy Folium (Leaflet) z markerami wizyt."""

from __future__ import annotations

from dataclasses import dataclass

import folium
import pandas as pd
from branca.element import MacroElement
from folium.plugins import HeatMap, MarkerCluster
from folium.template import Template

from .config import TILE_LAYERS
from .palette import group_colors, year_colors

COLOR_BY_YEAR = "Rok"
COLOR_BY_GROUP = "Grupa z pliku"

# Złota obwódka wyróżniająca miejsca z obiektem UNESCO.
UNESCO_RING = "#c9930b"

# Podpowiedź do mapy, która nie przechwytuje przewijania (patrz PageFriendlyGestures).
GESTURE_HINT = (
    "Kółko myszy przewija stronę — kliknij mapę, żeby przybliżać kółkiem. "
    "Na ekranie dotykowym mapę przesuwa się i przybliża dwoma palcami."
)


class PageFriendlyGestures(MacroElement):
    """Mapa nie przechwytuje przewijania strony.

    Leaflet domyślnie zamienia kółko myszy w zoom, a przeciągnięcie palcem
    w przesuwanie mapy. Mapa zajmuje prawie całą wysokość okna — a w ramce
    osadzonej na innej stronie nawet całą — więc gdy znajdzie się pod kursorem
    albo palcem, nie da się przewinąć ani aplikacji, ani strony.

    Dlatego kółko przybliża dopiero po kliknięciu mapy i tylko do chwili, gdy
    kursor ją opuści, a na ekranach dotykowych jeden palec przewija stronę,
    a mapę przesuwa i przybliża gest dwoma palcami.
    """

    _template = Template(
        """
        {% macro script(this, kwargs) %}
        (function (map) {
            var container = map.getContainer();
            map.scrollWheelZoom.disable();
            map.on("click focus", function () { map.scrollWheelZoom.enable(); });
            map.on("blur", function () { map.scrollWheelZoom.disable(); });
            container.addEventListener("mouseleave", function () {
                map.scrollWheelZoom.disable();
            });
            var coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
            if (coarse || L.Browser.mobile) {
                map.dragging.disable();
            }
        })({{ this._parent.get_name() }});
        {% endmacro %}
        """
    )


@dataclass(frozen=True)
class MapOptions:
    """Ustawienia mapy sterowane z panelu bocznego."""

    tiles: str = next(iter(TILE_LAYERS.values()))
    color_by: str = COLOR_BY_YEAR
    cluster: bool = False
    show_routes: bool = False
    show_heatmap: bool = False
    radius: int = 6


def color_lookup(frame: pd.DataFrame, color_by: str) -> tuple[dict, str]:
    """Zwraca mapę wartość -> kolor oraz nazwę kolumny, po której kolorujemy."""
    if color_by == COLOR_BY_GROUP:
        return group_colors(frame["kolor"].tolist()), "kolor"
    return year_colors(frame["rok"].tolist()), "rok"


def _popup_html(row: dict) -> str:
    visits = (
        f"<div style='color:#868e96'>wizyt w tym miejscu: {row['wizyt_lacznie']}</div>"
        if row["wizyt_lacznie"] > 1
        else ""
    )
    sites = row["unesco_obiekty"]
    unesco = (
        f"<div style='margin-top:6px;padding:4px 7px;border-radius:6px;"
        f"background:{UNESCO_RING}22;border-left:3px solid {UNESCO_RING};font-size:12px'>"
        f"<b>UNESCO</b><br>{'<br>'.join(sites)}</div>"
        if sites
        else ""
    )
    return (
        "<div style=\"font-family:system-ui,sans-serif;min-width:180px\">"
        f"<div style='font-size:15px;font-weight:600'>{row['nazwa']}</div>"
        f"<div style='color:#495057'>{row['rok']} · {row['panstwo']}</div>"
        f"{visits}{unesco}"
        "<div style='margin-top:6px;font-size:11px;color:#adb5bd'>"
        f"{row['lat']:.4f}, {row['lon']:.4f}</div></div>"
    )


def _fit_bounds(fmap: folium.Map, frame: pd.DataFrame) -> None:
    bounds = [
        [frame["lat"].min(), frame["lon"].min()],
        [frame["lat"].max(), frame["lon"].max()],
    ]
    if bounds[0] == bounds[1]:
        fmap.location = bounds[0]
        fmap.zoom_start = 11
        return
    fmap.fit_bounds(bounds, padding=(24, 24))


def _add_routes(fmap: folium.Map, frame: pd.DataFrame, colors: dict, column: str) -> None:
    """Łączy punkty w kolejności wpisów — pokazuje przebieg wyjazdów w roku."""
    layer = folium.FeatureGroup(name="Trasy", show=True)
    for year, group in frame.sort_values(["rok", "lp"]).groupby("rok"):
        if len(group) < 2:
            continue
        key = year if column == "rok" else group[column].iloc[0]
        folium.PolyLine(
            locations=group[["lat", "lon"]].to_numpy().tolist(),
            color=colors.get(key, "#868e96"),
            weight=2,
            opacity=0.45,
            tooltip=f"Trasa {year}",
        ).add_to(layer)
    layer.add_to(fmap)


def build_map(frame: pd.DataFrame, options: MapOptions) -> folium.Map:
    """Tworzy mapę z markerami dla przekazanych (już przefiltrowanych) wizyt."""
    fmap = folium.Map(
        location=[52.0, 19.3],
        zoom_start=6,
        tiles=options.tiles,
        control_scale=True,
        zoom_control=True,
        scroll_wheel_zoom=False,
    )
    PageFriendlyGestures().add_to(fmap)
    if frame.empty:
        return fmap

    colors, column = color_lookup(frame, options.color_by)
    _fit_bounds(fmap, frame)

    if options.show_heatmap:
        HeatMap(
            frame[["lat", "lon"]].to_numpy().tolist(),
            radius=18,
            blur=22,
            min_opacity=0.25,
        ).add_to(folium.FeatureGroup(name="Mapa cieplna", show=True).add_to(fmap))

    if options.show_routes:
        _add_routes(fmap, frame, colors, column)

    target: folium.Map | MarkerCluster | folium.FeatureGroup = fmap
    if options.cluster:
        target = MarkerCluster(name="Miejsca", disableClusteringAtZoom=10).add_to(fmap)

    for record in frame.to_dict("records"):
        unesco = bool(record["unesco"])
        bonus = (2 if record["wizyt_lacznie"] > 1 else 0) + (2 if unesco else 0)
        folium.CircleMarker(
            location=[record["lat"], record["lon"]],
            radius=options.radius + bonus,
            color=UNESCO_RING if unesco else "#ffffff",
            weight=2.6 if unesco else 1.2,
            fill=True,
            fill_color=colors.get(record[column], "#495057"),
            fill_opacity=0.9,
            popup=folium.Popup(_popup_html(record), max_width=280),
            tooltip=(
                f"{record['etykieta']} · UNESCO" if unesco else record["etykieta"]
            ),
        ).add_to(target)

    return fmap


def legend_items(frame: pd.DataFrame, color_by: str) -> list[tuple[str, str]]:
    """Pary (etykieta, kolor) do legendy renderowanej poza mapą."""
    colors, _ = color_lookup(frame, color_by)
    return [(str(key), value) for key, value in colors.items()]
