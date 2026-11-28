@echo off
setlocal

rem Inicia VistoBueno desde WSL. Requisitos:
rem - Ubuntu en WSL2 con Nix instalado.
rem - El repositorio en ~/vistobueno.
rem Si el repositorio queda en otra ruta, cambia el cd de la linea de abajo.
rem Si la distro no se llama "Ubuntu", cambia el valor de DISTRO por el
rem nombre exacto que muestra `wsl -l -v` (por ejemplo, Ubuntu-24.04).
set "DISTRO=Ubuntu"

wsl.exe -d %DISTRO% -- bash -lc "if ! command -v nix >/dev/null 2>&1; then . ~/.nix-profile/etc/profile.d/nix.sh || exit 1; fi; cd ~/vistobueno && nix --extra-experimental-features 'nix-command flakes' develop --command python3 scripts/lanzar_app.py --abrir-windows"

if errorlevel 1 (
  echo.
  echo VistoBueno no pudo iniciarse. Revisa el mensaje de arriba.
  pause
)
