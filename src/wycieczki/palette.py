"""Mapowanie lat i grup na kolory używane na mapie i wykresach."""

from __future__ import annotations

from .config import FALLBACK_COLOR, LEGACY_COLORS, YEAR_GRADIENT


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(round(channel)) for channel in rgb))


def sample_gradient(position: float, stops: list[str] | None = None) -> str:
    """Kolor z gradientu dla pozycji z zakresu 0-1."""
    stops = stops or YEAR_GRADIENT
    position = min(max(position, 0.0), 1.0)
    scaled = position * (len(stops) - 1)
    lower = int(scaled)
    upper = min(lower + 1, len(stops) - 1)
    weight = scaled - lower
    start, end = _hex_to_rgb(stops[lower]), _hex_to_rgb(stops[upper])
    return _rgb_to_hex(tuple(s + (e - s) * weight for s, e in zip(start, end)))


def year_colors(years: list[int]) -> dict[int, str]:
    """Przypisuje każdemu rokowi kolor z gradientu, chronologicznie."""
    unique_years = sorted(set(years))
    if not unique_years:
        return {}
    if len(unique_years) == 1:
        return {unique_years[0]: YEAR_GRADIENT[len(YEAR_GRADIENT) // 2]}
    last = len(unique_years) - 1
    return {year: sample_gradient(index / last) for index, year in enumerate(unique_years)}


def group_colors(groups: list[str]) -> dict[str, str]:
    """Kolory grup przeniesione 1:1 z nazw markerów Leaflet z wersji w R."""
    return {group: LEGACY_COLORS.get(group, FALLBACK_COLOR) for group in sorted(set(groups))}
