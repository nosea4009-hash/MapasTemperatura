"""Descarga de datos oficiales del Servicio Meteorologico Nacional (SMN).

Fuente oficial: https://www.smn.gob.ar/descarga-de-datos

El SMN publica dos archivos de interes para este proyecto:

1. Observaciones horarias de todas las Estaciones Meteorologicas (EMAs):
   https://ssl.smn.gob.ar/dpd/descarga_opendata.php?file=observaciones/datohorario<YYYYMMDD>.txt

2. Listado de estaciones (nombre, provincia, latitud, longitud, altura):
   https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones  (archivo .zip)

Ambos archivos vienen en un formato de columnas de ancho fijo, codificados en
ISO-8859-1 (latin-1).
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Optional

import requests

SMN_MEASURED_URL = (
    "https://ssl.smn.gob.ar/dpd/descarga_opendata.php"
    "?file=observaciones/datohorario{fecha}.txt"
)
SMN_STATIONS_ZIP_URL = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones"

REQUEST_TIMEOUT = 60
USER_AGENT = "Mozilla/5.0 (MapasTemperatura/1.0; +https://github.com/nosea4009-hash/MapasTemperatura)"


class SMNDownloadError(RuntimeError):
    """Se produjo un error al descargar o interpretar datos del SMN."""


def download_measured_text(fecha: str, cache_dir: Optional[Path] = None) -> str:
    """Descarga el archivo de observaciones horarias para una fecha dada.

    Args:
        fecha: fecha en formato YYYYMMDD.
        cache_dir: si se provee, se guarda/lee una copia local en este
            directorio para evitar descargas repetidas.

    Returns:
        El contenido del archivo como texto (decodificado en latin-1).

    Raises:
        SMNDownloadError: si el archivo no existe para esa fecha o si hubo
            un error de red.
    """
    if cache_dir is not None:
        cache_path = Path(cache_dir) / f"datohorario{fecha}.txt"
        if cache_path.exists():
            return cache_path.read_text(encoding="latin-1")

    url = SMN_MEASURED_URL.format(fecha=fecha)
    try:
        response = requests.get(
            url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SMNDownloadError(
            f"No se pudo conectar con el SMN para descargar datos del {fecha}: {exc}"
        ) from exc

    response.encoding = "latin-1"
    text = response.text

    if "El archivo no existe" in text or not text.strip():
        raise SMNDownloadError(
            f"El SMN no tiene datos de observaciones horarias disponibles para "
            f"el {fecha}. Verifique la fecha (formato YYYYMMDD) o intente con "
            f"un dia anterior."
        )

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"datohorario{fecha}.txt").write_text(text, encoding="latin-1")

    return text


def download_stations_text(cache_dir: Optional[Path] = None) -> str:
    """Descarga y descomprime el listado oficial de Estaciones Meteorologicas.

    Args:
        cache_dir: si se provee, se guarda/lee una copia local en este
            directorio para evitar descargas repetidas.

    Returns:
        El contenido del archivo de estaciones como texto (latin-1).

    Raises:
        SMNDownloadError: si hubo un error de red o al descomprimir el zip.
    """
    if cache_dir is not None:
        cache_path = Path(cache_dir) / "estaciones_smn.txt"
        if cache_path.exists():
            return cache_path.read_text(encoding="latin-1")

    try:
        response = requests.get(
            SMN_STATIONS_ZIP_URL,
            timeout=REQUEST_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SMNDownloadError(
            f"No se pudo descargar el listado de Estaciones Meteorologicas "
            f"del SMN: {exc}"
        ) from exc

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            inner_name = zf.namelist()[0]
            raw_bytes = zf.read(inner_name)
    except zipfile.BadZipFile as exc:
        raise SMNDownloadError(
            "El archivo de estaciones descargado del SMN no es un zip valido."
        ) from exc

    text = raw_bytes.decode("latin-1")

    if cache_dir is not None:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / "estaciones_smn.txt").write_text(text, encoding="latin-1")

    return text
