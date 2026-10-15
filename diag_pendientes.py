#!/usr/bin/env python3
"""Diagnóstico: ¿por qué no bajan los 58 documentos pendientes?

El servidor acepta la conexión, manda ~16 KB y se queda colgado. Se prueba:
  1. HEAD  -> ¿declara Content-Length y Accept-Ranges?
  2. Range -> ¿acepta descarga por partes?
  3. stream -> ¿hasta dónde llega realmente antes de morir?
"""
import glob
import json
import time
from urllib.parse import quote

from curl_cffi import requests

BASE = "http://compilacion.ordenjuridico.gob.mx"
RAIZ = "/home/alejandro/lex-mx-completo"


def primer_pendiente():
    for i in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
        for k, v in json.load(open(i)).items():
            if not v.get("archivo") and v.get("doc_path"):
                return k, v
    return None, None


k, meta = primer_pendiente()
if not k:
    print("  no hay pendientes")
    raise SystemExit

ruta = quote(meta["doc_path"], safe="/")
clave = quote(meta.get("doc_nombre") or "doc.doc", safe="")
u = f"{BASE}/obtenerdoc.php?path={ruta}&nombreclave={clave}"
print(f"  id={k}   doc_path={meta['doc_path']}")

print("\n  --- 1. HEAD ---")
try:
    r = requests.head(u, impersonate="chrome", timeout=(10, 20))
    print(f"    status {r.status_code}")
    for h in ("Content-Length", "Accept-Ranges", "Content-Type", "Transfer-Encoding"):
        if h in r.headers:
            print(f"    {h}: {r.headers[h]}")
except Exception as ex:
    print(f"    falló: {type(ex).__name__}")

print("\n  --- 2. Range bytes=0-8191 ---")
t0 = time.time()
try:
    r = requests.get(u, impersonate="chrome", timeout=(10, 45),
                     headers={"Range": "bytes=0-8191"})
    print(f"    status {r.status_code}  {len(r.content):,} bytes en {time.time()-t0:.1f}s")
    print(f"    Content-Range: {r.headers.get('Content-Range')}")
except Exception as ex:
    print(f"    falló tras {time.time()-t0:.1f}s: {type(ex).__name__}")

print("\n  --- 3. stream incremental (corta a los 55s) ---")
t0 = time.time()
total = 0
try:
    r = requests.get(u, impersonate="chrome", timeout=(10, 60), stream=True)
    print(f"    status {r.status_code}")
    for chunk in r.iter_content(8192):
        total += len(chunk)
        if time.time() - t0 > 55:
            print(f"    cortado: {total:,} bytes en {time.time()-t0:.1f}s")
            break
    else:
        print(f"    COMPLETO: {total:,} bytes en {time.time()-t0:.1f}s")
except Exception as ex:
    print(f"    error tras {time.time()-t0:.1f}s con {total:,} bytes: {type(ex).__name__}")
