#!/usr/bin/env python3
"""
Guarda como Markdown el texto OCR de los documentos escaneados.

Algunos ordenamientos de SEGOB están escaneados: el .docx trae el contenido
como imágenes JPEG y word/document.xml casi vacío (visto: 28 caracteres de
texto y 55 imágenes). Sin este paso quedan fuera del corpus en Markdown.

Produce el mismo frontmatter que convertir_md.py, con una marca `ocr: true`
para que quien consuma el corpus sepa que el texto viene de reconocimiento
y puede traer errores.
"""
import glob
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path("/home/alejandro/lex-mx-completo")
DATOS = RAIZ / "datos"
MARKDOWN = RAIZ / "markdown"


def ocr_docx(ruta, tmp):
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


def limpiar(t):
    t = t.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def main():
    hechos = 0
    for idx in sorted(glob.glob(f"{DATOS}/*/_index.json")):
        estado = os.path.basename(os.path.dirname(idx))
        d = json.load(open(idx))
        for k, v in d.items():
            if not v.get("archivo"):
                continue
            ruta = DATOS / estado / v["archivo"]
            salida = MARKDOWN / estado / (Path(v["archivo"]).stem + ".md")
            if salida.exists() or not ruta.exists():
                continue
            try:
                with zipfile.ZipFile(ruta) as z:
                    xml = z.read("word/document.xml").decode("utf-8", "replace")
            except Exception:
                continue
            nimg = len(re.findall(r"r:embed", xml))
            if len(re.sub(r"<[^>]+>", "", xml).strip()) >= 200 or nimg == 0:
                continue  # tiene texto: lo maneja convertir_md.py
            print(f"  OCR [{estado}] {v['archivo'][:55]}", flush=True)
            with tempfile.TemporaryDirectory() as tmp:
                texto = limpiar(ocr_docx(ruta, tmp))
            if len(texto) < 100:
                print("    -> muy poco texto, se omite", flush=True)
                continue
            fm = [
                "---",
                f'titulo: "{v.get("titulo", "")}"',
                f'tipo: "{v.get("tipo", "")}"',
                f'estado: "{v.get("estado_nombre", estado)}"',
                'ambito: "Estatal"',
                f'estatus: "{v.get("estatus", "")}"',
                f'fecha_publicacion: "{v.get("fecha", "")}"',
                'fuente: "Orden Juridico Nacional, SEGOB"',
                f'id_ordenjuridico: "{k}"',
                'ocr: true',
                'nota: "Texto obtenido por reconocimiento óptico de imágenes; puede contener errores."',
                "---",
                "",
            ]
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text("\n".join(fm) + texto + "\n", encoding="utf-8")
            print(f"    -> {len(texto):,} caracteres -> {salida.name[:50]}", flush=True)
            hechos += 1
    print(f"  listo: {hechos} documentos escaneados guardados como Markdown", flush=True)


if __name__ == "__main__":
    main()
