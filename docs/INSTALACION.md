# Instalación y puesta en marcha — VistoBueno

Guía para dejar el proyecto operativo en una máquina nueva. Cubre Linux,
macOS y Windows 10/11.

> **Camino soportado**: Nix con `flake.nix`. En Windows, Nix no corre de
> forma nativa: se usa WSL2. El camino nativo de Windows (§4) sirve para
> levantar la API y la SPA, pero no reproduce la suite ni el CI.

```text
Windows 10/11
├─ WSL2 (soportado)   → Ubuntu → Nix → nix develop → suite + API + SPA
└─ Nativo (fallback)  → Python 3.14 + Node → API + SPA (sin suite/CI)
```

Caption: dos caminos para Windows; solo WSL2 mantiene paridad con CI.

## 1. Requisitos

| Requisito | Valor |
|---|---|
| Sistema operativo | Linux x86_64/aarch64, macOS, o Windows 10/11 con WSL2 |
| Disco libre | 10 GB (store de Nix + dependencias) |
| Memoria | 4 GB mínimo; 8 GB recomendado |
| Red | Primera compilación: descarga de 1–2 GB |
| Git | 2.30 o superior |
| Python | 3.14 o superior (lo fija el flake) |
| Node.js | LTS (lo fija el flake) |

El flake fija Python 3.14 y Node LTS. No instales esas versiones a mano en
el camino soportado.

`recursos/` no está versionado. Sin esa carpeta, tres pruebas se omiten y
la constancia usa la plantilla sintética. `frontend/dist` tampoco está
versionado: sin el build del frontend se omite una prueba más, la que
comprueba que la API sirve la SPA. En un clon limpio se omiten cuatro
pruebas. Es el comportamiento esperado en un clon limpio y en CI.

## 2. Linux y macOS (camino soportado)

### 2.1 Instalar Nix

```bash
bash <(curl -L https://nixos.org/nix/install) --daemon
```

Cierra y abre la terminal. Después habilita flakes:

```bash
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
```

Verifica:

```bash
nix --version
nix flake --help >/dev/null
```

### 2.2 Clonar y entrar al entorno

```bash
git clone https://github.com/retblast/vistobueno.git
cd vistobueno
nix develop
```

La primera vez descarga y compila dependencias. Las siguientes entradas son
instantáneas.

### 2.3 Verificar la instalación

```bash
nix run .#test -- tests/ -q
```

Resultado esperado: **la suite termina en verde**. El conteo exacto depende
de las carpetas locales `recursos/` y `frontend/dist`; los tests que las
necesitan se marcan como `skipped` cuando faltan, y eso **no es un fallo de
la instalación**. Referencia medida en un clon sin esas carpetas:
`857 passed, 4 skipped` (sin `xfail`).

Levanta la API:

```bash
nix run .#serve -- validator.api:app --reload
```

Abre `http://127.0.0.1:8000/docs`. La app escucha solo en loopback y
arranca con `--no-proxy-headers`.

Frontend, en otra terminal:

```bash
cd frontend
npm ci
npm run dev
```

Abre `http://localhost:5173`. El proxy de Vite manda `/validar`,
`/ficha-pendiente`, `/deposito`, `/constancia` y `/fila-registro` a la API
del puerto 8000.

Build y tests del frontend:

```bash
npm run build
npm test
```

### 2.4 Verificación completa

```bash
nix flake check
nix develop --command ruff format --check validator/ scripts/ tests/
nix develop --command python3 scripts/generate_openapi.py --check
```

El ensayo general del flujo de depósito, en un comando:

```bash
nix run .#test-ficha-deposito
```

Salida esperada: `✅ FLUJO COMPLETO OK`.

## 3. Windows 10/11 (camino soportado: WSL2)

Nix necesita un kernel Linux. WSL2 lo provee. El navegador, Tampermonkey y
el archivo de hosts siguen del lado de Windows.

### 3.1 Instalar WSL2 y Ubuntu

En PowerShell **como administrador**:

```powershell
wsl --install -d Ubuntu
```

Reinicia si el instalador lo pide. Después:

```powershell
wsl --update
wsl --set-default-version 2
wsl -l -v
```

`wsl -l -v` debe mostrar `VERSION 2`. Si ya tenías WSL, alcanza con
`wsl --install -d Ubuntu` y `wsl --update`.

### 3.2 Instalar Nix dentro de Ubuntu

Abre Ubuntu desde el menú Inicio (o `wsl` en PowerShell) y ejecuta:

```bash
sudo apt update
sudo apt install -y curl xz-utils git
bash <(curl -L https://nixos.org/nix/install) --no-daemon
```

Cierra y abre la terminal de Ubuntu, o carga el perfil:

```bash
. ~/.nix-profile/etc/profile.d/nix.sh
```

Habilita flakes:

```bash
mkdir -p ~/.config/nix
echo 'experimental-features = nix-command flakes' >> ~/.config/nix/nix.conf
nix --version
```

`--no-daemon` evita depender de systemd. Si tu WSL tiene systemd habilitado
y prefieres el modo multi-usuario, usa `--daemon`.

### 3.3 Clonar dentro del sistema de archivos de Linux

```bash
cd ~
git clone https://github.com/retblast/vistobueno.git
cd vistobueno
```

No trabajes desde `/mnt/c/...`: es lento y puede romper permisos. Si el
repo ya está en `C:`, cópialo:

```bash
cp -r /mnt/c/Users/<usuario>/ruta/vistobueno ~/vistobueno
```

### 3.4 Verificar

```bash
nix develop
nix run .#test -- tests/ -q
```

Esperado: ver la tabla de conteos de la sección 2.3. En un clon limpio
sin `recursos/` ni `frontend/dist`: `745 passed, 4 skipped, 6 xfailed`.

### 3.5 Levantar la API y la SPA

```bash
nix run .#serve -- validator.api:app --reload
```

Si ya construiste `frontend/dist`, la API sirve la SPA en
`http://localhost:8000/`; el servidor de Vite solo hace falta para
desarrollo con recarga.

En otra terminal de Ubuntu:

```bash
cd ~/vistobueno/frontend
npm ci
VITE_DEV_OPEN=false npm run dev
```

Desde el navegador de Windows:

- API: `http://localhost:8000/docs`
- SPA: `http://localhost:5173`

WSL2 redirige `localhost` de Windows al servicio de la VM.
`VITE_DEV_OPEN=false` evita que Vite intente abrir un navegador dentro de
Linux.

Si `localhost` no responde: `wsl --shutdown`, vuelve a abrir Ubuntu y
reintenta. Confirma que `wsl -l -v` muestra `VERSION 2`.

> **Seguridad**: no uses `VISTOBUENO_HOST=0.0.0.0` para "arreglar" el
> acceso. La API maneja datos personales y por diseño escucha solo en
> loopback. Usa `localhost`, no la IP de la VM. Si un pedido llega como peer
> remoto, la API responde `403`; la solución es el camino nativo de §4 o el
> token (solo para la SPA), no abrir el puerto.

### 3.6 Userscript y descargas

- Instala Tampermonkey en el navegador de Windows.
- Instala `tools/dspace-fill/dist/vistobueno-dspace-fill.user.js`
  (Tampermonkey → panel → importar).
- El script declara `@connect localhost` y usa `http://localhost:8000`;
  llega a la API por el forwarding de WSL.
- Las descargas de constancias y del registro caen en la carpeta de
  descargas de Windows.
- La plantilla oficial de la constancia no está versionada. Copia el Modelo
  B a `recursos/TESIS DIGITAL MODELO B-2026.docx` (ruta por defecto) o
  define `VISTOBUENO_PLANTILLA_CONSTANCIA` con la ruta absoluta. Define
  `VISTOBUENO_FIRMA` para la columna FIRMA del registro.

### 3.7 Acceso directo en Windows

El acceso directo abre la SPA sin escribir comandos. Usa el navegador de
Windows, pero la API y Nix siguen dentro de WSL.

1. Construye la SPA una vez:

   ```bash
   cd ~/vistobueno
   nix develop --command bash -lc 'cd frontend && npm ci && npm run build'
   ```

2. Copia `tools/launcher/` a una carpeta local de Windows, por ejemplo
   `C:\VistoBueno\`. El `.bat` sigue apuntando al repositorio en WSL.

   ```bash
   mkdir -p /mnt/c/VistoBueno
   cp -r ~/vistobueno/tools/launcher/. /mnt/c/VistoBueno/
   ```

3. En PowerShell, crea el acceso directo:

   ```powershell
   cd C:\VistoBueno
   powershell -ExecutionPolicy Bypass -File .\crear_acceso_directo.ps1
   ```

4. Abre el acceso directo **VistoBueno** del escritorio. Se inicia la API
   en `http://127.0.0.1:8000/` y el navegador abre la SPA.

5. Para detenerlo, cierra la ventana de consola o pulsa `Ctrl+C`.

`VistoBueno.bat` usa la distro por defecto de WSL y espera el repositorio
en `~/vistobueno`. Si el repositorio está en otra ruta, edita el `cd` del
`.bat`. Si usas una distro concreta, cambia `wsl.exe --` por
`wsl.exe -d <distro> --`.

El ícono `vistobueno.ico` se genera con
`python3 scripts/generar_icono.py` a partir del trazo de
`frontend/public/favicon.svg`.

Si reconstruyes la SPA, cierra y vuelve a abrir el acceso directo para
que la API cargue el build nuevo.

### 3.8 Límites de WSL2

- `recursos/` es local; no se versiona.
- Los puertos 8000 y 5173 no se exponen a la LAN.
- Si usas VPN o modo mirrored, verifica que `localhost` siga funcionando.

## 4. Windows nativo (fallback para la API)

Este camino sirve para levantar la API y la SPA en la misma máquina
Windows, sin WSL. No reproduce `nix flake check`, los scripts bash ni el
CI. Para desarrollo y verificación, usa §3.

> **Aviso**: este camino no es reproducible. El proyecto fija las
> dependencias en `flake.nix`; `pip` puede resolver versiones distintas.
> Úsalo solo para la API/SPA en la misma máquina.

### 4.1 Requisitos

- Python 3.14 desde python.org (marca "Add python.exe to PATH").
- Node.js LTS desde nodejs.org.

Verifica en PowerShell:

```powershell
py -3.14 --version
node --version
npm --version
```

### 4.2 Entorno virtual y dependencias

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pydantic email-validator pyyaml python-docx openpyxl lxml python-multipart
```

Si PowerShell bloquea el script de activación:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Dependencias opcionales:

```powershell
# tests y sink SMTP
pip install pytest httpx pytest-cov coverage aiosmtpd

# exportación a PDF (requiere GTK3, ver §4.4)
pip install markdown weasyprint

# OCR y lectura de PDF (opcional)
pip install pymupdf pytesseract pillow
```

### 4.3 Arrancar

```powershell
python -m validator.api
```

Abre `http://127.0.0.1:8000/docs`. El módulo arranca uvicorn con
`proxy_headers=False` y bind a `127.0.0.1`. La alternativa es:

```powershell
uvicorn validator.api:app --no-proxy-headers
```

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

### 4.4 PDF en Windows (opcional)

WeasyPrint necesita Pango. Instala el runtime GTK3 para Windows (por
ejemplo, MSYS2 UCRT64 + `mingw-w64-ucrt-x86_64-pango`) y apunta la
variable:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = "C:\msys64\ucrt64\bin"
```

Sin eso, `--formato pdf` falla. Markdown y JSON funcionan igual.

### 4.5 Límites

- `nix run .#test`, `.#serve`, `.#test-ficha-deposito` y `nix flake check`
  no existen.
- Los scripts `scripts/*.sh` necesitan Git Bash o WSL.
- OCR (`ocrmypdf`, `tesseract`) requiere instalación aparte.
- La suite puede diferir de CI por dependencias nativas.

## 5. Checklist de puesta en marcha

Usa esta lista para el hito de instalación de la actividad 4.

- [ ] `nix develop` entra sin errores (o el venv nativo arranca).
- [ ] `cd frontend && npm ci && npm run build && npm test` → build y tests
      en verde. Esto deja `frontend/dist`, que la suite usa.
- [ ] `nix run .#test -- tests/ -q` → `749 passed, 6 xfailed` con
      `recursos/` y `frontend/dist`; sin `recursos/`: `746 passed,
      3 skipped, 6 xfailed`. Ver la tabla de la sección 2.3.
- [ ] `nix run .#serve -- validator.api:app` → `/docs` responde `200` en
      `127.0.0.1:8000`.
- [ ] `Host: atacante.example` → `400`.
- [ ] `docs/ejemplos/doc_bueno.docx` → verde; `doc_malo.docx` → rojo
      (4 errores, 1 warning).
- [ ] `nix run .#test-ficha-deposito` → `✅ FLUJO COMPLETO OK` (opcional).
- [ ] Anotar versiones: `nix --version`, `python3 --version`,
      `node --version`, `git rev-parse --short HEAD`.

## 6. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `experimental Nix feature 'flakes' is disabled` | Falta la config | Agregar `experimental-features = nix-command flakes` a `~/.config/nix/nix.conf` |
| `error: getting status of '/nix/store/...'` | Entorno incompleto | Volver a `nix develop` |
| `python3: command not found` | Se ejecutó fuera del entorno | Entrar con `nix develop` o usar `nix develop --command python3 ...` |
| `Address already in use` | Otro proceso en el puerto | Cerrar el proceso o cambiar el puerto (`--port` en uvicorn, `--puerto` en el lanzador) |
| `400` por `Host` | `Host` ajeno (por ejemplo, la IP de WSL) | Usar `localhost` o `127.0.0.1`; si es un dominio propio, agregarlo a `VISTOBUENO_HOSTS` |
| `403` desde el navegador en WSL | El peer no se ve como loopback | Usar `localhost` (no la IP de WSL) y verificar el forwarding; si persiste, usar §4 |
| `xfail` en la suite | Criterios abiertos de Int3 | Es esperado; no tocar |
| `skipped` en la suite | Faltan `recursos/` y/o `frontend/dist` | Es esperado; ver la tabla de conteos de la sección 2.3 |
| El acceso directo no abre la SPA | Falta `frontend/dist/index.html` | Construir la SPA (ver §3.7) |
| El acceso directo no inicia | La distro por defecto no tiene Nix o el repo no está en `~/vistobueno` | Revisar el `cd` y la distro de `VistoBueno.bat` |
| PDF falla en Windows | Falta Pango/GTK3 | Ver §4.4 |
| PDF falla en Linux/macOS | Falta Pango en el sistema | Usar Nix (`nix develop`) o instalar Pango |

## 7. Referencias

- `README.md` — comandos y estado del proyecto.
- `docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md` — checklist de seguridad y
  despliegue en la PC del operador.
- `docs/PILOTO_OPERADOR.md` — kit del piloto y checklist de 11 pasos.
- `docs/CONTRATO_API.md` — contrato de la API.
- `AGENTS.md` — convenciones de trabajo.
