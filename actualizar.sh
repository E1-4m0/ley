#!/usr/bin/env bash
#
# Actualiza el repositorio `ley` (acervo estatal de SEGOB).
#
# Re-escanea las 32 fuentes estatales, baja solo lo que falte o haya cambiado,
# y si hay algo nuevo hace commit y push.
#
# SILENCIOSO cuando no hay nada nuevo (patrón watchdog): no imprime nada y no
# manda mensaje. Solo habla si bajó documentos o si el push falló.
#
# Uso:  ./actualizar.sh
#
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")" && pwd)"
PYTHON=/usr/bin/python3
LOG="$RAIZ/actualizacion.log"

cd "$RAIZ" || exit 1

# 1. bajar lo que falte
ANTES="$(find datos -name '_index.json' -exec cat {} + 2>/dev/null | grep -c '"archivo"' || echo 0)"
SALIDA="$("$PYTHON" descargar.py todos 2>&1)"
DESPUES="$(find datos -name '_index.json' -exec cat {} + 2>/dev/null | grep -c '"archivo"' || echo 0)"
NUEVOS=$((DESPUES - ANTES))

# 2. convertir a Markdown lo que se haya bajado
CONV="$("$PYTHON" convertir_md.py 2>&1)"
MD_ANTES="$(find markdown -name '*.md' 2>/dev/null | wc -l)"

{
  echo "--- $(date -Iseconds) · nuevos=$NUEVOS ---"
  echo "$SALIDA" | tail -40
  echo "$CONV" | tail -20
} >> "$LOG"

CAMBIOS="$(git status --porcelain | wc -l)"

if [[ "$NUEVOS" -le 0 && "$CAMBIOS" -eq 0 ]]; then
  exit 0   # nada nuevo: silencio total
fi

git add -A >> "$LOG" 2>&1
if git diff --cached --quiet; then
  exit 0
fi

git commit -q -m "Acervo estatal: $NUEVOS documentos nuevos

Actualizacion automatica del $(date +%Y-%m-%d).
Markdown en el repositorio: $(find markdown -name '*.md' | wc -l) archivos." >> "$LOG" 2>&1

if git push >> "$LOG" 2>&1; then
  echo "Acervo estatal: $NUEVOS documentos nuevos, subidos. Markdown: $(find markdown -name '*.md' | wc -l) archivos."
else
  echo "Acervo estatal: $NUEVOS documentos nuevos, pero el PUSH FALLO. Ver $LOG"
  exit 1
fi
