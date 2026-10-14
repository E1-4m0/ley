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
import os
import signal
import subprocess
import sys
import time

RAIZ = "/home/alejandro/lex-mx-completo"
DATOS = f"{RAIZ}/datos"
SIN_AVANCE = 300      # segundos sin avanzar antes de reiniciar
CHEQUEO = 30          # cada cuánto revisar
MAX_REINICIOS = 40


def contar():
    n = 0
    for pat in ("*.doc", "*.docx", "*.pdf"):
        n += len(glob.glob(f"{DATOS}/*/{pat}"))
    return n


def lanzar():
    env = dict(os.environ, LEX_SALIDA=DATOS)
    return subprocess.Popen(
        [sys.executable, "descargar.py", "todos"],
        cwd=RAIZ, env=env,
        stdout=open(f"{RAIZ}/descarga.log", "a", buffering=1),
        stderr=subprocess.STDOUT,
        # CRÍTICO: sesión propia para que el hijo tenga su PROPIO grupo de
        # procesos. Sin esto comparte el grupo del vigilante y killpg() se
        # mata a sí mismo al intentar limpiar el hijo atascado.
        start_new_session=True,
    )


def main():
    print(f"  vigilante iniciado · reinicia tras {SIN_AVANCE}s sin avance", flush=True)
    proc = lanzar()
    ultimo = contar()
    ultimo_cambio = time.time()
    reinicios = 0

    while True:
        time.sleep(CHEQUEO)
        actual = contar()

        if actual != ultimo:
            print(f"  [{time.strftime('%H:%M:%S')}] {actual:,} documentos", flush=True)
            ultimo = actual
            ultimo_cambio = time.time()

        # ¿el proceso terminó por su cuenta?
        if proc.poll() is not None:
            if actual >= 35000 or reinicios >= MAX_REINICIOS:
                print(f"  FIN: {actual:,} documentos · {reinicios} reinicios", flush=True)
                return
            # terminó antes de tiempo (¿error?): reintentar
            print(f"  [{time.strftime('%H:%M:%S')}] proceso terminó en {actual:,} "
                  f"— relanzando", flush=True)
            proc = lanzar()
            ultimo_cambio = time.time()
            reinicios += 1
            continue

        # ¿lleva demasiado sin avanzar?
        if time.time() - ultimo_cambio > SIN_AVANCE:
            print(f"  [{time.strftime('%H:%M:%S')}] ATASCADO en {actual:,} — "
                  f"matando y relanzando (reinicio {reinicios+1})", flush=True)
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                proc.kill()
            proc.wait(timeout=30)
            proc = lanzar()
            ultimo_cambio = time.time()
            reinicios += 1


if __name__ == "__main__":
    main()
