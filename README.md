# MapasTemperatura
Kiro, hazme un script de Python que haga plots de mapas de temperaturas maximas de una provincia argentina de un dia seleccionado. Los datos deben ser oficiales y sacados de estaciones meteorologicas (EMAs), los datos de las EMAS las puedes sacar  de aqui: https://www.smn.gob.ar/descarga-de-datos - Te dejo una imagen adjunta de como quiero que sea, necesito que visualmente sea IDENTICO, pero diferentes provincias (seleccionables) diferente data, y en lugar de textos grandes, necesito que el plot este dentro de un cuadrado blanco fino, con la colormap al costado indicando el gradiente usado para las temperaturas. Arriba del plot, debe decir en fuente Tahoma: "Temperaturas Minimas registradas el (YYYYMMDD) y al costado "Region (region, por ejemplo "Buenos Aires".) Tambien,  debe haber pequeños cuadraditos transparentes con texto tahoma bold dentro que indiquen los areas coloreadas con temperaturas mas bajas y mas altas, por ejemplo: "MAS BAJA: (valor celsius)" "MAS ALTA: (valor celsius)"

---

## Sobre este proyecto

Genera mapas de temperaturas **mínimas** o **máximas** registradas en un día
determinado, para cualquier provincia argentina, usando **datos oficiales**
de las Estaciones Meteorológicas (EMAs) del **Servicio Meteorológico
Nacional (SMN)**: https://www.smn.gob.ar/descarga-de-datos

El estilo visual replica el de la imagen de referencia: mapa dentro de un
marco (cuadro) blanco fino, colormap verde con su barra de colores al
costado, título superior en fuente Tahoma ("Temperaturas Mínimas/Máximas
registradas el (YYYYMMDD)" + "Región: <provincia>"), y dos cuadraditos
semi-transparentes con texto Tahoma en negrita indicando la estación con la
temperatura "MAS BAJA" y la de "MAS ALTA".

### Fuente de datos

Todos los datos provienen en tiempo real de los endpoints públicos del SMN:

- Observaciones horarias por estación:
  `https://ssl.smn.gob.ar/dpd/descarga_opendata.php?file=observaciones/datohorario<YYYYMMDD>.txt`
- Listado oficial de Estaciones Meteorológicas (nombre, provincia, lat/lon):
  `https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones`

La temperatura mínima/máxima diaria de cada estación se calcula tomando el
mínimo/máximo de todas las observaciones horarias de ese día para esa
estación.

Los contornos geográficos (límite provincial y límites de
departamentos/partidos, dibujados como referencia interna) se toman de los
archivos `ar.json` y `departamentos.geojson` incluidos en este repositorio.

## Estructura del proyecto

```
MapasTemperatura/
├── main.py                    # CLI: punto de entrada
├── smn_maps/
│   ├── smn_download.py        # Descarga de datos oficiales del SMN
│   ├── parsing.py             # Parseo de los archivos de ancho fijo del SMN
│   ├── data.py                 # Combina estaciones + observaciones -> Tmin/Tmax diaria
│   ├── geo.py                  # Carga de ar.json / departamentos.geojson, mascaras
│   ├── interpolate.py          # Interpolación espacial (IDW) sobre la provincia
│   └── plotting.py             # Generación del mapa (estilo visual solicitado)
├── ar.json                     # Geometrías de las 24 provincias/CABA
├── departamentos.geojson       # Geometrías de departamentos/partidos
└── requirements.txt
```

## Instalación

Requiere Python 3.10+.

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Mapa de temperaturas mínimas de La Pampa para el 22/07/2026
python main.py --provincia "La Pampa" --fecha 20260722 --variable min

# Mapa de temperaturas máximas de Buenos Aires
python main.py --provincia "Buenos Aires" --fecha 20260722 --variable max

# Ver el listado de provincias disponibles (tal como aparecen en ar.json)
python main.py --listar-provincias
```

### Argumentos

| Argumento          | Obligatorio | Descripción                                                                 |
|---------------------|:-----------:|-------------------------------------------------------------------------------|
| `--provincia`       | Sí          | Nombre de la provincia (ej: `"La Pampa"`, `"Buenos Aires"`, `"Córdoba"`).      |
| `--fecha`           | Sí          | Fecha en formato `YYYYMMDD` (debe ser una fecha ya observada, no futura).     |
| `--variable`        | No          | `min` (default) o `max`.                                                      |
| `--salida`          | No          | Ruta del `.png` de salida. Default: `output/<provincia>_<variable>_<fecha>.png`. |
| `--cache-dir`       | No          | Directorio de cache local para no re-descargar los mismos archivos. Default: `.smn_cache`. |
| `--sin-cache`       | No          | Ignora el cache y fuerza la descarga de datos frescos del SMN.                |
| `--listar-provincias` | No        | Muestra las provincias disponibles y termina.                                 |

### Notas

- Se necesitan al menos **2** Estaciones Meteorológicas con datos válidos en
  la provincia elegida para poder generar el mapa (para poder interpolar).
- Los nombres de provincia son tolerantes a variantes comunes: `"CABA"`,
  `"Capital Federal"` o `"Ciudad Autónoma de Buenos Aires"` resuelven todos a
  la Ciudad de Buenos Aires; `"Tierra del Fuego"` resuelve al nombre INDEC
  completo.
- La fuente "Tahoma" se usa si está instalada en el sistema; si no está
  disponible (común en servidores Linux), se usa automáticamente una
  alternativa sans-serif muy similar (Verdana / DejaVu Sans) sin romper la
  generación del gráfico.
