#!/usr/bin/env bash
#
# Publica el proyecto "ley" (lex-mx-completo) en GitHub.
#
# Requisito: estar autenticado con `gh auth login` (lo corre el usuario, no el
# agente — nunca se piden credenciales por chat).
#
# Uso:
#   ./subir.sh                    # crea el repo como privado
#   ./subir.sh --publico          # crea el repo como público
#   ./subir.sh --nombre otro      # cambia el nombre del repo
#
set -euo pipefail

NOMBRE="ley"
VISIBILIDAD="--private"
DESCRIPCION="Acervo jurídico mexicano completo: 35,132 ordenamientos estatales de SEGOB, descargables y en Markdown"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --publico) VISIBILIDAD="--public"; shift ;;
    --nombre)  NOMBRE="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "opción desconocida: $1" >&2; exit 1 ;;
  esac
done

cd "$(dirname "$0")"

echo "==> 1/5  Verificando autenticación"
if ! gh auth status >/dev/null 2>&1; then
  echo
  echo "  ✗ No hay sesión de GitHub."
  echo "    Corre esto tú, en la Pi:"
  echo
  echo "        gh auth login"
  echo
  echo "    (elige GitHub.com → HTTPS → login por navegador)"
  echo "    Luego vuelve a correr ./subir.sh"
  exit 1
fi
USUARIO="$(gh api user --jq .login)"
echo "    ✓ sesión de: $USUARIO"

echo "==> 2/5  Verificando que no haya cambios sin comprometer"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "    hay cambios sin comprometer:"
  git status --short | sed 's/^/      /'
  echo
  read -rp "    ¿Comprometo todo antes de subir? [s/N] " R
  [[ "$R" =~ ^[sS]$ ]] || { echo "    cancelado"; exit 1; }
  git add -A
  git commit -m "Actualización antes de publicar"
fi
echo "    ✓ árbol limpio"

echo "==> 3/5  Tamaño del repo"
TAM="$(du -sh .git | cut -f1)"
ARCHIVOS="$(git ls-files | wc -l)"
echo "    .git: $TAM  ·  archivos versionados: $ARCHIVOS"
if [[ "$ARCHIVOS" -gt 100000 ]]; then
  echo "    ⚠️  son muchísimos archivos; el push puede tardar bastante"
fi

echo "==> 4/5  Creando el repositorio remoto"
if git remote get-url origin >/dev/null 2>&1; then
  echo "    ya existe origin: $(git remote get-url origin)"
else
  gh repo create "$NOMBRE" $VISIBILIDAD --source=. --description "$DESCRIPCION"
  echo "    ✓ creado: $USUARIO/$NOMBRE"
fi

echo "==> 5/5  Configurando las credenciales de git y subiendo"
# `gh auth login` autentica a gh, pero NO a git: sin esto el push muere con
# "could not read Username for 'https://github.com'". setup-git le enseña a git
# a usar el token de gh.
if ! git config --get-regexp 'credential\..*\.helper' >/dev/null 2>&1; then
  echo "    configurando el helper de credenciales de git…"
  gh auth setup-git
fi
echo "    subiendo (~400 MB, puede tardar varios minutos)…"
git push -u origin "$(git branch --show-current)"

echo
echo "✓ Listo: https://github.com/$USUARIO/$NOMBRE"
