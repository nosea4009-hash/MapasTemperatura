"""Parseo de los archivos de ancho fijo publicados por el SMN.

Estos archivos no son CSV: son archivos de texto con columnas alineadas por
posicion de caracter. Ademas, el nombre de la estacion puede quedar cortado
al final de la linea y continuar en la linea siguiente (defecto conocido de
la fuente oficial), por lo que el parser reconstruye esos nombres.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Station:
    """Una Estacion Meteorologica (EMA) del SMN."""

    name: str
    province: str
    lat: float
    lon: float


@dataclass(frozen=True)
class HourlyObservation:
    """Una observacion horaria de temperatura en una estacion."""

    date: str  # DDMMYYYY, tal cual lo entrega el SMN
    hour: str
    temperature: float
    station_name: str


def _dms_to_decimal(deg: float, minute: float) -> float:
    """Convierte grados/minutos del SMN a grados decimales.

    El SMN reporta latitud/longitud como grados enteros (con signo) y
    minutos (siempre positivos). Ej: lat_g=-36, lat_m=35 -> -36.5833...
    """
    if deg < 0:
        return deg - minute / 60.0
    return deg + minute / 60.0


# Nombres de provincia tal cual los usa el SMN en estaciones_smn.txt.
# Se ordenan por longitud descendente para evitar matches parciales
# (ej. que "SANTA FE" quede subsumido en un nombre mas largo).
_SMN_PROVINCE_NAMES = sorted(
    [
        "BUENOS AIRES",
        "CAPITAL FEDERAL",
        "CATAMARCA",
        "CHACO",
        "CHUBUT",
        "CORDOBA",
        "CORRIENTES",
        "ENTRE RIOS",
        "FORMOSA",
        "JUJUY",
        "LA PAMPA",
        "LA RIOJA",
        "MENDOZA",
        "MISIONES",
        "NEUQUEN",
        "RIO NEGRO",
        "SALTA",
        "SAN JUAN",
        "SAN LUIS",
        "SANTA CRUZ",
        "SANTA FE",
        "SANTIAGO DEL ESTERO",
        "TIERRA DEL FUEGO",
        "TUCUMAN",
        "ANTARTIDA",
    ],
    key=len,
    reverse=True,
)

# Alias para normalizar el nombre de provincia al mismo usado en los geojson
# (ar.json / departamentos.geojson), que usan tildes y "Ciudad Autonoma...".
PROVINCE_NAME_ALIASES: Dict[str, str] = {
    "BUENOS AIRES": "Buenos Aires",
    "CAPITAL FEDERAL": "Ciudad Autónoma de Buenos Aires",
    "CATAMARCA": "Catamarca",
    "CHACO": "Chaco",
    "CHUBUT": "Chubut",
    "CORDOBA": "Córdoba",
    "CORRIENTES": "Corrientes",
    "ENTRE RIOS": "Entre Ríos",
    "FORMOSA": "Formosa",
    "JUJUY": "Jujuy",
    "LA PAMPA": "La Pampa",
    "LA RIOJA": "La Rioja",
    "MENDOZA": "Mendoza",
    "MISIONES": "Misiones",
    "NEUQUEN": "Neuquén",
    "RIO NEGRO": "Río Negro",
    "SALTA": "Salta",
    "SAN JUAN": "San Juan",
    "SAN LUIS": "San Luis",
    "SANTA CRUZ": "Santa Cruz",
    "SANTA FE": "Santa Fe",
    "SANTIAGO DEL ESTERO": "Santiago del Estero",
    "TIERRA DEL FUEGO": "Tierra del Fuego, Antártida e Islas del Atlántico Sur",
    "TUCUMAN": "Tucumán",
    "ANTARTIDA": "Antártida",
}


def parse_stations(raw_text: str) -> List[Station]:
    """Parsea el listado oficial de Estaciones Meteorologicas del SMN.

    El archivo (estaciones_smn.txt, obtenido de zipopendata.php?dato=estaciones)
    tiene 2 lineas de encabezado y luego una fila de ancho fijo por estacion:
        NOMBRE  PROVINCIA  LAT_GRADOS  LAT_MIN  LON_GRADOS  LON_MIN  ALTURA  NRO/OACI

    El nombre de estacion puede quedar cortado y continuar en la linea
    siguiente (defecto conocido del archivo oficial), por lo que se
    reconstruye buscando el nombre de provincia conocido dentro de cada
    linea en lugar de asumir columnas de ancho fijo estricto.

    Args:
        raw_text: contenido completo del archivo de estaciones (latin-1).

    Returns:
        Lista de objetos Station, con el nombre de provincia normalizado
        segun PROVINCE_NAME_ALIASES.
    """
    lines = raw_text.splitlines()
    stations: List[Station] = []
    pending: Optional[Dict] = None

    for line in lines[2:]:
        if not line.strip():
            continue

        matched = _match_province_line(line)
        if matched is not None:
            if pending is not None:
                station = _finalize_station(pending)
                if station is not None:
                    stations.append(station)
            pending = matched
        else:
            # Continuacion del nombre de estacion cortado en la linea anterior.
            if pending is not None:
                pending["name"] += line.strip()

    if pending is not None:
        station = _finalize_station(pending)
        if station is not None:
            stations.append(station)

    return stations


def _match_province_line(line: str) -> Optional[Dict]:
    for province_smn in _SMN_PROVINCE_NAMES:
        idx = line.find(province_smn)
        if idx == -1:
            continue
        name = line[:idx].strip()
        rest = line[idx + len(province_smn) :]
        numbers = re.findall(r"-?\d+\.?\d*", rest)
        if len(numbers) < 4:
            continue
        return {
            "name": name,
            "province_smn": province_smn,
            "numbers": numbers,
        }
    return None


def _finalize_station(pending: Dict) -> Optional[Station]:
    try:
        lat_deg, lat_min, lon_deg, lon_min = (
            float(pending["numbers"][0]),
            float(pending["numbers"][1]),
            float(pending["numbers"][2]),
            float(pending["numbers"][3]),
        )
    except (IndexError, ValueError):
        return None

    lat = _dms_to_decimal(lat_deg, lat_min)
    lon = _dms_to_decimal(lon_deg, lon_min)
    province = PROVINCE_NAME_ALIASES.get(
        pending["province_smn"], pending["province_smn"].title()
    )
    return Station(name=pending["name"].strip(), province=province, lat=lat, lon=lon)


def parse_measured(raw_text: str) -> List[HourlyObservation]:
    """Parsea el archivo de observaciones horarias (datohorarioYYYYMMDD.txt).

    Formato de columnas de ancho fijo (indices de caracter):
        [0:8]   FECHA (DDMMYYYY)
        [8:15]  HORA
        [15:21] TEMP (grados Celsius)
        [22:25] HUM
        [27:34] PNM
        [35:39] DD (direccion del viento)
        [40:45] FF (velocidad del viento)
        [46:]   NOMBRE de estacion (puede continuar en la linea siguiente)

    Args:
        raw_text: contenido completo del archivo de observaciones (latin-1).

    Returns:
        Lista de objetos HourlyObservation (solo se conservan filas con una
        temperatura numerica valida).
    """
    lines = raw_text.splitlines()
    observations: List[HourlyObservation] = []
    pending: Optional[Dict] = None

    for raw_line in lines[2:]:
        if not raw_line.strip():
            continue

        date_field = raw_line[:8]
        is_new_record = date_field.strip().isdigit() and len(date_field.strip()) == 8

        if is_new_record:
            if pending is not None:
                observations.append(_finalize_observation(pending))
            pending = {
                "date": date_field.strip(),
                "hour": raw_line[8:15].strip(),
                "temp_raw": raw_line[15:21].strip(),
                "station_name": raw_line[46:].strip(),
            }
        else:
            # Continuacion del nombre de estacion cortado en la linea anterior.
            if pending is not None:
                pending["station_name"] += raw_line.strip()

    if pending is not None:
        observations.append(_finalize_observation(pending))

    return [obs for obs in observations if obs is not None]


def _finalize_observation(pending: Dict) -> Optional[HourlyObservation]:
    temp_raw = pending["temp_raw"]
    try:
        temperature = float(temp_raw)
    except (TypeError, ValueError):
        return None
    return HourlyObservation(
        date=pending["date"],
        hour=pending["hour"],
        temperature=temperature,
        station_name=pending["station_name"].strip(),
    )
