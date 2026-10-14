#!/usr/bin/env python3
"""
Lanzador con vigilante anti-atasco.

El servidor de SEGOB a veces deja una conexión colgada y el cliente se queda
esperando indefinidamente (observado: 3 h sin avanzar, CPU 0%). Este lanzador
corre la descarga, vigila el conteo de archivos y, si no avanza en N segundos,
mata el proceso y lo relanza. La descarga es reanudable, así que retomar es
seguro y no se pierde nada.
"""
import glob
import json
import os
import signal
import subprocess
import sys
import time

RAIZ = "/home/alejandro/lex-mx-completo"
DATOS = f"{RAIZ}/datos"
# Fijo, NO sys.executable: cuando el cronjob lo lanza usa el python de Hermes,
# que no tiene curl_cffi y mata la descarga con ModuleNotFoundError.
PYTHON = "/usr/bin/python3"
SIN_AVANCE = 300      # segundos sin avanzar antes de reiniciar
CHEQUEO = 30          # cada cuánto revisar
MAX_REINICIOS = 40


def contar():
    n = 0
    for pat in ("*.doc", "*.docx", "*.pdf"):
        n += len(glob.glob(f"{DATOS}/*/{pat}"))
    return n


def latido():
    """Lee el latido que escribe descargar.py. -1 si no existe."""
    try:
        d = json.load(open(f"{DATOS}/_progreso.json"))
        return d.get("t", -1), d
    except Exception:
        return -1, {}


def descarga_viva():
    """PID de un descargar.py ya corriendo, o None.

    Evita lanzar un segundo descargador (que pelearía por los mismos
    archivos) cuando el vigilante se reinicia o el cronjob lo relanza.
    """
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode()
        except Exception:
            continue
        if "descargar.py" in cmd and "python" in cmd and "vigilante" not in cmd:
            return int(pid)
    return None


def lanzar():
    ya = descarga_viva()
    if ya:
        return None, ya
    env = dict(os.environ, LEX_SALIDA=DATOS)
    p = subprocess.Popen(
        [PYTHON, "descargar.py", "todos"],
        cwd=RAIZ, env=env,
        stdout=open(f"{RAIZ}/descarga.log", "a", buffering=1),
        stderr=subprocess.STDOUT,
        # CRÍTICO: sesión propia para que el hijo tenga su PROPIO grupo de
        # procesos. Sin esto comparte el grupo del vigilante y killpg() se
        # mata a sí mismo al intentar limpiar el hijo atascado.
        start_new_session=True,
    )
    return p, p.pid


def main():
    print(f"  vigilante iniciado · reinicia tras {SIN_AVANCE}s sin latido", flush=True)
    proc, pid = lanzar()
    print(f"  {'enganchado a descarga existente' if proc is None else 'descarga lanzada'} "
          f"· pid {pid}", flush=True)
    ultimo = contar()
    ultimo_cambio = time.time()
    ultimo_latido = time.time()
    t_lat_visto = 0
    reinicios = 0

    while True:
        time.sleep(CHEQUEO)
        actual = contar()
        t_lat, info = latido()

        # Una descarga nueva no debe heredar el latido viejo: solo cuenta si
        # es más reciente que el último que ya vimos.
        if t_lat > t_lat_visto:
            t_lat_visto = t_lat
            ultimo_latido = time.time()

        if actual != ultimo:
            print(f"  [{time.strftime('%H:%M:%S')}] {actual:,} documentos", flush=True)
            ultimo = actual
            ultimo_cambio = time.time()

        # ¿el proceso terminó por su cuenta?
        # (si nos enganchamos a uno existente, proc es None: revisamos por PID)
        vivo = proc is not None and proc.poll() is None
        if proc is None:
            vivo = descarga_viva() is not None

        if not vivo:
            if actual >= 35000 or reinicios >= MAX_REINICIOS:
                print(f"  FIN: {actual:,} documentos · {reinicios} reinicios", flush=True)
                return
            print(f"  [{time.strftime('%H:%M:%S')}] proceso terminó en {actual:,} "
                  f"— relanzando", flush=True)
            proc, pid = lanzar()
            ultimo_latido = time.time()
            reinicios += 1
            continue

        # ATASCO REAL: ni avanza el conteo NI late el proceso.
        # (el conteo plano por sí solo es normal durante el re-escaneo)
        if (time.time() - ultimo_latido > SIN_AVANCE
                and time.time() - ultimo_cambio > SIN_AVANCE):
            est = info.get("estado", "?")
            print(f"  [{time.strftime('%H:%M:%S')}] ATASCADO en {actual:,} "
                  f"(estado {est}) — matando y relanzando (reinicio {reinicios+1})",
                  flush=True)
            objetivo = proc.pid if proc is not None else descarga_viva()
            if objetivo:
                try:
                    os.killpg(os.getpgid(objetivo), signal.SIGKILL)
                except Exception:
                    try:
                        os.kill(objetivo, signal.SIGKILL)
                    except Exception:
                        pass
            if proc is not None:
                try:
                    proc.wait(timeout=30)
                except Exception:
                    pass
            time.sleep(2)
            proc, pid = lanzar()
            ultimo_latido = time.time()
            ultimo_cambio = time.time()
            reinicios += 1


if __name__ == "__main__":
    main()
