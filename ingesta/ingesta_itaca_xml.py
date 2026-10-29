import os
import sys
import json
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import date
from glob import glob

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ingesta_itaca_xml")

RUTA_XML = "data/exported/Analisis_Academico"
RUTA_RAW = "data/raw"

TABLAS = ["cursos", "alumnos", "contenidos", "calificaciones"]
CAMPOS = {
    "cursos": ["codigo", "nombre_cas", "nombre_val", "abreviatura", "ensenanza", "padre"],
    "alumnos": [
        "NIA", "sexo", "nacionalidad", "provincia", "municipio", "ensenanza", "curso",
        "grupo", "turno", "linea", "modalidad", "repite", "estado_matricula",
        "tipo_matricula", "fecha_matricula", "fecha_ingreso_centro",
    ],
    "contenidos": ["codigo", "nombre_cas", "nombre_val", "ensenanza", "curso"],
    "calificaciones": [
        "evaluacion", "alumno", "ensenanza", "curso", "contenido",
        "bloque_contenido", "nota_numerica", "tipo_nota",
    ],
}
# Campos que contienen el NIA y deben anonimizarse (alumnos y su referencia en calificaciones)
CAMPOS_NIA = {"alumnos": "NIA", "calificaciones": "alumno"}

_cache_nia: dict[str, str] = {}


def anonimizar_nia(nia: str) -> str:
    # El hash se calcula una sola vez por NIA original y se reutiliza en todas las tablas
    if nia not in _cache_nia:
        _cache_nia[nia] = hashlib.sha256(str(nia).encode()).hexdigest()[:10]
    return _cache_nia[nia]


def parsear_xml(tabla: str) -> list[dict]:
    carpetas = sorted(glob(os.path.join(RUTA_XML, "*")))
    if not carpetas:
        raise FileNotFoundError(f"No hay carpetas de curso en {RUTA_XML}")

    registros = []
    for carpeta in carpetas:
        ruta = os.path.join(carpeta, f"{tabla}.xml")
        raiz = ET.parse(ruta).getroot()
        anyo = raiz.get("curso")  # Anyo = atributo curso de la cabecera <centro>
        # raiz[0] es el contenedor (<alumnos>, <cursos>...); los datos son atributos de cada nodo
        for nodo in raiz[0]:
            registro = {"Anyo": anyo}
            for campo in CAMPOS[tabla]:
                registro[campo] = nodo.get(campo)
            campo_nia = CAMPOS_NIA.get(tabla)
            if campo_nia and registro[campo_nia] is not None:
                registro[campo_nia] = anonimizar_nia(registro[campo_nia])
            registros.append(registro)
        logger.info("Leído %s (%s)", ruta, anyo)
    return registros


def guardar(datos: list[dict], nombre: str) -> None:
    fecha = date.today().isoformat()
    ruta = f"{RUTA_RAW}/{nombre}_{fecha}.json"
    os.makedirs(RUTA_RAW, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    logger.info("Guardados %d registros en %s", len(datos), ruta)


if __name__ == "__main__":
    try:
        for tabla in TABLAS:
            guardar(parsear_xml(tabla), tabla)
    except (ET.ParseError, OSError) as e:
        logger.exception("Error en la ingesta: %s", e)
        sys.exit(1)
