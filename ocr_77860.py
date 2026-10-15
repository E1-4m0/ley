#!/usr/bin/env python3
"""OCR del documento escaneado 77860 (campeche).

El .doc no trae texto: dentro del flujo WordDocument hay imágenes (un JPEG en
el offset 3699 y un BMP en el 48204) y ni una sola cadena UTF-16 legible. Es un
escaneo metido en un contenedor de Word — el mismo caso que ya se resolvió para
otros documentos del acervo.

Se extraen las imágenes y se les pasa tesseract en español.
"""
import os
import re
import subprocess
import tempfile

import olefile

RAIZ = "/home/alejandro/lex-mx-completo"
ORIGEN = os.path.join(
    RAIZ, "datos", "campeche",
    "77860--Reforma-al-Artículo-1-del-decreto-no.-130-de-la-LXII-"
    "Legislatura-del-H.-Congreso-del-Estad.doc",
)
DESTINO = os.path.join(
    RAIZ, "markdown", "campeche",
    "77860--Reforma-al-Artículo-1-del-decreto-no.-130-de-la-LXII-"
    "Legislatura-del-H.-Congreso-del-Estad.md",
)

TITULO = ("Reforma al Artículo 1 del decreto no. 130 de la LXII Legislatura "
          "del H. Congreso del Estado de Campeche.")


def extraer_imagenes(datos: bytes, tmp: str) -> list[str]:
    """Saca los JPEG y BMP embebidos en el flujo."""
    rutas = []

    # JPEG: empieza en FFD8FF y termina en FFD9
    for m in re.finditer(rb"\xff\xd8\xff", datos):
        ini = m.start()
        fin = datos.find(b"\xff\xd9", ini + 3)
        if fin == -1:
            continue
        blob = datos[ini:fin + 2]
        if len(blob) < 5000:      # ignorar miniaturas
            continue
        p = os.path.join(tmp, f"img_jpg_{ini}.jpg")
        open(p, "wb").write(blob)
        rutas.append(p)

    # BMP: firma "BM" + tamaño en los 4 bytes siguientes
    for m in re.finditer(rb"BM", datos):
        ini = m.start()
        if ini + 6 > len(datos):
            continue
        tam = int.from_bytes(datos[ini + 2:ini + 6], "little")
        if not (5000 < tam < 50_000_000) or ini + tam > len(datos):
            continue
        blob = datos[ini:ini + tam]
        p = os.path.join(tmp, f"img_bmp_{ini}.bmp")
        open(p, "wb").write(blob)
        rutas.append(p)

    return rutas


def main():
    o = olefile.OleFileIO(ORIGEN)
    datos = o.openstream("WordDocument").read()
    print(f"  WordDocument: {len(datos):,} bytes")

    with tempfile.TemporaryDirectory() as tmp:
        imgs = extraer_imagenes(datos, tmp)
        print(f"  imágenes extraídas: {len(imgs)}")
        for p in imgs:
            print(f"    {os.path.basename(p)} · {os.path.getsize(p):,} B")

        if not imgs:
            print("  no hay imágenes que OCR-ear")
            return

        textos = []
        for p in imgs:
            base = os.path.splitext(p)[0]
            subprocess.run(["tesseract", p, base, "-l", "spa"],
                           capture_output=True, timeout=300)
            txt = base + ".txt"
            if os.path.exists(txt):
                t = open(txt, encoding="utf-8", errors="ignore").read().strip()
                if len(t) > 40:
                    textos.append(t)
                    print(f"    OCR {os.path.basename(p)}: {len(t):,} caracteres")

    cuerpo = "\n\n".join(textos).strip()
    if len(cuerpo) < 200:
        print(f"  OCR insuficiente ({len(cuerpo)} caracteres): no se escribe archivo")
        return

    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as f:
        f.write(
            f"# {TITULO}\n\n"
            f"- Fuente: compilación.ordenjuridico.gob.mx\n"
            f"- Estado: campeche · id `77860`\n"
            f"- **OCR**: el archivo original es un escaneo dentro de un "
            f"contenedor `.doc` (imágenes, sin texto). Este contenido se obtuvo "
            f"con reconocimiento óptico de caracteres, así que puede tener "
            f"errores de lectura.\n\n---\n\n{cuerpo}\n"
        )
    print(f"\n  ✓ escrito {DESTINO} ({len(cuerpo):,} caracteres)")


if __name__ == "__main__":
    main()
