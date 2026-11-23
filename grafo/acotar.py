#!/usr/bin/env python3
"""Nodo 0 del grafo: ACOTAR.

Determinista y gratis: no llama a ningún modelo. Recorre el corpus, se queda con
los documentos que mencionan el tema y devuelve una lista con su ficha.

Es la "arista" del grafo: filtra y estructura en código, para que los agentes de
fan-out nunca lean un documento que no toca.

Uso:
    python3 acotar.py "autolavado" [--estado queretaro] [--max 40] [--out candidatos.json]
"""
import argparse
import json
import os
import re
import subprocess
import sys

RAIZ = os.path.expanduser("~/lex-mx-completo")
MD = os.path.join(RAIZ, "markdown")

RE_FRONT = re.compile(r"^---\n(.*?)\n---", re.S)


def ficha(path):
    """Lee el frontmatter YAML sin dependencias."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            head = f.read(2000)
    except OSError:
        return {}
    m = RE_FRONT.match(head)
    if not m:
        return {}
    datos = {}
    for linea in m.group(1).splitlines():
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        datos[clave.strip()] = valor.strip().strip('"')
    return datos


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tema")
    p.add_argument("--estado", default=None, help="filtra por estado (carpeta)")
    p.add_argument("--max", type=int, default=40)
    p.add_argument("--max-bytes", type=int, default=120_000,
                   help="descarta documentos más grandes que esto (un agente no lee 1.5 MB)")
    p.add_argument("--out", default="candidatos.json")
    args = p.parse_args()

    ruta = os.path.join(MD, args.estado) if args.estado else MD
    # grep -l con contexto de archivo: rápido y sin cargar nada en memoria
    res = subprocess.run(
        ["grep", "-rl", "-i", "-m1", args.tema, ruta],
        capture_output=True, text=True,
    )
    archivos = [a for a in res.stdout.splitlines() if a.endswith(".md")]

    cand = []
    for a in archivos:
        f = ficha(a)
        tam = os.path.getsize(a)
        if tam > args.max_bytes:
            continue
        # densidad: cuántas veces aparece el tema en el documento
        try:
            veces = int(subprocess.run(["grep", "-o", "-i", args.tema, a],
                                       capture_output=True, text=True).stdout.count("\n"))
        except ValueError:
            veces = 0
        cand.append({
            "archivo": a,
            "titulo": f.get("titulo", os.path.basename(a)),
            "tipo": f.get("tipo", ""),
            "estado": f.get("estado", ""),
            "status": f.get("status", ""),
            "fecha": f.get("fecha_publicacion", ""),
            "bytes": tam,
            "menciones": veces,
        })

    # Las leyes de ingresos son tarifas, no obligaciones: ruido para esta pregunta
    utiles = [c for c in cand if "ingresos" not in c["titulo"].lower()]
    descartados = len(cand) - len(utiles)

    # ordenar por densidad relativa, no por tamaño: el documento grande no es el relevante
    utiles.sort(key=lambda c: c["menciones"], reverse=True)
    seleccion = utiles[: args.max]

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(seleccion, f, ensure_ascii=False, indent=2)

    print(f"menciones: {len(cand)} · descartados (ingresos): {descartados} "
          f"· enviados al fan-out: {len(seleccion)}")
    for c in seleccion:
        print(f"  {c['estado']:<18} {c['menciones']:>3} menc  {c['bytes']:>7} B  {c['titulo'][:60]}")


if __name__ == "__main__":
    main()
