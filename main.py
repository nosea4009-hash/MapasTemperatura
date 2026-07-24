#!/usr/bin/env python3
"""CLI para generar mapas de temperaturas minimas/maximas de una provincia
argentina, para un dia seleccionado, usando datos oficiales de las
Estaciones Meteorologicas (EMAs) del Servicio Meteorologico Nacional (SMN).

Fuente de datos: https://www.smn.gob.ar/descarga-de-datos

Ejemplos de uso:

    python main.py --provincia "La Pampa" --fecha 20260722 --variable min
    python main.py --provincia "Buenos Aires" --fecha 20260722 --variable max
    python main.py --listar-provincias
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from smn_maps.data import (
    compute_daily_metric_by_station,
    load_daily_observations,
    load_stations,
    stations_by_province,
)
from smn_maps.geo import get_province_geometry, list_provinces, load_department_boundaries
from smn_maps.interpolate import interpolate_province_field
from smn_maps.plotting import render_temperature_map
from smn_maps.smn_download import SMNDownloadError

DEFAULT_CACHE_DIR = Path(".smn_cache")
DEFAULT_OUTPUT_DIR = Path("output")


def _valid_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Fecha invalida: '{value}'. Debe tener formato YYYYMMDD (ej: 20260722)."
        ) from exc
    if parsed > date.today():
        raise argparse.ArgumentTypeError(
            f"La fecha '{value}' es futura. El SMN solo publica datos ya observados."
        )
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Genera un mapa de temperaturas minimas o maximas registradas "
            "en las Estaciones Meteorologicas (EMAs) de una provincia "
            "argentina, para un dia dado, usando datos oficiales del SMN."
        )
    )
    parser.add_argument(
        "--provincia",
        type=str,
        default=None,
        help='Nombre de la provincia (ej: "La Pampa", "Buenos Aires", "Córdoba").',
    )
    parser.add_argument(
        "--fecha",
        type=_valid_date,
        default=None,
        help="Fecha en formato YYYYMMDD (ej: 20260722).",
    )
    parser.add_argument(
        "--variable",
        choices=["min", "max"],
        default="min",
        help="Temperatura minima ('min') o maxima ('max') del dia. Default: min.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=None,
        help=(
            "Ruta del archivo .png de salida. Por defecto se guarda en "
            f"'{DEFAULT_OUTPUT_DIR}/<provincia>_<variable>_<fecha>.png'."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE_DIR,
        help=(
            "Directorio de cache local para no volver a descargar los "
            f"mismos archivos del SMN en corridas repetidas. Default: {DEFAULT_CACHE_DIR}."
        ),
    )
    parser.add_argument(
        "--sin-cache",
        action="store_true",
        help="Ignora el cache local y fuerza la descarga de datos frescos del SMN.",
    )
    parser.add_argument(
        "--listar-provincias",
        action="store_true",
        help="Muestra las provincias disponibles (segun ar.json) y termina.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.listar_provincias:
        for name in list_provinces():
            print(name)
        return 0

    if not args.provincia or not args.fecha:
        parser.error(
            "Los argumentos --provincia y --fecha son obligatorios "
            "(o use --listar-provincias)."
        )

    cache_dir = None if args.sin_cache else args.cache_dir

    try:
        geometry = get_province_geometry(args.provincia)
    except KeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Descargando listado de Estaciones Meteorologicas (EMAs) del SMN...")
    try:
        stations = load_stations(cache_dir=cache_dir)
    except SMNDownloadError as exc:
        print(f"Error al descargar estaciones: {exc}", file=sys.stderr)
        return 1

    stations_in_province = stations_by_province(stations, geometry.name)
    if not stations_in_province:
        print(
            f"Error: no se encontraron Estaciones Meteorologicas del SMN "
            f"para la provincia '{geometry.name}'.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Descargando observaciones horarias del {args.fecha} "
        f"(https://www.smn.gob.ar/descarga-de-datos)..."
    )
    try:
        observations = load_daily_observations(args.fecha, cache_dir=cache_dir)
    except SMNDownloadError as exc:
        print(f"Error al descargar observaciones: {exc}", file=sys.stderr)
        return 1

    daily_metric = compute_daily_metric_by_station(
        observations, stations_in_province, args.variable
    )
    if len(daily_metric) < 2:
        print(
            f"Error: solo se encontraron datos validos en "
            f"{len(daily_metric)} estacion(es) de '{geometry.name}' para "
            f"el {args.fecha}. Se necesitan al menos 2 para generar el mapa.",
            file=sys.stderr,
        )
        return 1

    print(f"Estaciones con datos validos en {geometry.name}: {len(daily_metric)}")

    department_rings = load_department_boundaries(geometry.name)
    field = interpolate_province_field(daily_metric, geometry)

    output_path = args.salida
    if output_path is None:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        province_slug = geometry.name.replace(" ", "_")
        output_path = (
            DEFAULT_OUTPUT_DIR / f"{province_slug}_{args.variable}_{args.fecha}.png"
        )

    saved_path = render_temperature_map(
        field=field,
        geometry=geometry,
        department_rings=department_rings,
        metric=args.variable,
        date_str=args.fecha,
        province_label=geometry.name,
        output_path=output_path,
    )

    print(f"Mapa generado exitosamente: {saved_path.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
