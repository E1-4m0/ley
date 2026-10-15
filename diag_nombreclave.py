#!/usr/bin/env python3
"""Última prueba: ¿el parametro nombreclave rompe la descarga?

Se pide el mismo documento de tres formas para aislar cual funciona.
"""
import glob
import json
import time
from urllib.parse import quote

from curl_cffi import requests

BASE = "http://compilacion.ordenjuridico.gob.mx"
RAIZ = "/home/alejandro/lex-mx-completo"

malo = None
for i in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
    for k, v in json.load(open(i)).items():
        if not v.get("archivo") and v.get("doc_path"):
            malo = (k, v)
            break
    if malo:
        break

k, meta = malo
ruta = quote(meta["doc_path"], safe="/")
clave = quote(meta.get("doc_nombre") or "doc.doc", safe="")
clave_cruda = meta.get("doc_nombre") or "doc.doc"

print(f"  id={k}")
print(f"  ruta:  {meta['doc_path']}")
print(f"  clave: {clave_cruda!r}")

variantes = [
    ("con nombreclave (lo que hace el scraper)", f"{BASE}/obtenerdoc.php?path={ruta}&nombreclave={clave}"),
    ("SIN nombreclave", f"{BASE}/obtenerdoc.php?path={ruta}"),
    ("nombreclave crudo sin escapar", f"{BASE}/obtenerdoc.php?path={ruta}&nombreclave={clave_cruda}"),
    ("path sin escapar (espacios crudos)", f"{BASE}/obtenerdoc.php?path={meta['doc_path']}&nombreclave={clave_cruda}"),
]

for etiqueta, u in variantes:
    print(f"\n  --- {etiqueta} ---")
    t0 = time.time()
    total = 0
    try:
        r = requests.get(u, impersonate="chrome", timeout=(10, 40), stream=True)
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if time.time() - t0 > 38:
                break
        print(f"    {r.status_code}  {total:,} bytes en {time.time()-t0:.1f}s")
    except Exception as ex:
        print(f"    ERROR tras {time.time()-t0:.1f}s con {total:,} bytes: {type(ex).__name__}")
