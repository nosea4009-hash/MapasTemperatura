"""Utilidades geograficas: carga de los geojson de provincias y departamentos
argentinos incluidos en este repositorio (ar.json y departamentos.geojson),
y construccion de mascaras poligonales para la interpolacion.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Tuple

import numpy as np
from matplotlib.path import Path as MplPath

REPO_ROOT = Path(__file__).resolve().parent.parent
PROVINCES_GEOJSON = REPO_ROOT / "ar.json"
DEPARTMENTS_GEOJSON = REPO_ROOT / "departamentos.geojson"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_province_name(name: str) -> str:
    """Normaliza un nombre de provincia para comparaciones (sin tildes,
    sin puntuacion, minusculas, sin espacios extra)."""
    no_accents = _strip_accents(name).lower()
    no_punct = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in no_accents)
    return " ".join(no_punct.split())


@dataclass(frozen=True)
class Ring:
    """Un anillo de coordenadas (lon, lat) que forma parte de un poligono."""

    lons: np.ndarray
    lats: np.ndarray


@dataclass(frozen=True)
class ProvinceGeometry:
    """Geometria (uno o mas poligonos/anillos exteriores) de una provincia."""

    name: str
    rings: List[Ring]

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Retorna (lon_min, lon_max, lat_min, lat_max)."""
        all_lons = np.concatenate([ring.lons for ring in self.rings])
        all_lats = np.concatenate([ring.lats for ring in self.rings])
        return (
            float(all_lons.min()),
            float(all_lons.max()),
            float(all_lats.min()),
            float(all_lats.max()),
        )

    def contains_points(self, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
        """Devuelve una mascara booleana: True si el punto cae dentro de
        alguno de los anillos exteriores de la provincia."""
        points = np.column_stack([lons.ravel(), lats.ravel()])
        inside = np.zeros(points.shape[0], dtype=bool)
        for ring in self.rings:
            ring_points = np.column_stack([ring.lons, ring.lats])
            path = MplPath(ring_points)
            inside |= path.contains_points(points)
        return inside.reshape(lons.shape)


def _iter_exterior_rings(geometry: dict) -> Iterator[List[List[float]]]:
    """Itera los anillos exteriores (el primer anillo de cada poligono) de
    una geometria GeoJSON Polygon o MultiPolygon."""
    geom_type = geometry["type"]
    coordinates = geometry["coordinates"]
    if geom_type == "Polygon":
        yield coordinates[0]
    elif geom_type == "MultiPolygon":
        for polygon in coordinates:
            yield polygon[0]
    else:
        raise ValueError(f"Tipo de geometria no soportado: {geom_type}")


def load_province_geometries() -> dict:
    """Carga ar.json y devuelve un dict {nombre_normalizado: ProvinceGeometry}."""
    with open(PROVINCES_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)

    geometries: dict = {}
    for feature in data["features"]:
        name = feature["properties"]["name"]
        rings = []
        for ring_coords in _iter_exterior_rings(feature["geometry"]):
            arr = np.array(ring_coords, dtype=float)
            rings.append(Ring(lons=arr[:, 0], lats=arr[:, 1]))
        geometries[normalize_province_name(name)] = ProvinceGeometry(
            name=name, rings=rings
        )
    return geometries


def get_province_geometry(province: str) -> ProvinceGeometry:
    """Busca la geometria de una provincia por nombre (tolerante a tildes,
    mayusculas/minusculas y variantes de "Ciudad de Buenos Aires")."""
    geometries = load_province_geometries()
    target = normalize_province_name(province)

    if target in geometries:
        return geometries[target]

    # Alias comunes -> deben resolver a una clave EXACTA de `geometries`.
    aliases = {
        "caba": "ciudad de buenos aires",
        "capital federal": "ciudad de buenos aires",
        "ciudad autonoma de buenos aires": "ciudad de buenos aires",
    }
    alias_target = aliases.get(target)
    if alias_target is not None and alias_target in geometries:
        return geometries[alias_target]

    # "Tierra del Fuego, Antartida e Islas del Atlantico Sur" (nombre INDEC
    # completo) debe resolver a la clave "tierra del fuego" de ar.json.
    if target.startswith("tierra del fuego") and "tierra del fuego" in geometries:
        return geometries["tierra del fuego"]

    available = ", ".join(sorted(g.name for g in geometries.values()))
    raise KeyError(
        f"No se encontro la provincia '{province}' en ar.json. "
        f"Provincias disponibles: {available}"
    )


def list_provinces() -> List[str]:
    """Devuelve la lista de nombres de provincia disponibles en ar.json."""
    geometries = load_province_geometries()
    return sorted(g.name for g in geometries.values())


def load_department_boundaries(province: str) -> List[Ring]:
    """Carga los limites (anillos exteriores) de los departamentos/partidos
    de una provincia desde departamentos.geojson, para dibujarlos como
    referencia interna en el mapa (igual que en la imagen de referencia).

    Al igual que en get_province_geometry, el nombre es tolerante a
    variantes (ej. "Tierra del Fuego" vs "Tierra del Fuego, Antártida e
    Islas del Atlántico Sur", o "CABA"/"Ciudad Autónoma de Buenos Aires").
    """
    with open(DEPARTMENTS_GEOJSON, encoding="utf-8") as f:
        data = json.load(f)

    target = normalize_province_name(province)
    aliases = {
        "caba": "ciudad autonoma de buenos aires",
        "capital federal": "ciudad autonoma de buenos aires",
        "ciudad de buenos aires": "ciudad autonoma de buenos aires",
    }
    target = aliases.get(target, target)

    rings: List[Ring] = []
    for feature in data["features"]:
        province_name = feature["properties"]["provincia"]["nombre"]
        normalized_feature_province = normalize_province_name(province_name)
        if (
            normalized_feature_province != target
            and not normalized_feature_province.startswith(target)
            and not target.startswith(normalized_feature_province)
        ):
            continue
        for ring_coords in _iter_exterior_rings(feature["geometry"]):
            arr = np.array(ring_coords, dtype=float)
            rings.append(Ring(lons=arr[:, 0], lats=arr[:, 1]))
    return rings
