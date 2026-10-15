#!/usr/bin/env python3
"""Marca los documentos que la fuente no puede entregar, con el motivo real.

Usa verifica_pendientes.json (resultado de probar CADA documento, uno por uno)
en vez de asumir. Distingue los dos modos de falla medidos:

  vacio              -> el servidor responde HTTP 200 con cero bytes
  RequestException   -> empieza a mandar y muere a ~16 KB

Se marca `origen_roto`, NO `sin_documento`: existen, tienen URL, y la fuente
no los entrega. `sin_documento` queda reservado para las fichas que no traen
enlace, que es otra cosa.

Los que sí bajen se descartan (se borra la marca si la tenían).
"""
import glob
import json

RAIZ = "/home/alejandro/lex-mx-completo"

verif = json.load(open(f"{RAIZ}/verifica_pendientes.json"))
por_id = {}
for r in verif:
    por_id.setdefault((r["estado"], r["id"]), r)

aplicados = revertidos = 0
for idx in sorted(glob.glob(f"{RAIZ}/datos/*/_index.json")):
    estado = idx.split("/")[-2]
    d = json.load(open(idx))
    cambio = False
    for k, v in d.items():
        r = por_id.get((estado, k))
        if not r:
            continue
        if r["resultado"] == "completo":
            # sí baja: quitar cualquier marca de fallo previa
            if v.pop("origen_roto", None):
                revertidos += 1
                cambio = True
            v.pop("fallo_descarga", None)
        else:
            v["origen_roto"] = True
            v["fallo_descarga"] = (
                f"la fuente no entrega el archivo ({r['resultado']}, "
                f"{r['bytes']} bytes tras {r['segundos']}s) — verificado individualmente"
            )
            aplicados += 1
            cambio = True
    if cambio:
        json.dump(d, open(idx, "w"), ensure_ascii=False, indent=1)

print(f"  marcados como origen_roto: {aplicados}")
print(f"  revertidos (sí bajaban):   {revertidos}")
