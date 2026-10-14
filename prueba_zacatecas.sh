#!/usr/bin/env bash
# Limpia la muestra de prueba y re-descarga Zacatecas con el parser corregido.
set -euo pipefail

cd /home/alejandro/lex-mx-completo
export LEX_SALIDA=/home/alejandro/lex-mx-completo/datos

echo "=== 1. Limpiar muestra de prueba (12 archivos con nombres roto) ==="
rm -rf datos/zacatecas
echo "  limpio"

echo
echo "=== 2. Re-descargar Zacatecas completo (47 ordenamientos) ==="
timeout 540 python3 descargar.py 32 2>&1 | tail -6

echo
echo "=== 3. Verificar que los títulos ahora salen bien ==="
python3 - <<'PYEOF'
import json, glob, os
for idx in sorted(glob.glob('/home/alejandro/lex-mx-completo/datos/*/_index.json')):
    d = json.load(open(idx))
    con_titulo = sum(1 for v in d.values() if v.get('titulo') and v['titulo'] != 'sin-titulo')
    con_doc    = sum(1 for v in d.values() if v.get('archivo'))
    estado     = os.path.basename(os.path.dirname(idx))
    print(f"  [{estado}] {len(d)} fichas | {con_titulo} con título | {con_doc} con documento")
    for v in list(d.values())[:5]:
        print(f"      {str(v.get('tipo'))[:14]:15s} | {str(v.get('titulo'))[:56]}")
        print(f"          fecha={v.get('fecha_publicacion')} | {v.get('estatus')} | {v.get('bytes','-')} bytes")
PYEOF

echo
echo "=== 4. Peso en disco ==="
du -sh datos/* 2>/dev/null
