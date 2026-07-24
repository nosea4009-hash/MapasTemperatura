"""Combina estaciones y observaciones horarias para obtener Tmin/Tmax diaria
por Estacion Meteorologica (EMA), filtradas por provincia.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Literal, Optional

from .parsing import HourlyObservation, Station, parse_measured, parse_stations
from .smn_download import download_measured_text, download_stations_text

Metric = Literal["min", "max"]


@dataclass(frozen=True)
class StationDailyTemperature:
    """Temperatura minima o maxima diaria registrada en una estacion."""

    station: Station
    value: float


def _normalize(name: str) -> str:
    return " ".join(name.upper().split())


def load_stations(cache_dir: Optional[Path] = None) -> List[Station]:
    """Descarga (o lee de cache) y parsea el listado de EMAs del SMN."""
    raw_text = download_stations_text(cache_dir=cache_dir)
    return parse_stations(raw_text)


def load_daily_observations(
    fecha: str, cache_dir: Optional[Path] = None
) -> List[HourlyObservation]:
    """Descarga (o lee de cache) y parsea las observaciones horarias de un dia.

    Args:
        fecha: fecha en formato YYYYMMDD.
        cache_dir: directorio opcional de cache local.
    """
    raw_text = download_measured_text(fecha, cache_dir=cache_dir)
    return parse_measured(raw_text)


def stations_by_province(
    stations: List[Station], province: str
) -> Dict[str, Station]:
    """Filtra estaciones que pertenecen a una provincia (nombre normalizado).

    La comparacion es tolerante a variantes de nombre largo/corto (ej.
    "Tierra del Fuego" vs "Tierra del Fuego, Antártida e Islas del
    Atlántico Sur"): se considera match si uno de los nombres normalizados
    es prefijo del otro.

    Returns:
        Diccionario {nombre_normalizado_de_estacion: Station}.
    """
    target = _normalize(province)
    matches = {}
    for station in stations:
        station_province = _normalize(station.province)
        if (
            station_province == target
            or station_province.startswith(target)
            or target.startswith(station_province)
        ):
            matches[_normalize(station.name)] = station
    return matches


def compute_daily_metric_by_station(
    observations: List[HourlyObservation],
    stations_in_province: Dict[str, Station],
    metric: Metric,
) -> List[StationDailyTemperature]:
    """Calcula la temperatura minima o maxima diaria por estacion.

    Solo se consideran estaciones presentes en `stations_in_province`.

    Args:
        observations: observaciones horarias de un dia (todo el pais).
        stations_in_province: estaciones de la provincia de interes.
        metric: "min" o "max".

    Returns:
        Lista de StationDailyTemperature, una por estacion con datos.
    """
    temps_by_station: Dict[str, List[float]] = {}
    for obs in observations:
        key = _normalize(obs.station_name)
        if key not in stations_in_province:
            continue
        temps_by_station.setdefault(key, []).append(obs.temperature)

    results: List[StationDailyTemperature] = []
    for key, temps in temps_by_station.items():
        if not temps:
            continue
        value = min(temps) if metric == "min" else max(temps)
        results.append(
            StationDailyTemperature(station=stations_in_province[key], value=value)
        )

    return results
