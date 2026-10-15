#!/usr/bin/env python3
"""Recupera texto de documentos .doc corruptos de la SEGOB.

Tres documentos de los 28,088 no los convierte antiword ni catdoc:

  77860 (campeche)  OLE2 válido por fuera, pero las herramientas no sacan nada
  28070 (colima)    OLE2 dañado: "Can't read SSAT"
  28072 (colima)    83,968 bytes de los que solo 325 no son cero: archivo vacío

No hay LibreOffice ni pandoc en esta máquina, así que se extrae el texto
directamente de los flujos del archivo: dentro de un OLE2 el texto de Word
suele estar como UTF-16LE, y además quedan cadenas legibles en CP1252.

Esto NO reconstruye el documento: recupera lo que se pueda leer. Se marca
`recuperado_parcial` para que quede claro que no es una conversión limpia.
"""
import json
import os
import re
import sys

RAIZ = "/home/alejandro/lex-mx-completo"
MARKDOWN = os.path.join(RAIZ, "markdown")

OBJETIVOS = [
    ("campeche", "77860"),
    ("colima", "28070"),
    ("colima", "28072"),
]


def extraer(path: str) -> str:
    """Saca el texto legible de un archivo binario de Word."""
    d = open(path, "rb").read()

    partes = []

    # 1. UTF-16LE: el texto de Word suele ir así dentro del flujo WordDocument.
    #    Se buscan secuencias largas de caracteres imprimibles en pares
    #    byte+0x00, típicas de ASCII en UTF-16LE.
    for m in re.finditer(rb"(?:[\x20-\x7e][\x00]){25,}", d):
        try:
            t = m.group().decode("utf-16le", "ignore")
        except Exception:
            continue
        if t.strip():
            partes.append(t)

    # 2. CP1252/Latin-1 con acentos, que en UTF-16LE no aparecen por el byte 0.
    for m in re.finditer(rb"[\x20-\xff]{60,}", d):
        trozo = m.group()
        # descartar basura: si hay muchos bytes de control, no es texto
        imprimibles = sum(1 for b in trozo if 32 <= b < 127 or b in (0xa0, 0xc0))
        if imprimibles / len(trozo) < 0.85:
            continue
        try:
            t = trozo.decode("cp1252", "ignore")
        except Exception:
            continue
        if t.strip():
            partes.append(t)

    # limpiar y unir, quitando repetidos
    vistas, salida = set(), []
    for p in partes:
        p = re.sub(r"[ \t\u00a0]+", " ", p)
        p = re.sub(r"\n{3,}", "\n\n", p).strip()
        if len(p) < 30:
            continue
        clave = p[:100]
        if clave in vistas:
            continue
        vistas.add(clave)
        salida.append(p)

    return "\n\n".join(salida)


def main():
    aplicados = 0
    for estado, codigo in OBJETIVOS:
        idx_path = os.path.join(RAIZ, "datos", estado, "_index.json")
        if not os.path.exists(idx_path):
            print(f"  [{estado}] {codigo}: sin índice")
            continue
        indice = json.load(open(idx_path))
        reg = indice.get(codigo)
        if not reg or not reg.get("archivo"):
            print(f"  [{estado}] {codigo}: sin archivo registrado")
            continue

        # `archivo` guarda solo el nombre del fichero; el real está en
        # datos/<estado>/<archivo>.
        origen = os.path.join(RAIZ, "datos", estado, reg["archivo"])
        if not os.path.exists(origen):
            print(f"  [{estado}] {codigo}: no existe {origen}")
            continue

        texto = extraer(origen)
        if len(texto) < 200:
            reg["fallo_conversion"] = (
                f"irrecuperable: solo {len(texto)} caracteres legibles"
            )
            print(f"  [{estado}] {codigo}: irrecuperable ({len(texto)} car.)")
        else:
            base = os.path.splitext(os.path.basename(reg["archivo"]))[0]
            destino = os.path.join(MARKDOWN, estado, base + ".md")
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            titulo = reg.get("titulo") or base
            with open(destino, "w", encoding="utf-8") as f:
                f.write(
                    f"# {titulo}\n\n"
                    f"- Fuente: compilación.ordenjuridico.gob.mx\n"
                    f"- Estado: {estado} · id `{codigo}`\n"
                    f"- **Recuperado del binario**: el archivo original está dañado y "
                    f"no se pudo convertir de forma limpia. Este texto se extrajo "
                    f"directamente de los flujos del `.doc`, así que puede estar "
                    f"incompleto o desordenado.\n\n---\n\n{texto}\n"
                )
            reg["archivo_md"] = os.path.relpath(destino, RAIZ)
            reg["recuperado_parcial"] = True
            reg["caracteres_recuperados"] = len(texto)
            reg.pop("fallo_conversion", None)
            print(f"  [{estado}] {codigo}: recuperados {len(texto):,} caracteres -> {base}.md")
            aplicados += 1

        json.dump(indice, open(idx_path, "w"), ensure_ascii=False, indent=1)

    print(f"\n  recuperados: {aplicados} de {len(OBJETIVOS)}")


if __name__ == "__main__":
    main()
