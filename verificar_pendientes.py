#!/usr/bin/env python3
"""Verifica UNO POR UNO los pendientes antes de marcarlos como irrecuperables.

No se asume nada: cada documento se intenta bajar de verdad. Solo los que
fallan se marcan. Un documento sano de este servidor baja en menos de un
segundo (medido: 128 KB en 0.1 s), así que 25 s de margen sobra de sobra.

Salida: verifica_pendientes.json con el resultado de cada uno.
"""
import glob
import json
import time
from urllib.parse import quote

from curl_cffi import requests

BASE = "http://compilacion.ordenjuridico.gob.mx"
RAIZ = "/home/alejandro/lex-mx-completo"
MARGEN = 25  # segundos; un archivo sano tarda décimas


def pendientes():
    for idx in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
        estado = idx.split("/")[-2]
        d = json.load(open(idx))
        for k, v in d.items():
            if v.get("archivo") or not v.get("doc_path"):
                continue
            if v.get("origen_roto"):
                continue
            yield estado, k, v, idx


def probar(meta):
    ruta = quote(meta["doc_path"], safe="/")
    clave = quote(meta.get("doc_nombre") or "doc.doc", safe="")
    u = f"{BASE}/obtenerdoc.php?path={ruta}&nombreclave={clave}"
    t0 = time.time()
    total = 0
    try:
        r = requests.get(u, impersonate="chrome", timeout=(10, MARGEN), stream=True)
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if time.time() - t0 > MARGEN:
                return "cortado", total, r.status_code, time.time() - t0
        dt = time.time() - t0
        # OJO: si el servidor manda una respuesta vacía, iter_content() no
        # produce nada, el bucle no corre y antes se caía al return "completo"
        # marcando éxito con 0 bytes. Hay que mirar el estado y el tamaño.
        if r.status_code != 200:
            return f"HTTP {r.status_code}", total, r.status_code, dt
        if total == 0:
            return "vacio", total, r.status_code, dt
        if total < 500:
            return "diminuto", total, r.status_code, dt
        return "completo", total, r.status_code, dt
    except Exception as ex:
        return type(ex).__name__, total, None, time.time() - t0


resultados = []
for estado, k, v, idx in pendientes():
    res, total, code, dt = probar(v)
    marca = "✅" if res == "completo" else "❌"
    print(f"  {marca} [{estado}] {k}: {res} · {total:,} bytes · HTTP {code} · {dt:.1f}s", flush=True)
    resultados.append({"estado": estado, "id": k, "resultado": res,
                       "bytes": total, "http": code, "segundos": round(dt, 1)})

json.dump(resultados, open(f"{RAIZ}/verifica_pendientes.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
c = Counter(r["resultado"] for r in resultados)
print(f"\n  === RESUMEN ({len(resultados)} verificados) ===")
for k, n in c.most_common():
    print(f"    {n:>3}  {k}")
