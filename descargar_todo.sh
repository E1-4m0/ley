#!/usr/bin/env bash
# Descarga completa del acervo jurídico estatal mexicano.
# Reanudable: lo ya descargado se salta.
set -uo pipefail

cd /home/alejandro/lex-mx-completo
export LEX_SALIDA=/home/alejandro/lex-mx-completo/datos
LOG=/home/alejandro/lex-mx-completo/descarga.log

echo "==============================================="
echo "  Descarga completa — 31 estados"
echo "  Inicio: $(date '+%Y-%m-%d %H:%M:%S')"
echo "==============================================="

# Zacatecas quedó con metadatos rotos del primer intento: se rehace.
if [ -d datos/zacatecas ]; then
  rm -rf datos/zacatecas
  echo "  zacatecas: muestra vieja retirada, se re-descarga limpio"
fi

INICIO=$(date +%s)
python3 descargar.py todos 2>&1 | tee -a "$LOG"
FIN=$(date +%s)

echo
echo "==============================================="
echo "  Terminado: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Duración: $(( (FIN-INICIO)/60 )) minutos"
echo "==============================================="

echo
echo "=== RESUMEN ==="
python3 - <<'PYEOF'
import json, glob, os
tot = 0; byt = 0; tit = 0; doc = 0; est = 0
for idx in sorted(glob.glob('/home/alejandro/lex-mx-completo/datos/*/_index.json')):
    d = json.load(open(idx))
    n_t = sum(1 for v in d.values() if v.get('titulo') and '\ufffd' not in v['titulo'])
    n_d = sum(1 for v in d.values() if v.get('archivo'))
    print(f"  {os.path.basename(os.path.dirname(idx)):24s} {len(d):>6d} fichas | {n_d:>6d} docs | {n_t:>6d} con título")
    tot += len(d); tit += n_t; doc += n_d
    byt += sum(v.get('bytes') or 0 for v in d.values())
    est += 1
print()
print(f"  ESTADOS: {est} | FICHAS: {tot} | DOCUMENTOS: {doc} | TÍTULOS OK: {tit} ({100*tit//max(tot,1)}%)")
print(f"  PESO TOTAL: {byt/1e9:.2f} GB")
PYEOF
du -sh datos 2>/dev/null
