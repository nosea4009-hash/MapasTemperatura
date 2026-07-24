"""Interpolacion espacial de temperaturas puntuales (por estacion) a una
grilla regular, enmascarada al contorno de la provincia."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .data import StationDailyTemperature
from .geo import ProvinceGeometry

GRID_RESOLUTION = 300
MARGIN_DEG = 0.15
IDW_POWER = 2.0


@dataclass(frozen=True)
class InterpolatedField:
    """Campo de temperatura interpolado sobre una grilla regular."""

    lon_grid: np.ndarray
    lat_grid: np.ndarray
    values: np.ndarray  # masked array; NaN fuera de la provincia
    station_lons: np.ndarray
    station_lats: np.ndarray
    station_values: np.ndarray
    station_names: List[str]


def _inverse_distance_weighting(
    lon_grid: np.ndarray,
    lat_grid: np.ndarray,
    station_lons: np.ndarray,
    station_lats: np.ndarray,
    station_values: np.ndarray,
    power: float = IDW_POWER,
) -> np.ndarray:
    """Interpolacion IDW (Inverse Distance Weighting) vectorizada.

    Genera "manchas" circulares de color alrededor de cada estacion (mas
    intensas cerca del punto de medicion y difuminandose con la distancia),
    que es el aspecto visual de la imagen de referencia.
    """
    grid_lon_flat = lon_grid.ravel()[:, None]
    grid_lat_flat = lat_grid.ravel()[:, None]
    station_lon_row = station_lons[None, :]
    station_lat_row = station_lats[None, :]

    dist_sq = (grid_lon_flat - station_lon_row) ** 2 + (
        grid_lat_flat - station_lat_row
    ) ** 2
    dist_sq = np.maximum(dist_sq, 1e-12)
    weights = 1.0 / (dist_sq ** (power / 2.0))

    values_flat = (weights * station_values[None, :]).sum(axis=1) / weights.sum(
        axis=1
    )
    return values_flat.reshape(lon_grid.shape)


def interpolate_province_field(
    daily_temps: List[StationDailyTemperature],
    geometry: ProvinceGeometry,
    resolution: int = GRID_RESOLUTION,
) -> InterpolatedField:
    """Interpola las temperaturas de las estaciones sobre una grilla regular
    recortada al contorno de la provincia.

    Se usa IDW (Inverse Distance Weighting), que genera zonas de color en
    forma de "mancha" alrededor de cada estacion, similar al aspecto visual
    de la imagen de referencia.

    Args:
        daily_temps: temperaturas diarias (min o max) por estacion.
        geometry: geometria de la provincia (para el recorte y los limites
            de la grilla).
        resolution: cantidad de puntos de grilla por eje.

    Raises:
        ValueError: si hay menos de 2 estaciones con datos (no se puede
            interpolar).
    """
    if len(daily_temps) < 2:
        raise ValueError(
            "Se necesitan al menos 2 Estaciones Meteorologicas con datos "
            "validos en la provincia para poder interpolar un mapa."
        )

    station_lons = np.array([dt.station.lon for dt in daily_temps])
    station_lats = np.array([dt.station.lat for dt in daily_temps])
    station_values = np.array([dt.value for dt in daily_temps])
    station_names = [dt.station.name for dt in daily_temps]

    lon_min, lon_max, lat_min, lat_max = geometry.bounds
    lon_min -= MARGIN_DEG
    lon_max += MARGIN_DEG
    lat_min -= MARGIN_DEG
    lat_max += MARGIN_DEG

    lon_lin = np.linspace(lon_min, lon_max, resolution)
    lat_lin = np.linspace(lat_min, lat_max, resolution)
    lon_grid, lat_grid = np.meshgrid(lon_lin, lat_lin)

    values = _inverse_distance_weighting(
        lon_grid, lat_grid, station_lons, station_lats, station_values
    )

    inside_mask = geometry.contains_points(lon_grid, lat_grid)
    values = np.where(inside_mask, values, np.nan)

    return InterpolatedField(
        lon_grid=lon_grid,
        lat_grid=lat_grid,
        values=values,
        station_lons=station_lons,
        station_lats=station_lats,
        station_values=station_values,
        station_names=station_names,
    )


def extreme_stations(
    field: InterpolatedField,
) -> Tuple[Tuple[str, float, float, float], Tuple[str, float, float, float]]:
    """Devuelve la estacion con el valor mas bajo y la de valor mas alto.

    Returns:
        ((nombre, valor, lon, lat) del minimo, (nombre, valor, lon, lat) del maximo)
    """
    idx_min = int(np.argmin(field.station_values))
    idx_max = int(np.argmax(field.station_values))
    lowest = (
        field.station_names[idx_min],
        float(field.station_values[idx_min]),
        float(field.station_lons[idx_min]),
        float(field.station_lats[idx_min]),
    )
    highest = (
        field.station_names[idx_max],
        float(field.station_values[idx_max]),
        float(field.station_lons[idx_max]),
        float(field.station_lats[idx_max]),
    )
    return lowest, highest
