#!/usr/bin/env python3
"""Nodo verificador del grafo: la PUERTA en la arista.

Ningún hallazgo baja al informe sin que se haya intentado matarlo. Aquí el juez
es código, no otro agente: si la cita textual que devolvió el nodo de extracción
no aparece literalmente en el documento fuente, el hallazgo se cae.

Cuesta cero tokens y no se deja convencer.

Uso:
    python3 verificar.py hallazgos.json
hallazgos.json = [{"archivo": "...", "que": "...", "articulo": "...", "cita": "..."}]
"""
import json
import os
import re
import sys
import unicodedata


def normaliza(t):
    """Quita acentos y colapsa espacios: el corpus y el modelo no escriben igual."""
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"\s+", " ", t)
    return t.lower().strip()


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else "hallazgos.json"
    with open(ruta, encoding="utf-8") as f:
        hallazgos = json.load(f)

    textos = {}
    vivos, muertos = [], []

    for h in hallazgos:
        src = h["archivo"]
        if src not in textos:
            with open(src, encoding="utf-8", errors="ignore") as f:
                textos[src] = normaliza(f.read())

        cita = normaliza(h.get("cita", ""))
        if not cita:
            muertos.append((h, "sin cita"))
            continue

        if cita in textos[src]:
            vivos.append(h)
        else:
            # segundo intento: por fragmentos largos, por si el modelo unió dos párrafos
            trozos = [t for t in re.split(r"(?<=\.)\s+", cita) if len(t) > 40]
            encontrados = sum(1 for t in trozos[:3] if t in textos[src])
            if trozos and encontrados == len(trozos[:3]):
                vivos.append(h)
            else:
                muertos.append((h, f"no aparece textual ({encontrados}/{min(3, len(trozos))} fragmentos)"))

    print(f"hallazgos: {len(hallazgos)} · verificados: {len(vivos)} · rechazados: {len(muertos)}")
    for h, motivo in muertos:
        print(f"  ✗ {h.get('articulo', '?')}: {h.get('que', '')[:70]}")
        print(f"      motivo: {motivo}")
    print("\nlos que pasan la puerta:")
    for h in vivos:
        print(f"  ✓ {h.get('articulo', '?'):<18} {h.get('que', '')[:70]}")

    with open("verificados.json", "w", encoding="utf-8") as f:
        json.dump(vivos, f, ensure_ascii=False, indent=2)
    with open("rechazados.json", "w", encoding="utf-8") as f:
        json.dump([{"hallazgo": h, "motivo": m} for h, m in muertos], f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
