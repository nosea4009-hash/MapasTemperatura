"""Generacion del mapa de temperaturas (estilo visual solicitado):

- El mapa queda encerrado en un cuadro blanco fino (marco delgado).
- Colormap (gradiente verde) con su barra de colores al costado.
- Titulo arriba, en fuente Tahoma: "Temperaturas Minimas/Maximas
  registradas el YYYYMMDD" a la izquierda y "Region: <provincia>" a la
  derecha.
- Dos cuadraditos semi-transparentes con texto Tahoma en negrita:
  "MAS BAJA: X.X°C (estacion)" y "MAS ALTA: X.X°C (estacion)".
- Puntos rojos marcando cada Estacion Meteorologica (EMA) usada.
- Limites de departamentos/partidos dibujados como referencia interna.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import matplotlib
import matplotlib.font_manager as fm
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import BoundaryNorm  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402

from .data import Metric
from .geo import ProvinceGeometry, Ring
from .interpolate import InterpolatedField, extreme_stations

# La fuente "Tahoma" no suele venir instalada en entornos Linux/servidor.
# Se intenta usar Tahoma si esta disponible en el sistema; si no, se cae a
# una alternativa sans-serif muy similar visualmente (Verdana / DejaVu Sans)
# para no romper la generacion del grafico.
_PREFERRED_FONTS = ["Tahoma", "Verdana", "DejaVu Sans", "Noto Sans", "sans-serif"]


def _resolve_font_family() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    for font_name in _PREFERRED_FONTS:
        if font_name in available or font_name == "sans-serif":
            return font_name
    return "sans-serif"


FONT_FAMILY = _resolve_font_family()

# Colormap tipo "verde" (frio = verde oscuro, calido = verde-amarillo claro),
# igual al estilo de la imagen de referencia.
TEMPERATURE_CMAP = "YlGn_r"
LEVEL_STEP = 2.0  # grados Celsius por banda de color (bandas discretas)

FRAME_COLOR = "black"
FRAME_LINEWIDTH = 1.4
STATION_DOT_COLOR = "#d62728"
STATION_DOT_EDGE = "white"
DEPARTMENT_LINE_COLOR = "#333333"


def _title_font(size: float, bold: bool = False) -> FontProperties:
    return FontProperties(
        family=FONT_FAMILY, size=size, weight="bold" if bold else "normal"
    )


def _compute_levels(field: InterpolatedField) -> np.ndarray:
    valid = field.values[~np.isnan(field.values)]
    vmin = np.floor(valid.min() / LEVEL_STEP) * LEVEL_STEP
    vmax = np.ceil(valid.max() / LEVEL_STEP) * LEVEL_STEP
    if vmax <= vmin:
        vmax = vmin + LEVEL_STEP
    return np.arange(vmin, vmax + LEVEL_STEP, LEVEL_STEP)


def _draw_department_boundaries(ax, rings: List[Ring]) -> None:
    for ring in rings:
        ax.plot(
            ring.lons,
            ring.lats,
            color=DEPARTMENT_LINE_COLOR,
            linewidth=0.6,
            zorder=3,
        )


def _extreme_box_offset(
    x: float, y: float, bounds: Tuple[float, float, float, float]
) -> Tuple[float, float]:
    """Calcula el desplazamiento (en puntos) de un cuadradito de extremo,
    apuntando desde la estacion hacia el centro del mapa (para minimizar la
    chance de quedar cortado por el borde del cuadro blanco)."""
    lon_min, lon_max, lat_min, lat_max = bounds
    lon_mid = (lon_min + lon_max) / 2.0
    lat_mid = (lat_min + lat_max) / 2.0
    offset_x = 55 if x <= lon_mid else -55
    offset_y = 30 if y <= lat_mid else -30
    return offset_x, offset_y


def _draw_extreme_box(
    ax,
    x: float,
    y: float,
    label: str,
    value: float,
    station_name: str,
    offset: Tuple[float, float],
):
    """Dibuja el cuadradito semi-transparente de un valor extremo, con una
    pequena flecha que apunta desde el punto de la estacion hacia el
    cuadro de texto (desplazado segun `offset`, en puntos).

    Returns:
        El objeto matplotlib.text.Annotation dibujado (para poder
        detectar colisiones con otras anotaciones y, si es necesario,
        removerlo y redibujarlo en otra posicion).
    """
    text = f"{label}: {value:.1f}°C\n({station_name.title()})"
    return ax.annotate(
        text,
        xy=(x, y),
        xytext=offset,
        textcoords="offset points",
        fontproperties=_title_font(7.5, bold=True),
        color="black",
        ha="center",
        va="center",
        zorder=6,
        arrowprops=dict(
            arrowstyle="-",
            color="black",
            linewidth=0.6,
            shrinkA=0,
            shrinkB=3,
        ),
        bbox=dict(
            boxstyle="round,pad=0.35",
            facecolor="white",
            alpha=0.6,
            edgecolor="black",
            linewidth=0.8,
        ),
    )


def render_temperature_map(
    field: InterpolatedField,
    geometry: ProvinceGeometry,
    department_rings: List[Ring],
    metric: Metric,
    date_str: str,
    province_label: str,
    output_path: Path,
    source_note: Optional[str] = (
        "Fuente: Servicio Meteorológico Nacional (SMN) — Estaciones "
        "Meteorológicas (EMAs), datos oficiales."
    ),
    dpi: int = 160,
) -> Path:
    """Genera y guarda el mapa de temperaturas.

    Args:
        field: campo interpolado (ver interpolate_province_field).
        geometry: geometria de la provincia (para el contorno externo).
        department_rings: limites internos de departamentos/partidos.
        metric: "min" o "max".
        date_str: fecha en formato YYYYMMDD, para el titulo.
        province_label: nombre de la provincia a mostrar junto al titulo.
        output_path: ruta del archivo de imagen a generar (.png).
        source_note: leyenda de atribucion de la fuente de datos (se puede
            pasar None para omitirla).
        dpi: resolucion de salida.

    Returns:
        La ruta del archivo generado.
    """
    metric_label = "Mínimas" if metric == "min" else "Máximas"
    levels = _compute_levels(field)
    lowest, highest = extreme_stations(field)

    fig = plt.figure(figsize=(7.2, 8.0), facecolor="white")

    # --- Cabecera (titulo + region), en fuente Tahoma ---------------------
    header_ax = fig.add_axes([0.06, 0.90, 0.88, 0.07])
    header_ax.axis("off")
    header_ax.set_xlim(0, 1)
    header_ax.set_ylim(0, 1)

    title_text = f"Temperaturas {metric_label} registradas el ({date_str})"
    region_text = f"Región: {province_label}"

    title_size = 13.0
    region_size = 12.0
    title_artist = header_ax.text(
        0.0,
        0.5,
        title_text,
        fontproperties=_title_font(title_size),
        ha="left",
        va="center",
        transform=header_ax.transAxes,
    )
    region_artist = header_ax.text(
        1.0,
        0.5,
        region_text,
        fontproperties=_title_font(region_size, bold=True),
        ha="right",
        va="center",
        transform=header_ax.transAxes,
    )

    # Si el titulo es largo (ej. provincias con nombre extenso), ambos
    # textos pueden superponerse. Se reduce el tamano de fuente hasta que
    # dejen de colisionar (o se llega a un minimo razonable).
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    min_gap_px = 10.0
    for _ in range(12):
        title_bbox = title_artist.get_window_extent(renderer=renderer)
        region_bbox = region_artist.get_window_extent(renderer=renderer)
        gap = region_bbox.x0 - title_bbox.x1
        if gap >= min_gap_px or title_size <= 8.5:
            break
        title_size -= 0.5
        region_size = max(region_size - 0.3, 9.0)
        title_artist.set_fontproperties(_title_font(title_size))
        region_artist.set_fontproperties(_title_font(region_size, bold=True))
        fig.canvas.draw()

    # --- Mapa principal, encerrado en un marco (cuadro) fino --------------
    map_ax = fig.add_axes([0.06, 0.06, 0.74, 0.82])

    mesh = map_ax.contourf(
        field.lon_grid,
        field.lat_grid,
        field.values,
        levels=levels,
        cmap=TEMPERATURE_CMAP,
        extend="both",
        zorder=1,
    )
    map_ax.contour(
        field.lon_grid,
        field.lat_grid,
        field.values,
        levels=levels,
        colors="white",
        linewidths=0.25,
        alpha=0.35,
        zorder=2,
    )

    _draw_department_boundaries(map_ax, department_rings)

    for ring in geometry.rings:
        map_ax.plot(ring.lons, ring.lats, color="black", linewidth=1.1, zorder=4)

    map_ax.scatter(
        field.station_lons,
        field.station_lats,
        s=22,
        color=STATION_DOT_COLOR,
        edgecolors=STATION_DOT_EDGE,
        linewidths=0.6,
        zorder=5,
    )

    lon_min, lon_max, lat_min, lat_max = geometry.bounds
    pad_lon = (lon_max - lon_min) * 0.04
    pad_lat = (lat_max - lat_min) * 0.04
    map_ax.set_xlim(lon_min - pad_lon, lon_max + pad_lon)
    map_ax.set_ylim(lat_min - pad_lat, lat_max + pad_lat)
    # adjustable="datalim": la relacion de aspecto real (lat/lon) se
    # preserva ajustando los limites de los ejes en lugar de "achicar" el
    # recuadro dentro de la figura. Esto evita que queden franjas blancas
    # grandes por fuera del cuadro fino en provincias muy alargadas
    # (ej. Tierra del Fuego), ya que el mapa ocupa todo el marco.
    map_ax.set_aspect("equal", adjustable="datalim")
    map_ax.set_xticks([])
    map_ax.set_yticks([])

    # El "cuadro blanco fino": marco delgado alrededor de todo el mapa.
    for spine in map_ax.spines.values():
        spine.set_visible(True)
        spine.set_edgecolor(FRAME_COLOR)
        spine.set_linewidth(FRAME_LINEWIDTH)

    # --- Cuadraditos semi-transparentes de extremos ------------------------
    province_bounds = (lon_min, lon_max, lat_min, lat_max)
    highest_offset = _extreme_box_offset(highest[2], highest[3], province_bounds)
    lowest_offset = _extreme_box_offset(lowest[2], lowest[3], province_bounds)

    highest_box = _draw_extreme_box(
        map_ax,
        highest[2],
        highest[3],
        "MAS ALTA",
        highest[1],
        highest[0],
        highest_offset,
    )
    lowest_box = _draw_extreme_box(
        map_ax,
        lowest[2],
        lowest[3],
        "MAS BAJA",
        lowest[1],
        lowest[0],
        lowest_offset,
    )

    # Si, con los offsets "hacia el centro", los dos cuadros de texto
    # terminan superpuestos (estaciones extremas cercanas entre si), se
    # separan verticalmente: uno arriba y el otro abajo de su estacion.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    if highest_box.get_window_extent(renderer).overlaps(
        lowest_box.get_window_extent(renderer)
    ):
        highest_box.remove()
        lowest_box.remove()
        highest_offset = (highest_offset[0], 42)
        lowest_offset = (lowest_offset[0], -42)
        _draw_extreme_box(
            map_ax,
            highest[2],
            highest[3],
            "MAS ALTA",
            highest[1],
            highest[0],
            highest_offset,
        )
        _draw_extreme_box(
            map_ax,
            lowest[2],
            lowest[3],
            "MAS BAJA",
            lowest[1],
            lowest[0],
            lowest_offset,
        )

    # --- Barra de colores (colormap) al costado ----------------------------
    cbar_ax = fig.add_axes([0.84, 0.08, 0.05, 0.78])
    norm = BoundaryNorm(levels, ncolors=256)
    cbar = fig.colorbar(mesh, cax=cbar_ax, norm=norm, ticks=levels)
    cbar.ax.tick_params(labelsize=9)
    for label in cbar.ax.get_yticklabels():
        label.set_fontproperties(_title_font(9))
    cbar.set_label(
        "Temperatura (°C)", fontproperties=_title_font(10), rotation=90
    )

    if source_note:
        fig.text(
            0.06,
            0.015,
            source_note,
            fontproperties=_title_font(7.5),
            ha="left",
            va="bottom",
            color="#555555",
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, facecolor="white")
    plt.close(fig)
    return output_path
