#!/usr/bin/env python3
"""Compara un documento que SÍ bajó contra uno de los 58 que fallan.

Si ambos se comportan igual, el problema es del servidor para esos archivos
concretos. Si el bueno baja completo y el malo corta siempre en el mismo
byte, hay algo filtrando en la red.
"""
import glob
import json
import os
import time
from urllib.parse import quote

from curl_cffi import requests

BASE = "http://compilacion.ordenjuridico.gob.mx"
RAIZ = "/home/alejandro/lex-mx-completo"


def uno_ok():
    """Un documento ya descargado, con su doc_path guardado."""
    for i in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
        for k, v in json.load(open(i)).items():
            if v.get("archivo") and v.get("doc_path") and v.get("bytes"):
                return k, v
    return None, None


def uno_malo():
    for i in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
        for k, v in json.load(open(i)).items():
            if not v.get("archivo") and v.get("doc_path"):
                return k, v
    return None, None


def url_de(meta):
    ruta = quote(meta["doc_path"], safe="/")
    clave = quote(meta.get("doc_nombre") or "doc.doc", safe="")
    return f"{BASE}/obtenerdoc.php?path={ruta}&nombreclave={clave}"


for etiqueta, getter in (("BUENO (ya bajado)", uno_ok), ("MALO (de los 58)", uno_malo)):
    k, meta = getter()
    if not k:
        print(f"  {etiqueta}: no encontrado")
        continue
    u = url_de(meta)
    print(f"\n=== {etiqueta} ===")
    print(f"  id={k}  bytes_registrados={meta.get('bytes')}")
    print(f"  path={meta['doc_path']}")
    t0 = time.time()
    total = 0
    try:
        r = requests.get(u, impersonate="chrome", timeout=(10, 90), stream=True)
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if time.time() - t0 > 85:
                break
        print(f"  -> {r.status_code}  {total:,} bytes en {time.time()-t0:.1f}s")
    except Exception as ex:
        print(f"  -> ERROR tras {time.time()-t0:.1f}s con {total:,} bytes: {type(ex).__name__}")

# Tercera prueba: el MALO con otro user-agent (sin impersonate)
k, meta = uno_malo()
u = url_de(meta)
print(f"\n=== MALO con requests normal (sin impersonate) ===")
import urllib.request
t0 = time.time()
try:
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        datos = r.read()
    print(f"  -> {len(datos):,} bytes en {time.time()-t0:.1f}s  firma={datos[:4]!r}")
except Exception as ex:
    print(f"  -> ERROR tras {time.time()-t0:.1f}s: {type(ex).__name__}: {ex}")
