#!/usr/bin/env python3
"""Verificador de filtración de credenciales (capa 2 y 3).

Bloquea cualquier asignación con valor REAL de las credenciales del
proyecto (SMTP, DSpace y el token del buzón) y cualquier archivo .env /
.env.* presente en el árbol. Se usa en dos capas:

- Hook de pre-commit (``.pre-commit-config.yaml``): recibe los archivos
  staged como argumentos y falla el commit si detecta una violación.
- CI (``.github/workflows/ci.yml``): se ejecuta con ``--all`` sobre todo el
  árbol de trabajo, cubriendo el caso ``git commit --no-verify``.

Valores permitidos (placeholders documentales/dummy): ``dummy``, ``prueba``,
``test``, ``changeme``, ``<valor>``, los valores entre ángulos
(``<mi-token>``), los que terminan en ``-de-prueba`` (convención de los
tests del repo) y las referencias al entorno (``$VAR``, ``${VAR}``,
``os.environ.get(...)``).

El propio verificador y sus tests están excluidos: contienen el patrón
deliberadamente (para probarlo) pero nunca un valor real.

Cobertura (auditoría 2026-10-26, AUD-22)
----------------------------------------

El verificador marca **cuatro** clases de filtración:

1. **Asignación de una variable del proyecto** con valor real
   (``VISTOBUENO_SMTP_PASSWORD``, ``VISTOBUENO_DSPACE_USER``,
   ``VISTOBUENO_DSPACE_PASSWORD``, ``VISTOBUENO_API_TOKEN``).
2. **Asignación genérica**: una variable en MAYÚSCULAS cuyo nombre
   **termina** en una palabra que denota un secreto (``PASSWORD``,
   ``PASSWD``, ``SECRET``, ``TOKEN``, ``API_KEY``, ``ACCESS_KEY``,
   ``PRIVATE_KEY``, ``CREDENTIAL``/``CREDENTIALS``). Ejemplos:
   ``DB_PASSWORD=...``, ``GITHUB_TOKEN=...``, ``AWS_SECRET_ACCESS_KEY=...``.
3. **URL con credenciales embebidas**: ``https://usuario:clave@host``.
4. **Bloque YAML multilínea**: ``clave: |`` o ``clave: >`` seguido de un
   valor real (se lee **todas** las líneas del bloque indentado, no solo
   la primera: un placeholder arriba y el secreto abajo también se
   detectan).

Límites conocidos (declarados a propósito):

- Solo se revisan **nombres en mayúsculas**: una clave de Python o de
  JavaScript en minúsculas (``password="..."``) no se marca. Es una
  decisión: los secretos reales del proyecto se configuran por variable
  de entorno, y revisar minúsculas produciría falsos positivos en cada
  test y docstring del repo.
- No se revisan **archivos binarios**: se leen con ``errors="replace"``
  y solo se busca texto.
- No se detectan secretos **partidos** o codificados (base64, cifrado).
- Los archivos ``.env``/``.env.*`` están bloqueados por su nombre, así
  que su contenido no necesita analizarse en detalle.

Uso:
    python3 scripts/verificar_secretos.py ARCHIVO...   # modo pre-commit
    python3 scripts/verificar_secretos.py --all        # modo CI/árbol completo

Salida:
    0 = sin violaciones; 1 = violación detectada (con detalle en stdout).
"""

import re
import sys
from pathlib import Path

# Credenciales cubiertas: la contraseña y el usuario SMTP (Actividad 6),
# el usuario y la contraseña de la cuenta de servicio de DSpace
# (Actividad 10, ver docs/DSPACE_API.md §8) y el token compartido del
# buzón (opcional, `VISTOBUENO_API_TOKEN`). El resto de variables son
# configuración no sensible (hosts, puertos, UUIDs de colección).
NOMBRES_SECRETOS = (
    "VISTOBUENO_SMTP_PASSWORD",
    "VISTOBUENO_SMTP_USER",
    "VISTOBUENO_DSPACE_PASSWORD",
    "VISTOBUENO_DSPACE_USER",
    "VISTOBUENO_API_TOKEN",
)

# Sufijos que delatan un secreto en el nombre de una variable.
SUFIJOS_SECRETOS = (
    "PASSWD",
    "PASSWORD",
    "SECRET_KEY",
    "ENCRYPTION_KEY",
    "SECRET",
    "TOKEN",
    "API_KEY",
    "APIKEY",
    "ACCESS_KEY",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "CREDENTIALS",
)

# Asignación del secret con un valor no vacío: VAR=valor, VAR: valor.
# El grupo 1 captura el nombre (para el mensaje) y el 2 el valor.
# La alternativa genérica exige que el nombre TERMINE en un sufijo
# secreto: así `CABECERA_TOKEN_BUZON` (un nombre de header) no se marca.
_NOMBRE_EXPLICITO = "|".join(NOMBRES_SECRETOS)
_NOMBRE_GENERICO = (
    r"(?<![A-Z0-9_])(?:[A-Z][A-Z0-9]*_)*(?:" + "|".join(SUFIJOS_SECRETOS) + r")(?![A-Z0-9_])"
)
PATRON_ASIGNACION = re.compile(
    rf"({_NOMBRE_EXPLICITO}|{_NOMBRE_GENERICO})\s*[=:]\s*(\S+)",
)

# URL con credenciales embebidas: https://usuario:clave@host
PATRON_URL_CREDENCIALES = re.compile(r"://[^\s:/@]+:[^\s/@]+@")

# Valores que NO son secretos reales (placeholders de docs/tests/scripts).
PLACEHOLDERS = {"dummy", "prueba", "test", "changeme", "<valor>"}

# Prefijos de referencia al entorno: no son un valor, son una lectura.
PREFIXOS_REFERENCIA = ("os.environ", "os.getenv", "getenv(", "environ[")

# Archivos que contienen el patrón deliberadamente (el verificador y sus
# tests); comparación por ruta relativa POSIX desde la raíz del repo.
EXCLUIDOS = {
    "scripts/verificar_secretos.py",
    "tests/test_verificar_secretos.py",
}

# Directorios nunca escaneados en modo --all: cachés, dependencias
# instaladas y materiales de referencia que no se versionan.
DIRS_EXCLUIDOS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "recursos",
    "result",
}

MSG_VIOLACION = (
    "VIOLACIÓN: {ruta}:{linea}: asignación de {var} con valor real "
    "(use una variable de entorno del proceso, nunca un archivo)"
)
MSG_URL = (
    "VIOLACIÓN: {ruta}:{linea}: URL con credenciales embebidas "
    "(use una variable de entorno del proceso, nunca una URL con clave)"
)
MSG_ENV = (
    "VIOLACIÓN: {ruta}: archivo .env en el repo "
    "(la configuración vive en el entorno, no en archivos)"
)


def _valor_permitido(valor: str) -> bool:
    """True si el valor capturado es placeholder o autorreferencia ($VAR)."""
    limpio = valor.strip().strip("\"'")
    if not limpio:
        return True
    if limpio.startswith("$"):
        # Autorreferencia de variable de entorno (${VAR}, $VAR)
        return True
    if limpio.startswith("<") and limpio.endswith(">"):
        # Placeholders entre ángulos (<valor>, <mi-token>)
        return True
    if limpio.startswith(PREFIXOS_REFERENCIA):
        # Lectura del entorno, no un valor: os.environ.get("X", "")
        return True
    if limpio.lower().endswith("-de-prueba"):
        # Convención de los tests del repo: "secreto-de-prueba" no es un
        # secreto real y no obliga a excluir el archivo del escaneo.
        return True
    return limpio.lower() in PLACEHOLDERS


def _es_archivo_env(ruta: Path) -> bool:
    """True para archivos .env o .env.<algo> excepto .env.example.

    ``.env.example`` es una plantilla documental inerte (convención Vite, ver
    ``frontend/.env.example``) y no la carga ninguna herramienta: se permite
    como archivo, pero su CONTENIDO se escanea igual que cualquier otro.
    """
    if ruta.name == ".env.example":
        return False
    return ruta.name == ".env" or ruta.name.startswith(".env.")


def _lineas_bloque_yaml(lineas: list[str], indice: int, sangria: int) -> list[str]:
    """Líneas con contenido del bloque YAML que sigue a una clave con `|` o `>`.

    Devuelve **todas** las líneas del bloque (no solo la primera): un
    bloque puede poner el placeholder arriba y el valor real abajo.
    """
    bloque: list[str] = []
    for linea in lineas[indice + 1 :]:
        if not linea.strip():
            continue
        sangria_linea = len(linea) - len(linea.lstrip())
        if sangria_linea <= sangria:
            # Salió del bloque: la clave no tiene valor multilínea.
            break
        bloque.append(linea.strip())
    return bloque


def verificar_archivo(ruta: Path) -> list[str]:
    """Devuelve la lista de violaciones (mensajes) encontradas en un archivo.

    Un archivo .env/.env.* es violación por sí mismo, sin importar su
    contenido (cubre el caso de credenciales en formato libre).
    """
    if _es_archivo_env(ruta):
        return [MSG_ENV.format(ruta=ruta)]

    violaciones: list[str] = []
    try:
        texto = ruta.read_text(encoding="utf-8", errors="replace")
    except OSError, UnicodeDecodeError:
        # Legibilidad ante archivos raros: no se puede verificar y no se
        # bloquea; la capa de asignaciones es la protección principal.
        return violaciones

    lineas = texto.splitlines()
    for n, linea in enumerate(lineas, start=1):
        m = PATRON_ASIGNACION.search(linea)
        if m:
            valor = m.group(2)
            if valor.strip("\"'") in ("|", ">"):
                # Bloque YAML multilínea: el valor está en las líneas
                # indentadas que siguen. Se revisan todas: si una sola
                # no es un placeholder, el bloque es un secreto real.
                sangria = len(linea) - len(linea.lstrip())
                bloque = _lineas_bloque_yaml(lineas, n - 1, sangria)
                if any(not _valor_permitido(v) for v in bloque):
                    violaciones.append(MSG_VIOLACION.format(ruta=ruta, linea=n, var=m.group(1)))
            elif not _valor_permitido(valor):
                # No se imprime el valor: nunca repetir un posible secreto en logs.
                violaciones.append(MSG_VIOLACION.format(ruta=ruta, linea=n, var=m.group(1)))
        if PATRON_URL_CREDENCIALES.search(linea):
            violaciones.append(MSG_URL.format(ruta=ruta, linea=n))
    return violaciones


def verificar_arbol(raiz: Path) -> list[str]:
    """Escanea recursivamente el árbol (modo --all), respetando exclusiones."""
    violaciones: list[str] = []
    for ruta in sorted(raiz.rglob("*")):
        if not ruta.is_file():
            continue
        partes = set(ruta.relative_to(raiz).parts)
        if partes & DIRS_EXCLUIDOS:
            continue
        rel = ruta.relative_to(raiz).as_posix()
        if rel in EXCLUIDOS:
            continue
        violaciones.extend(verificar_archivo(ruta))
    return violaciones


def main(argv: list[str]) -> int:
    if "--all" in argv:
        raiz = Path.cwd()
        violaciones = verificar_arbol(raiz)
    else:
        archivos = [a for a in argv if not a.startswith("-")]
        if not archivos:
            print("Uso: verificar_secretos.py ARCHIVO... | --all", file=sys.stderr)
            return 2
        violaciones = []
        for a in archivos:
            violaciones.extend(verificar_archivo(Path(a)))

    if violaciones:
        for v in violaciones:
            print(v)
        print(
            f"\n{len(violaciones)} violación(es). "
            "Configure el secret como variable de entorno del proceso; "
            "nunca como texto en el repo.",
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
