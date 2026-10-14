#!/usr/bin/env python3
"""
Convierte los documentos descargados (.doc) a Markdown limpio.

Los archivos vienen en dos formatos mezclados:
  - ZIP  (docx disfrazado de .doc)  -> se extrae el XML con zipfile
  - OLE2 (doc binario de Word 2003) -> se usa catdoc

Salida: un .md por ordenamiento, con frontmatter de metadatos, en la misma
estructura de carpetas que los datos crudos.
"""
import html as html_mod
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path("/home/alejandro/lex-mx-completo")
DATOS = RAIZ / "datos"
SALIDA = RAIZ / "markdown"


def formato(ruta):
    try:
        with open(ruta, "rb") as f:
            cab = f.read(8)
    except Exception:
        return "?"
    if cab[:4] == b"PK\x03\x04":
        return "zip"
    if cab[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole2"
    if cab[:5] == b"%PDF-":
        return "pdf"
    if cab[:5] == b"{\\rtf":
        return "rtf"
    return "?"


def limpiar(t):
    """Normaliza el texto extraído a Markdown legible."""
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\xa0", " ").replace("\u200b", "")
    # colapsar espacios sobrantes pero conservar estructura de párrafos
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    lineas = [l.rstrip() for l in t.split("\n")]
    return "\n".join(lineas).strip()


def titulo_markdown(texto):
    """Marca como encabezado la primera línea que parezca título de ley."""
    lineas = [l for l in texto.split("\n") if l.strip()]
    for i, l in enumerate(lineas[:12]):
        ls = l.strip()
        if re.match(r"^(LEY|C[ÓO]DIGO|CONSTITUCI[ÓO]N|REGLAMENTO|DECRETO|ACUERDO|"
                    r"ESTATUTO|REGLAS|LINEAMIENTOS|CONVENIO|DECLARATORIA)\b", ls, re.I) \
                and 8 < len(ls) < 200:
            return i, ls
    return None, None


def desde_zip(ruta):
    """Extrae texto de un docx (ZIP) leyendo word/document.xml."""
    with zipfile.ZipFile(ruta) as z:
        xml = None
        for n in z.namelist():
            if n.endswith("document.xml"):
                xml = z.read(n)
                break
        if xml is None:
            return None
    t = xml.decode("utf-8", errors="replace")
    # saltos de párrafo, tabuladores, saltos de línea explícitos
    t = re.sub(r"<w:br[^>]*/>", "\n", t)
    t = re.sub(r"<w:tab[^>]*/>", " ", t)
    t = re.sub(r"</w:p>", "\n\n", t)
    t = re.sub(r"<[^>]+>", "", t)
    return html_mod.unescape(t)


def desde_ole2(ruta):
    """Extrae texto de un .doc binario usando catdoc."""
    for exe, args in (("catdoc", ["catdoc", "-d", "utf-8", str(ruta)]),
                      ("antiword", ["antiword", "-m", "UTF-8.txt", str(ruta)])):
        try:
            r = subprocess.run(args, capture_output=True, timeout=90)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.decode("utf-8", errors="replace")
        except Exception:
            continue
    return None


def desde_pdf(ruta):
    """Extrae texto de un PDF.

    Hay archivos con extensión .doc cuyo contenido real es PDF (la firma es
    %PDF). Sin esta rama se descartaban silenciosamente.
    """
    try:
        r = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(ruta), "-"],
            capture_output=True, timeout=180,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.decode("utf-8", errors="replace")
    except Exception:
        pass
    return None


def convertir(ruta):
    fmt = formato(ruta)
    if fmt == "zip":
        return desde_zip(ruta)
    if fmt == "ole2":
        return desde_ole2(ruta)
    if fmt == "pdf":
        return desde_pdf(ruta)
    if fmt == "rtf":
        try:
            return ruta.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None
    return None


def main():
    estados = sys.argv[1:] or None
    SALIDA.mkdir(exist_ok=True)
    total = ok = fallos = 0
    for carpeta in sorted(DATOS.iterdir()):
        if not carpeta.is_dir():
            continue
        if estados and carpeta.name not in estados:
            continue
        idx_path = carpeta / "_index.json"
        indice = json.load(open(idx_path)) if idx_path.exists() else {}
        destino = SALIDA / carpeta.name
        destino.mkdir(parents=True, exist_ok=True)

        docs = sorted(carpeta.glob("*.doc")) + sorted(carpeta.glob("*.pdf"))
        print(f"  [{carpeta.name}] {len(docs)} documentos", flush=True)
        for d in docs:
            total += 1
            md_path = destino / (d.stem + ".md")
            if md_path.exists():
                ok += 1
                continue
            texto = convertir(d)
            if not texto or len(texto.strip()) < 50:
                fallos += 1
                continue
            texto = limpiar(texto)

            # metadatos de la ficha
            ida = d.name.split("--")[0]
            f = indice.get(ida, {})
            part_i, part_tit = titulo_markdown(texto)
            titulo = f.get("titulo") or part_tit or d.stem

            fm = [
                "---",
                f'titulo: "{titulo}"',
                f'tipo: "{f.get("tipo") or "Ordenamiento"}"',
                f'estado: "{carpeta.name.replace("-", " ").title()}"',
                f'ambito: "{f.get("ambito") or "Estatal"}"',
                f'estatus: "{f.get("estatus") or ""}"',
                f'fecha_publicacion: "{f.get("fecha_publicacion") or ""}"',
                f'fuente: "Orden Juridico Nacional, SEGOB"',
                f'id_ordenjuridico: "{ida}"',
                "---",
                "",
            ]
            cuerpo = texto
            if part_i is not None:
                lineas = texto.split("\n")
                lineas[part_i] = "# " + lineas[part_i].strip()
                cuerpo = "\n".join(lineas)
            md_path.write_text("\n".join(fm) + cuerpo + "\n", encoding="utf-8")
            ok += 1
        print(f"    [{carpeta.name}] listo", flush=True)

    print()
    print(f"  CONVERTIDOS: {ok} de {total}  ({100*ok//max(total,1)}%)")
    print(f"  FALLOS:      {fallos}")


if __name__ == "__main__":
    main()
