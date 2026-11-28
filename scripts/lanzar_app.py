"""Inicia VistoBueno y abre la SPA en el navegador.

Pensado para el acceso directo de Windows: corre dentro de WSL, levanta
la API en loopback y abre el navegador de Windows cuando el servidor
responde. El build del frontend debe existir en ``frontend/dist``.

Uso:
    python3 scripts/lanzar_app.py --abrir-windows
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
LOCAL_SIGNATURE = REPO_ROOT / "recursos" / "firma.txt"
PROC_VERSION = Path("/proc/sys/kernel/osrelease")
WAIT_TIMEOUT = 30.0


def is_wsl() -> bool:
    """True si el proceso corre dentro de WSL."""
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    try:
        return "microsoft" in PROC_VERSION.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def browser_command(url: str, *, windows: bool) -> list[str] | None:
    """Comando para abrir el navegador de Windows; None usa webbrowser."""
    if not windows:
        return None
    return ["cmd.exe", "/c", "start", "", url]


def open_browser(url: str, *, windows: bool) -> None:
    command = browser_command(url, windows=windows)
    if command is not None and shutil.which(command[0]) is not None:
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    webbrowser.open(url)


def wait_for_server(url: str, timeout: float = WAIT_TIMEOUT) -> bool:
    """Espera a que la URL responda; True si respondió dentro del plazo."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def build_available(dist_dir: Path | None = None) -> bool:
    """True si frontend/dist/index.html existe."""
    if dist_dir is None:
        dist_dir = FRONTEND_DIST
    return (dist_dir / "index.html").is_file()


def load_local_signature(path: Path) -> None:
    """Usa la primera línea de la firma guardada si el entorno no la define."""
    if os.environ.get("VISTOBUENO_FIRMA", "").strip():
        return
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        return
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        os.environ["VISTOBUENO_FIRMA"] = lines[0]


def _open_when_ready(url: str, *, windows: bool) -> None:
    if wait_for_server(f"{url}docs"):
        open_browser(url, windows=windows)
    else:
        print(f"La API no respondió en {WAIT_TIMEOUT:.0f} s. Abre {url} a mano.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inicia la API y abre la SPA de VistoBueno en el navegador."
    )
    parser.add_argument("--puerto", type=int, default=8000, help="puerto local (default: 8000)")
    parser.add_argument(
        "--abrir-windows",
        action="store_true",
        help="abre el navegador de Windows con cmd.exe (modo WSL)",
    )
    parser.add_argument(
        "--sin-navegador",
        action="store_true",
        help="inicia la API sin abrir el navegador",
    )
    args = parser.parse_args(argv)

    if not build_available():
        print("No se encontró frontend/dist/index.html.")
        print("Construye la pantalla según docs/INSTALACION.md (§3.4 o §4.3).")
        return 1

    try:
        load_local_signature(LOCAL_SIGNATURE)
    except OSError, UnicodeDecodeError:
        print("No se pudo leer recursos/firma.txt. Revisa el archivo y guárdalo como UTF-8.")
        return 1

    # El script vive en scripts/: agrega la raíz para que uvicorn importe
    # validator.api aunque se ejecute desde otra carpeta.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    url = f"http://127.0.0.1:{args.puerto}/"
    if not args.sin_navegador:
        threading.Thread(
            target=_open_when_ready,
            args=(url,),
            kwargs={"windows": args.abrir_windows},
            daemon=True,
        ).start()

    import uvicorn

    print(f"VistoBueno en {url}")
    print("Ctrl+C para detener.")
    config = uvicorn.Config(
        "validator.api:app",
        host="127.0.0.1",
        port=args.puerto,
        proxy_headers=False,
        log_level="info",
    )
    uvicorn.Server(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
