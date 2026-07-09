#!/usr/bin/env python3
"""
main.py - Descarga imágenes para el "Collage de Mina" y actualiza
automáticamente el bloque <div class="collage"> en index.html.

CÓMO USARLO
-----------
1. Coloca este archivo (main.py) dentro de la carpeta "Collage de Mina",
   junto a index.html y style.css.
2. Escribe una URL de imagen por línea en el archivo "urls.txt"
   (que se crea solo la primera vez que corres el script si no existe).
   Puedes agregar comentarios con "#" al inicio de una línea.
3. Instala la única dependencia externa que se usa:
       pip install requests
4. Corre:
       python main.py
5. El script:
   - Descarga cada URL nueva de urls.txt (las que ya se descargaron antes
     no se vuelven a bajar).
   - Detecta la extensión real de la imagen (jpeg, png, webp, gif...).
   - Nombra los archivos siguiendo tu convención actual: img, img1, img2...
     continuando desde el número más alto que ya exista en la carpeta.
   - Reescribe SOLO el bloque <div class="collage">...</div> de index.html
     con un <img> por cada imagen que haya en la carpeta (las viejas + las
     nuevas), en el mismo orden numérico. El resto del HTML (banner,
     estilos, etc.) no se toca.

No hace falta tocar nada del CSS: sigue funcionando igual porque las
clases y estructura no cambian.
"""

import json
import mimetypes
import os
import re
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit(
        "Falta la librería 'requests'. Instálala con:\n"
        "    pip install requests"
    )

# --------------------------------------------------------------------------
# Configuración (puedes ajustar estos valores si cambias nombres de archivo)
# --------------------------------------------------------------------------
CARPETA = Path(__file__).parent.resolve()
ARCHIVO_URLS = CARPETA / "urls.txt"
ARCHIVO_HTML = CARPETA / "index.html"
REGISTRO_DESCARGAS = CARPETA / ".descargas.json"  # evita re-descargar lo mismo
PREFIJO_IMAGEN = "img"
EXTENSIONES_VALIDAS = {".jpeg", ".jpg", ".png", ".gif", ".webp"}

PLANTILLA_URLS = """# Pega aquí una URL de imagen por línea.
# Las líneas que empiecen con # se ignoran.
# Ejemplo:
# https://ejemplo.com/foto1.jpg
# https://ejemplo.com/foto2.png
"""


def cargar_registro():
    if REGISTRO_DESCARGAS.exists():
        return json.loads(REGISTRO_DESCARGAS.read_text(encoding="utf-8"))
    return {}


def guardar_registro(registro):
    REGISTRO_DESCARGAS.write_text(
        json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def leer_urls():
    if not ARCHIVO_URLS.exists():
        ARCHIVO_URLS.write_text(PLANTILLA_URLS, encoding="utf-8")
        print(f"Cree '{ARCHIVO_URLS.name}' (estaba vacío). "
              "Agrega tus URLs ahí y vuelve a correr el script.")
        return []

    urls = []
    for linea in ARCHIVO_URLS.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            urls.append(linea)
    return urls


def indices_existentes():
    """Devuelve la lista de índices numéricos ya usados por archivos img*.ext
    que ya están en la carpeta (img.jpeg -> 0, img1.png -> 1, etc.)."""
    indices = []
    patron = re.compile(rf"^{PREFIJO_IMAGEN}(\d*)\.(\w+)$", re.IGNORECASE)
    for archivo in CARPETA.iterdir():
        if archivo.suffix.lower() in EXTENSIONES_VALIDAS:
            m = patron.match(archivo.name)
            if m:
                numero = m.group(1)
                indices.append(int(numero) if numero else 0)
    return indices


def siguiente_nombre(indice):
    """indice 0 -> 'img', indice 1 -> 'img1', indice 2 -> 'img2', etc."""
    return PREFIJO_IMAGEN if indice == 0 else f"{PREFIJO_IMAGEN}{indice}"


def extension_desde_respuesta(url, respuesta):
    tipo_contenido = respuesta.headers.get("Content-Type", "").split(";")[0].strip()
    ext = mimetypes.guess_extension(tipo_contenido or "")
    if ext == ".jpe":
        ext = ".jpeg"
    if ext and ext.lower() in EXTENSIONES_VALIDAS:
        return ext.lower()

    # Si el servidor no manda un Content-Type útil, probamos con la URL
    ext_url = Path(url.split("?")[0]).suffix.lower()
    if ext_url in EXTENSIONES_VALIDAS:
        return ".jpeg" if ext_url == ".jpg" else ext_url

    return ".jpeg"  # valor por defecto razonable


def descargar_imagen(url, nombre_base):
    print(f"  Descargando: {url}")
    respuesta = requests.get(url, timeout=20)
    respuesta.raise_for_status()

    ext = extension_desde_respuesta(url, respuesta)
    nombre_archivo = f"{nombre_base}{ext}"
    ruta_destino = CARPETA / nombre_archivo
    ruta_destino.write_bytes(respuesta.content)
    print(f"    -> guardada como {nombre_archivo}")
    return nombre_archivo


def descargar_pendientes():
    urls = leer_urls()
    if not urls:
        return

    registro = cargar_registro()
    ya_descargadas = set(registro.keys())
    pendientes = [u for u in urls if u not in ya_descargadas]

    if not pendientes:
        print("No hay URLs nuevas en urls.txt (todo ya estaba descargado).")
        return

    indice_actual = max(indices_existentes(), default=-1) + 1

    print(f"Descargando {len(pendientes)} imagen(es) nueva(s)...")
    for url in pendientes:
        nombre_base = siguiente_nombre(indice_actual)
        try:
            nombre_archivo = descargar_imagen(url, nombre_base)
            registro[url] = nombre_archivo
            indice_actual += 1
        except requests.RequestException as error:
            print(f"    (!) No se pudo descargar {url}: {error}")

    guardar_registro(registro)


def listar_imagenes_ordenadas():
    """Todas las imágenes de la carpeta, ordenadas img, img1, img2... img10..."""
    patron = re.compile(rf"^{PREFIJO_IMAGEN}(\d*)\.(\w+)$", re.IGNORECASE)
    imagenes = []
    for archivo in CARPETA.iterdir():
        if archivo.suffix.lower() in EXTENSIONES_VALIDAS:
            m = patron.match(archivo.name)
            if m:
                numero = int(m.group(1)) if m.group(1) else 0
                imagenes.append((numero, archivo.name))
    imagenes.sort(key=lambda par: par[0])
    return [nombre for _, nombre in imagenes]


def actualizar_html():
    if not ARCHIVO_HTML.exists():
        print(f"(!) No se encontró {ARCHIVO_HTML.name}; no se actualizó el HTML.")
        return

    imagenes = listar_imagenes_ordenadas()
    if not imagenes:
        print("No hay imágenes en la carpeta; no se actualizó el HTML.")
        return

    nuevo_bloque_tiles = "\n".join(
        f'            <img src="{nombre}" class="tile" alt="">' for nombre in imagenes
    )
    nuevo_bloque = f'<div class="collage">\n{nuevo_bloque_tiles}\n        </div>'

    html_original = ARCHIVO_HTML.read_text(encoding="utf-8")
    patron_collage = re.compile(
        r'<div class="collage">.*?</div>', re.DOTALL
    )

    if not patron_collage.search(html_original):
        print("(!) No se encontró el bloque <div class=\"collage\">...</div> "
              "en index.html; no se hicieron cambios.")
        return

    html_actualizado = patron_collage.sub(nuevo_bloque, html_original, count=1)
    ARCHIVO_HTML.write_text(html_actualizado, encoding="utf-8")
    print(f"index.html actualizado con {len(imagenes)} imagen(es): "
          f"{', '.join(imagenes)}")


def main():
    print(f"Carpeta del proyecto: {CARPETA}")
    descargar_pendientes()
    actualizar_html()
    print("Listo. Abre index.html en tu navegador para ver el resultado.")


if __name__ == "__main__":
    main()
