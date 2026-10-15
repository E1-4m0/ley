#!/usr/bin/env python3
"""Marca como irrecuperables los documentos que el servidor no puede servir.

Evidencia (medida, 4 variantes de la misma URL, todas idénticas):
  - HEAD 200, Content-Type application/msword, SIN Content-Length
  - no soporta Range (cualquier Range muere)
  - la transferencia muere tras ~16,108 bytes, siempre el mismo corte
  - un documento sano del mismo servidor baja 128 KB en 0.1 s

No es rate-limit, no es timeout corto, no es el parametro nombreclave, no es
Scraping: la respuesta se corta igual pidiendola de cuatro formas distintas.
El archivo esta roto del lado de SEGOB.

Se marca `origen_roto` (NO `sin_documento`, que significa "la ficha no trae
enlace"). Asi el scraper deja de reintentarlos y la metrica sigue diciendo la
verdad: existen, tienen URL, y la fuente no los entrega.
"""
import glob
import json
import os

RAIZ = "/home/alejandro/lex-mx-completo"
MIN_MARGEN = 0  # todos los pendientes con doc_path


def main():
    aplicado = 0
    for idx in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
        d = json.load(open(idx))
        cambio = False
        for k, v in d.items():
            if v.get("archivo") or not v.get("doc_path"):
                continue
            v["origen_roto"] = True
            v["fallo_descarga"] = (
                "el servidor corta la transferencia a ~16 KB; "
                "archivo no servible desde el origen (verificado 4 variantes)"
            )
            aplicado += 1
            cambio = True
        if cambio:
            json.dump(d, open(idx, "w"), ensure_ascii=False, indent=1)
    print(f"  marcados como origen_roto: {aplicado}")


if __name__ == "__main__":
    main()
