#!/usr/bin/env python3
"""
lex-mx-completo — descarga el acervo jurídico mexicano completo.

Fuente: compilacion.ordenjuridico.gob.mx (Orden Jurídico Nacional, SEGOB).
Dominio público (Art. 14, Ley Federal del Derecho de Autor).

Pipeline:
  1. listPoder3.php?edo=N        -> enumera todos los ordenamientos de un estado
  2. fichaOrdenamiento2.php?id=X -> metadatos (tipo, fecha, estatus, título)
  3. obtenerdoc.php?path=...     -> descarga el documento (.doc/.pdf)
"""
import html as html_mod
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests

BASE = "http://compilacion.ordenjuridico.gob.mx"
SALIDA = Path(os.environ.get("LEX_SALIDA", Path.home() / "lex-mx-completo" / "datos"))
# Tras N corridas sin que el servidor entregue el archivo, la ficha se marca
# como resuelta. Sin este tope el scraper reintenta esas URLs en cada pasada
# y el re-escaneo nunca termina (quedó atorado 2 días con 17 fichas).
MAX_INTENTOS = 3

ESTADOS = {
    1: "aguascalientes", 2: "baja-california", 3: "baja-california-sur",
    4: "campeche", 5: "coahuila", 6: "colima", 7: "chiapas", 8: "chihuahua",
    9: "ciudad-de-mexico", 10: "durango", 11: "guanajuato", 12: "guerrero",
    13: "hidalgo", 14: "jalisco", 15: "estado-de-mexico", 16: "michoacan",
    17: "morelos", 18: "nayarit", 19: "nuevo-leon", 20: "oaxaca",
    21: "puebla", 22: "queretaro", 23: "quintana-roo", 24: "san-luis-potosi",
    25: "sinaloa", 26: "sonora", 27: "tabasco", 28: "tamaulipas",
    29: "tlaxcala", 30: "veracruz", 31: "yucatan", 32: "zacatecas",
}

SES = requests.Session(impersonate="chrome")


def get(url, intentos=2, pausa=1.5):
    """GET con reintentos y timeout acotado. Devuelve el texto o None.

    El servidor declara UTF-8 pero manda bytes fuera de rango en los acentos,
    así que se decodifica a mano: si UTF-8 estricto falla, se cae a cp1252.

    El timeout es (conexión, lectura) y va corto a propósito: una conexión
    colgada sin timeout dejó la descarga 4 horas parada.
    """
    for i in range(intentos):
        try:
            r = SES.get(url, timeout=(10, 30))
            if r.status_code == 200:
                return _decodificar(r.content)
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(pausa * (i + 1))
    return None


def _decodificar(raw):
    """Decodifica respuestas del servidor tolerando su codificación mixta."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # El sitio es de los 2000: cp1252 recupera los acentos correctamente.
        return raw.decode("cp1252", errors="replace")


def get_bytes(url, intentos=2):
    """Descarga binaria con timeout generoso.

    El servidor de SEGOB estrangula la velocidad cuando detecta muchas
    peticiones: se midió a ~0.4 KB/s (16 KB en 40 s). Con timeout de lectura
    de 45 s, cualquier archivo de más de ~20 KB se abortaba, y eran 58
    documentos atorados para siempre. La lectura se deja en 300 s y la
    conexión en 15 s.
    """
    for i in range(intentos):
        try:
            r = SES.get(url, timeout=(15, 300))
            if r.status_code == 200 and r.content:
                return r.content
        except Exception:
            pass
        time.sleep(5 * (i + 1))
    return None


def listar_estado(edo):
    """Enumera los IDs de todos los ordenamientos de un estado."""
    t = get(f"{BASE}/listPoder3.php?edo={edo}")
    if not t:
        return []
    return sorted(set(re.findall(r"fichaOrdenamiento2\.php\?idArchivo=(\d+)", t)))


def ficha(id_archivo):
    """Lee la ficha técnica: título, tipo, fecha, estatus, ruta del documento."""
    t = get(f"{BASE}/fichaOrdenamiento2.php?idArchivo={id_archivo}&ambito=estatal")
    if not t:
        return None

    # El servidor mezcla entidades HTML y caracteres mal codificados ("Ficha
    # t\uFFFDIcnica"), así que se decodifican entidades y se empareja tolerante.
    plano = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S | re.I)
    plano = re.sub(r"<[^>]+>", "|", plano)
    plano = html_mod.unescape(plano)
    celdas = [re.sub(r"\s+", " ", c).strip() for c in plano.split("|")]

    def valor(etiqueta):
        """Valor siguiente a una etiqueta, tolerando el carácter de reemplazo."""
        patron = re.compile(re.escape(etiqueta).replace(r"\ ", r"\s*"), re.I)
        for i, c in enumerate(celdas):
            if patron.fullmatch(c.rstrip(":").strip()):
                for sig in celdas[i + 1:i + 8]:
                    if sig and not patron.fullmatch(sig.rstrip(":").strip()):
                        return sig
        return None

    # El título es la primera celda no vacía después del encabezado de la ficha.
    titulo = None
    for i, c in enumerate(celdas):
        if re.search(r"Ficha t.?.{0,3}cnica del Ordenamiento", c, re.I):
            for sig in celdas[i + 1:i + 9]:
                if sig and sig.lower() != "imprimir":
                    titulo = sig
                    break
            break

    # OJO: la ruta lleva espacios ("/Documentos/ESTADO/NUEVO LEON/o4100383.doc"),
    # así que NO se puede excluir \s al capturarla — solo & y comillas.
    doc = re.search(r"obtenerdoc\.php\?path=([^\"&]+)&nombreclave=([^\"&\s]+)", t)
    return {
        "id": id_archivo,
        "titulo": titulo,
        "fecha_publicacion": valor("Fecha de publicación"),
        "poder": valor("Poder"),
        "ambito": valor("Ámbito") or valor("Ambito"),
        "estatus": valor("Estatus"),
        "tipo": valor("Tipo"),
        "localidad": valor("Localidad"),
        "doc_path": doc.group(1) if doc else None,
        "doc_nombre": doc.group(2) if doc else None,
    }


def nombre_seguro(s, maxlen=90):
    s = re.sub(r"[^\w\s\.\-áéíóúÁÉÍÓÚñÑ]", "", s or "sin-titulo", flags=re.U)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:maxlen].strip("-") or "sin-titulo"


def progreso(**datos):
    """Escribe un latido con el avance real.

    El conteo de archivos NO sirve como señal de vida: durante el re-escaneo
    de estados ya completados se queda plano aunque el proceso trabaje. Este
    latido sí distingue 'trabajando' de 'atascado'.
    """
    datos["t"] = time.time()
    try:
        (SALIDA / "_progreso.json").write_text(json.dumps(datos, ensure_ascii=False))
    except Exception:
        pass


def descargar_estado(edo, limite=None):
    """Descarga todos los ordenamientos de un estado."""
    nombre = ESTADOS[edo]
    destino = SALIDA / nombre
    destino.mkdir(parents=True, exist_ok=True)
    meta_path = destino / "_index.json"

    indice = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    ids = listar_estado(edo)
    if limite:
        ids = ids[:limite]
    print(f"  [{nombre}] {len(ids)} ordenamientos", flush=True)

    nuevos = 0
    sin_doc = 0
    for n, ida in enumerate(ids, 1):
        # Saltar lo ya resuelto: con archivo descargado, o ya marcado como
        # "la fuente no publica este documento" (si no, se re-consulta su
        # ficha en cada corrida y el re-escaneo se vuelve eterno).
        if ida in indice and (indice[ida].get("archivo") or indice[ida].get("sin_documento")):
            continue
        f = ficha(ida)
        if not f:
            # La ficha ni siquiera se pudo consultar (servidor caído, 404,
            # respuesta vacía). Antes se saltaba SIN marcarla, así que se
            # reintentaba en cada pasada y el re-escaneo nunca terminaba.
            prev = indice.get(ida) or {}
            prev["intentos"] = prev.get("intentos", 0) + 1
            if prev["intentos"] >= MAX_INTENTOS:
                # Igual que arriba: una ficha que no se pudo consultar NO es
                # lo mismo que un ordenamiento que la fuente no publica.
                prev["fallo_ficha"] = f"ficha ilegible tras {prev['intentos']} intentos"
            indice[ida] = prev
            progreso(estado=nombre, n=n, total=len(ids), nuevos=nuevos, estado_edo=edo)
            time.sleep(0.1)
            continue
        if f.get("doc_path"):
            # La ruta trae espacios sin codificar ("NUEVO LEON"), hay que escaparla.
            # OJO: no llamar `nombre` a estas variables — pisaría el nombre del
            # estado, que se usa en el log y en el resumen.
            ruta_url = quote(f["doc_path"], safe="/")
            clave_url = quote(f["doc_nombre"] or "doc.doc", safe="")
            url = f"{BASE}/obtenerdoc.php?path={ruta_url}&nombreclave={clave_url}"
            datos = get_bytes(url)
            if datos:
                ext = Path(f["doc_nombre"] or "doc.doc").suffix or ".doc"
                archivo = f"{ida}--{nombre_seguro(f['titulo'])}{ext}"
                (destino / archivo).write_bytes(datos)
                f["archivo"] = archivo
                f["bytes"] = len(datos)
                f.pop("intentos", None)
                nuevos += 1
            else:
                # La ficha trae enlace pero el servidor no entrega el archivo
                # (404, vacío o rechazo). Sin tope, la ficha se reintenta en
                # CADA corrida para siempre y el re-escaneo nunca termina.
                f["intentos"] = f.get("intentos", 0) + 1
                if f["intentos"] >= MAX_INTENTOS:
                    # OJO: NO marcar sin_documento aquí. La ficha SÍ trae
                    # enlace, así que el documento existe y es descargable;
                    # marcarlo como 'no existe' infla la cobertura con algo
                    # que sí se puede recuperar. Solo se deja de reintentar
                    # en esta pasada.
                    f["fallo_descarga"] = f"sin bajar tras {f['intentos']} intentos"
        else:
            # La ficha no trae enlace: la fuente simplemente no publica este
            # ordenamiento. Se marca para no volver a consultarlo.
            f["sin_documento"] = True
            sin_doc += 1
        indice[ida] = f
        # El latido va en CADA iteración, no cada 25: cuando quedan pocos
        # documentos no se alcanza el múltiplo de 25 y el vigilante cree que
        # el proceso está muerto. El disco aguanta este ritmo de sobra.
        progreso(estado=nombre, n=n, total=len(ids), nuevos=nuevos, estado_edo=edo)
        if n % 25 == 0:
            meta_path.write_text(json.dumps(indice, ensure_ascii=False, indent=1))
            print(f"    [{nombre}] {n}/{len(ids)} · {nuevos} nuevos", flush=True)
        time.sleep(0.1)

    meta_path.write_text(json.dumps(indice, ensure_ascii=False, indent=1))
    print(f"  [{nombre}] listo: {len(indice)} fichas, {nuevos} descargados ahora", flush=True)
    return len(indice), nuevos


def main():
    args = sys.argv[1:]
    limite = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    if args and args[0] != "todos":
        edos = [int(args[0])]
    else:
        edos = sorted(ESTADOS)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for edo in edos:
        try:
            descargar_estado(edo, limite)
        except KeyboardInterrupt:
            print("\n  interrumpido — el avance está guardado en _index.json")
            break
        except Exception as e:
            print(f"  [{ESTADOS.get(edo, edo)}] ERROR: {str(e)[:100]}")


if __name__ == "__main__":
    main()
