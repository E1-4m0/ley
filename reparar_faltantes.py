#!/usr/bin/env python3
"""
Repara los 12 documentos que no se convirtieron a Markdown.

Son dos problemas distintos, y cada uno necesita tratamiento propio:

  A) ZIP CORRUPTO (6 archivos) — la descarga quedó truncada. Se borra el
     archivo dañado y se vuelve a bajar; el scraper lo reintenta solo.

  B) ESCANEADO (6 archivos) — el .docx trae el contenido como imágenes JPEG
     (hay documentos con 55 imágenes y 28 caracteres de texto). No hay texto
     que extraer: hay que OCR-ear cada imagen con tesseract.

El script clasifica cada caso, actúa, y al final rehace la conversión.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path("/home/alejandro/lex-mx-completo")
DATOS = RAIZ / "datos"
MARKDOWN = RAIZ / "markdown"


def pendientes():
    """(estado, meta, ruta_del_doc) de todo lo descargado sin .md."""
    for idx in sorted(glob.glob(f"{DATOS}/*/_index.json")):
        estado = os.path.basename(os.path.dirname(idx))
        for k, v in json.load(open(idx)).items():
            if not v.get("archivo"):
                continue
            stem = os.path.splitext(v["archivo"])[0]
            if os.path.exists(f"{MARKDOWN}/{estado}/{stem}.md"):
                continue
            yield estado, v, Path(f"{DATOS}/{estado}/{v['archivo']}")


def clasificar(ruta):
    """'corrupto' si el ZIP no abre, 'escaneado' si trae imágenes sin texto,
    'ok' si tiene texto extraíble."""
    if not zipfile.is_zipfile(ruta):
        return "corrupto", 0, 0
    try:
        with zipfile.ZipFile(ruta) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
            media = len([n for n in z.namelist() if n.startswith("word/media/")])
    except Exception:
        return "corrupto", 0, 0
    texto = re.sub(r"<[^>]+>", "", xml).strip()
    imgs = max(len(re.findall(r"r:embed", xml)), media)
    if len(texto) < 200 and imgs > 0:
        return "escaneado", len(texto), imgs
    return "ok", len(texto), imgs


def ocr_docx(ruta, tmp):
    """Extrae las imágenes del docx y les pasa tesseract en español."""
    with zipfile.ZipFile(ruta) as z:
        imgs = sorted(n for n in z.namelist() if n.startswith("word/media/"))
        z.extractall(tmp)
    partes = []
    for n in imgs:
        img = Path(tmp) / n
        try:
            r = subprocess.run(
                ["tesseract", str(img), "stdout", "-l", "spa", "--psm", "6"],
                capture_output=True, timeout=180,
            )
            t = r.stdout.decode("utf-8", errors="replace").strip()
            if len(t) > 20:
                partes.append(t)
        except Exception:
            continue
    return "\n\n".join(partes)


def main():
    aplicar = "--aplicar" in sys.argv
    casos = {"corrupto": [], "escaneado": [], "ok": []}

    for estado, meta, ruta in pendientes():
        if not ruta.exists():
            casos["corrupto"].append((estado, meta, ruta))
            continue
        tipo, ntex, nimg = clasificar(ruta)
        casos[tipo].append((estado, meta, ruta))

    print(f"  corruptos (re-descargar): {len(casos['corrupto'])}")
    print(f"  escaneados (OCR):         {len(casos['escaneado'])}")
    print(f"  con texto (re-convertir): {len(casos['ok'])}")

    if not aplicar:
        print("\n  (modo simulación — corre con --aplicar para ejecutar)")
        return

    # A) corruptos: borrar el archivo y limpiar la marca para que se rebaje
    for estado, meta, ruta in casos["corrupto"]:
        print(f"  borrando corrupto: {ruta.name[:60]}")
        ruta.unlink(missing_ok=True)
        idx = DATOS / estado / "_index.json"
        d = json.load(open(idx))
        k = None
        for kk, vv in d.items():
            if vv.get("archivo") == meta["archivo"]:
                k = kk
                break
        if k:
            d[k].pop("archivo", None)
            d[k].pop("bytes", None)
            d[k].pop("intentos", None)
            json.dump(d, open(idx, "w"), ensure_ascii=False, indent=1)

    # B) escaneados: OCR
    for estado, meta, ruta in casos["escaneado"]:
        print(f"  OCR: {ruta.name[:55]}")
        with tempfile.TemporaryDirectory() as tmp:
            texto = ocr_docx(ruta, tmp)
        print(f"    -> {len(texto):,} caracteres reconocidos")


if __name__ == "__main__":
    main()
