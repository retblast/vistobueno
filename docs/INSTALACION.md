# Instalación y puesta en marcha — VistoBueno

Para la biblioteca, usa [Windows 11 con Ubuntu en WSL2](#3-windows-11-con-ubuntu-en-wsl2).
Si el equipo ya está instalado, empieza por [uso diario](#uso-diario-para-el-operador).
Las demás secciones son para el responsable técnico.

> **Camino soportado**: Nix con `flake.nix`. En Windows, Nix no corre de
> forma nativa: se usa WSL2. El camino nativo de Windows (§4) sirve para
> levantar la API y la SPA, pero no reproduce la suite ni el CI.

```text
Windows 11
├─ WSL2 (soportado)   → Ubuntu → Nix → nix develop → suite + API + SPA
└─ Nativo (fallback)  → Python 3.14 + Node → API + SPA (sin suite/CI)
```

La rama superior muestra la instalación recomendada para la biblioteca.

## 1. Requisitos

| Requisito | Valor |
|---|---|
| Sistema operativo | Linux x86_64/aarch64, macOS, o Windows 11 con WSL2 |
| Disco libre | 10 GB (store de Nix + dependencias) |
| Memoria | 4 GB mínimo; 8 GB recomendado |
| Red | Primera compilación: descarga de 1–2 GB |
| Git | 2.30 o superior |
| Python | 3.14 o superior (lo fija el flake) |
| Node.js | LTS (lo fija el flake) |

El flake fija Python 3.14 y Node LTS. No instales esas versiones a mano en
el camino soportado.

`recursos/` queda fuera de Git. La constancia requiere la plantilla oficial
Modelo B que ya tiene la biblioteca. `frontend/dist` se genera al construir
la pantalla. Algunas pruebas técnicas se omiten si faltan esos archivos.

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

La suite debe terminar sin fallos. Algunas pruebas se omiten
(`skipped`) si faltan archivos locales de `recursos/` o `frontend/dist`.
Construye el frontend para incluir las pruebas que usan esos archivos.

Levanta la API:

```bash
nix run .#serve -- validator.api:app --reload
```

Abre `http://127.0.0.1:8000/docs`. La app escucha solo en loopback y
arranca con `--no-proxy-headers`.

Para probar el frontend en desarrollo, abre otra terminal en la raíz
del proyecto:

```bash
nix develop
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

## 3. Windows 11 con Ubuntu en WSL2

Esta es la instalación recomendada para la biblioteca. WSL2 permite
ejecutar Ubuntu dentro de Windows. El navegador, Word y las descargas
siguen en Windows.

### Uso diario para el operador

1. Haz doble clic en **VistoBueno** en el escritorio. Deja abierta la ventana
   negra mientras trabajas.
2. Espera a que aparezca la pantalla de carga en el navegador. Si el
   navegador no se abre, escribe `http://localhost:8000/` en la barra de
   direcciones. Si la pantalla de carga no aparece, copia el mensaje de
   la ventana negra y avisa al responsable de la instalación.
3. Sube el DOCX. Si vas a depositarlo, revisa los datos de la ficha antes de
   continuar. Usa tu sesión habitual del repositorio de la UNT.
4. Termina los trámites abiertos antes de cerrar VistoBueno. Al detenerlo
   se pierde la ficha que espera confirmación. Vuelve a la ventana negra,
   pulsa **Ctrl+C** y confirma el cierre si Windows lo pide.

### 3.1 Instalar Ubuntu

Los pasos 3.1 a 3.8 son para el responsable de la instalación. Haz la
configuración en la misma cuenta de Windows con la que se usará VistoBueno.
Si el equipo pide credenciales de otra cuenta de administrador, coordina
con TI la habilitación de WSL y comprueba que Ubuntu quede disponible
para la cuenta del operador.

En Windows, busca **PowerShell** en Inicio. Haz clic derecho y elige
**Ejecutar como administrador**. Si Ubuntu aún no está instalado, ejecuta:

```powershell
wsl --install -d Ubuntu
```

Reinicia Windows si se solicita. Abre **Ubuntu** desde Inicio. En el primer
arranque, crea un usuario y una contraseña de Ubuntu. La contraseña no se
muestra al escribir. Guárdala para los comandos que empiezan con `sudo`.

En **PowerShell**, ejecuta:

```powershell
wsl -l -v
```

La fila **Ubuntu** debe mostrar **2** en la columna **VERSION**. Si muestra
**1**, TI puede convertir esa instalación con `wsl --set-version Ubuntu 2`.
Si Ubuntu contiene trabajo previo, haz una copia antes de convertirlo.
Anota el nombre exacto de la distro. El acceso directo usa `Ubuntu`; si la
fila muestra otro nombre (por ejemplo, `Ubuntu-24.04`), cambia el valor de
`DISTRO` en `VistoBueno.bat` por ese nombre.
[Guía oficial de WSL](https://learn.microsoft.com/es-es/windows/wsl/install)

### 3.2 Instalar Nix

En **Ubuntu**, ejecuta los comandos de este bloque. Si `sudo` pide una
contraseña, usa la de Ubuntu. Si Nix ya está instalado, pasa a la
verificación.

```bash
sudo apt update
sudo apt install -y curl xz-utils git
bash <(curl -fL https://nixos.org/nix/install) --no-daemon
```

Cierra y vuelve a abrir **Ubuntu**. Ejecuta:

```bash
nix --version
```

Debes ver una línea que indique la versión. Si no aparece, carga el perfil
con `. ~/.nix-profile/etc/profile.d/nix.sh` y vuelve a comprobar. Si el comando aún falla, conserva el mensaje y revisa la instalación de Nix. [Instalación oficial de Nix](https://nix.dev/manual/nix/latest/installation/installing-binary)

### 3.3 Obtener el proyecto

En **Ubuntu**, para una instalación nueva, copia y ejecuta el bloque:

```bash
cd ~
git clone https://github.com/retblast/vistobueno.git
cd ~/vistobueno
git rev-parse --short HEAD
```

Registra el identificador que imprime el último comando. El responsable
de la entrega debe comprobar que corresponde a la versión aprobada por el
equipo. Si ya existe una instalación, conserva sus archivos locales y
coordina la actualización antes de seguir. Mantén el proyecto dentro de
Ubuntu para usar el sistema de archivos de WSL.
[Archivos compartidos entre Ubuntu y Windows](https://learn.microsoft.com/es-es/windows/wsl/filesystems)

### 3.4 Construir la pantalla de carga

En **Ubuntu**, desde la carpeta indicada:

```bash
cd ~/vistobueno
nix --extra-experimental-features 'nix-command flakes' develop --command bash -c 'cd frontend && npm ci && npm run build'
```

La primera vez descarga dependencias. Espera a que termine. Debes ver un
mensaje con el texto `built in`. Si aparece un error de descarga o
compilación, conserva el mensaje completo y resuélvelo antes de continuar.
Repite este paso cuando instales una nueva versión del proyecto.

### 3.5 Preparar la constancia y el registro

Modelo B es la plantilla oficial que ya tiene el operador de la biblioteca.
Usa esa copia o la que confirme la biblioteca. La carpeta `recursos/` no se
versiona: una clonación nueva no trae la plantilla.

En **Ubuntu**, abre la carpeta local de la instalación en el Explorador de
archivos:

```bash
cd ~/vistobueno
mkdir -p recursos
(cd recursos && explorer.exe .)
```

En esa carpeta abierta en **Windows**:

1. Copia la plantilla y comprueba que el nombre completo sea
   `TESIS DIGITAL MODELO B-2026.docx`. La plantilla original puede
   quedarse en su ubicación habitual.
2. En **Bloc de notas**, escribe en una sola línea el nombre que debe
   aparecer en la columna **FIRMA** del registro. Guarda el archivo
   como `firma.txt` en la misma carpeta, con codificación **UTF-8**.
   Para confirmar el nombre completo, activa **Ver → Mostrar →
   Extensiones de nombre de archivo** en el Explorador.

El lanzador lee `recursos/firma.txt` cada vez que se abre. Una configuración
ya establecida en `VISTOBUENO_FIRMA` tiene prioridad. Para esta instalación
basta con el archivo. Si TI configura otra ubicación para Modelo B, puede
usar `VISTOBUENO_PLANTILLA_CONSTANCIA` en el entorno que inicia la API.

### 3.6 Instalar el complemento de DSpace

1. En el navegador de **Windows**, instala **Tampermonkey** desde
   [su sitio oficial](https://www.tampermonkey.net/). Usa el perfil de
   navegador con el que el operador entra al repositorio de la UNT.
2. En **Ubuntu**, abre la carpeta del archivo aprobado:

   ```bash
   cd ~/vistobueno/tools/dspace-fill/dist
   explorer.exe .
   ```

   En el Explorador copia `vistobueno-dspace-fill.user.js` a **Descargas**.
   En Windows, abre el **Panel de control** de Tampermonkey y usa
   **Utilidades → Importar desde archivo** para instalarlo. Comprueba
   que haya una sola copia activa del script de VistoBueno y que su versión
   coincida con la indicada por el responsable de la entrega.
3. Comprueba que el navegador permita ejecutar scripts de usuario. Si el
   permiso está bloqueado en Chrome o Edge institucional, pide a TI que lo
   revise. La prueba del botón de relleno se hace en §3.8.
   [Permiso de scripts de usuario en Tampermonkey](https://www.tampermonkey.net/faq.php?q=Q209)

### 3.7 Crear el acceso directo

En **Ubuntu**, abre la carpeta del lanzador:

```bash
cd ~/vistobueno/tools/launcher
explorer.exe .
```

En el **Explorador de Windows**:

1. Copia `VistoBueno.bat`. Escribe `%LOCALAPPDATA%` en la barra de direcciones
   y pulsa **Enter**. Crea la carpeta **VistoBueno** y pega el archivo dentro.
2. Haz clic derecho en `VistoBueno.bat` y elige **Mostrar más opciones →
   Enviar a → Escritorio (crear acceso directo)**. Puedes cambiar el nombre
   del acceso directo a **VistoBueno**.
3. Abre el acceso directo y confirma que la pantalla de carga aparece en
   `http://localhost:8000/`. Si abriste una instancia de prueba en otra
   ventana, detenla con **Ctrl+C** antes de abrir el acceso directo.

El acceso directo inicia la distro configurada en `VistoBueno.bat` (por
defecto, **Ubuntu**) y espera el proyecto en `~/vistobueno`. Después de
actualizar, vuelve a copiar el `.bat` desde la
versión instalada si el archivo cambió y reconstruye la pantalla (§3.4).
Para iniciar a mano y ver si hay un error, ejecuta en **Ubuntu**:

```bash
cd ~/vistobueno
nix --extra-experimental-features 'nix-command flakes' develop --command python3 scripts/lanzar_app.py --sin-navegador
```

Mientras el comando esté abierto, entra a `http://localhost:8000/` desde
**Windows**. Mantén el puerto 8000: el complemento de DSpace lo usa.
[Red de WSL y acceso desde Windows](https://learn.microsoft.com/es-es/windows/wsl/networking)

> Opcional: `tools/launcher/crear_acceso_directo.ps1` crea el acceso
> directo con el icono `vistobueno.ico`. Requiere permitir la ejecución
> del script en PowerShell; el método manual de arriba no lo necesita.

> **Seguridad**: no expongas el puerto 8000 a la red ni uses
> `VISTOBUENO_HOST=0.0.0.0`. La API maneja datos personales y por diseño
> escucha solo en loopback. Para acceso desde otro equipo, usa el token y
> `VISTOBUENO_HOSTS` (ver el handover de despliegue).

### 3.8 Primera prueba en el equipo de la biblioteca

En **Ubuntu**, abre la carpeta de ejemplos:

```bash
cd ~/vistobueno/docs/ejemplos
explorer.exe .
```

Copia `doc_bueno.docx` y `doc_malo.docx` a **Descargas**. En el navegador
de **Windows**, sube un archivo a la vez. El bueno debe salir
**verde** y el malo **rojo**. Estos dos ejemplos solo prueban la pantalla
de carga y la validación.

Con el responsable técnico, elige una tesis de prueba autorizada por la
biblioteca que obtenga semáforo verde. Sigue estos pasos en el navegador
antes de usar VistoBueno para un depósito real:

1. En VistoBueno, revisa la ficha, completa los datos pendientes y pulsa
   **Preparar depósito**.
2. En el formulario de DSpace, pulsa **Rellenar con ficha de VistoBueno**.
   Revisa los campos, incluido el ORCID del asesor y **Acceso abierto**.
   Si algún valor queda pendiente, corrígelo en el formulario.
3. Completa el ensayo según el [protocolo del piloto](PILOTO_OPERADOR.md#5-checklist-de-ejecución).
   Abre de nuevo el ítem de prueba. Comprueba que conserve **Acceso abierto**.
   Coteja el handle (el enlace permanente del ítem) y los datos del depósito
   antes de pulsar **Confirmar depósito archivado**.
4. En VistoBueno, descarga la constancia y el registro. Abre la constancia
   en Word y revisa los datos. Abre el registro y comprueba el nombre en la
   columna **FIRMA**. Busca los archivos en **Descargas** de Windows o en la
   carpeta que usa tu navegador.

Si la prueba falla, anota el paso, el mensaje que aparece y la versión
instalada. Comunícaselo al responsable de la instalación sin adjuntar la
tesis ni los datos personales de la ficha.

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
npm.cmd --version
```

### 4.2 Entorno virtual y dependencias

Abre **PowerShell** en la carpeta del proyecto y comprueba que allí esté
`flake.nix`. Ejecuta:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install fastapi "uvicorn[standard]" pydantic email-validator pyyaml python-docx openpyxl lxml python-multipart httpx tzdata
```

La API usa `tzdata` para obtener la zona horaria de Lima en Windows.
[Zonas horarias en Python](https://docs.python.org/3/library/zoneinfo.html#data-sources)

Para pruebas, PDF u OCR, instala solo las dependencias que necesites:

```powershell
# Pruebas y SMTP local
.\.venv\Scripts\python.exe -m pip install pytest pytest-cov coverage aiosmtpd
# PDF
.\.venv\Scripts\python.exe -m pip install markdown weasyprint
# OCR
.\.venv\Scripts\python.exe -m pip install pymupdf pytesseract pillow
```

### 4.3 Arrancar

Desde la carpeta del proyecto, en **PowerShell**:

```powershell
cd frontend
npm.cmd ci
npm.cmd run build
cd ..
.\.venv\Scripts\python.exe scripts\lanzar_app.py --sin-navegador
```

Abre `http://localhost:8000/`. La API sirve la pantalla y escucha solo en
esta máquina. Para usar el lanzador, prepara la plantilla y el archivo
`recursos/firma.txt` como en §3.5, dentro de la carpeta del proyecto en
Windows. La comprobación final es la misma que en §3.8.

Si solo necesitas la API (sin la SPA), ejecuta
`.\.venv\Scripts\python.exe -m validator.api` y abre
`http://127.0.0.1:8000/docs`.

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

## 5. Verificación técnica

Para aceptar la instalación de la biblioteca, sigue las pruebas de §3.8.
El equipo de desarrollo puede hacer las siguientes comprobaciones desde
la raíz del proyecto en Ubuntu:

```bash
nix --extra-experimental-features 'nix-command flakes' develop --command bash -c 'cd frontend && npm ci && npm run build && npm test'
nix --extra-experimental-features 'nix-command flakes' develop --command pytest tests/ -q
nix --extra-experimental-features 'nix-command flakes' run .#test-ficha-deposito
```

El último comando usa un formulario simulado de DSpace. Comprueba el flujo
con el repositorio de la UNT durante la prueba de §3.8.

## 6. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `experimental Nix feature 'flakes' is disabled` | Falta la config | Agregar `experimental-features = nix-command flakes` a `~/.config/nix/nix.conf` |
| `error: getting status of '/nix/store/...'` | Entorno incompleto | Volver a `nix develop` |
| `python3: command not found` | Se ejecutó fuera del entorno | Entrar con `nix develop` o usar `nix develop --command python3 ...` |
| `Address already in use` | Otro proceso en el puerto | Cierra la instancia previa de VistoBueno con **Ctrl+C** en su ventana. Si otra aplicación usa el puerto 8000, pide ayuda a TI. |
| `400` por `Host` | `Host` ajeno (por ejemplo, la IP de WSL) | Usar `localhost` o `127.0.0.1`; si es un dominio propio, agregarlo a `VISTOBUENO_HOSTS` |
| `403` desde el navegador en WSL | La conexión no llega como local | Usa `http://localhost:8000/`. Pide a TI que revise el acceso local de WSL si persiste. |
| `skipped` en la suite | Faltan `recursos/` y/o `frontend/dist` | Es esperado; ver §2.3 |
| El lanzador indica que falta la pantalla | Falta `frontend/dist/index.html` | Ejecuta el paso §3.4 y vuelve a abrir el acceso directo. |
| El acceso directo no inicia | La distro `Ubuntu` no está disponible, Nix no se carga o falta el proyecto | Comprueba §3.1 a §3.4. Si tu distro tiene otro nombre, ajústalo en `VistoBueno.bat`. Usa el arranque manual de §3.7 para ver el mensaje. |
| Constancia o registro no disponible | Falta la plantilla o el nombre de FIRMA | Revisa §3.5 y vuelve a abrir el acceso directo. |
| La página no abre tras iniciar Ubuntu | El servicio no está listo o WSL no reenvía el puerto | Comprueba el mensaje del lanzador. Si Ubuntu tampoco inicia y no hay trámites abiertos, TI puede reiniciar WSL con `wsl --shutdown` desde PowerShell. Conserva el puerto 8000 y el acceso local. |
| `ZoneInfoNotFoundError` al iniciar en Windows nativo | Falta `tzdata` | Repite la instalación de dependencias de §4.2. |
| PDF falla en Windows | Falta Pango/GTK3 | Ver §4.4 |
| PDF falla en Linux/macOS | Falta Pango en el sistema | Usar Nix (`nix develop`) o instalar Pango |

## 7. Referencias

- `README.md` — comandos y estado del proyecto.
- `docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md` — checklist de seguridad y
  despliegue en la PC del operador.
- `docs/PILOTO_OPERADOR.md` — kit del piloto y checklist de 11 pasos.
- `docs/CONTRATO_API.md` — contrato de la API.
- `AGENTS.md` — convenciones de trabajo.

## Apéndice A — Checklist de puesta en marcha (actividad 4)

Usa esta lista para el hito de instalación de la actividad 4.

- [ ] `nix develop` entra sin errores (o el venv nativo arranca).
- [ ] `cd frontend && npm ci && npm run build && npm test` → build y tests
      en verde. Esto deja `frontend/dist`, que la suite usa.
- [ ] `nix run .#test -- tests/ -q` → verde, sin `xfail`. Con `recursos/`
      los `skipped` se reducen (ver §2.3).
- [ ] `nix run .#serve -- validator.api:app` → `/docs` responde `200` en
      `127.0.0.1:8000`.
- [ ] `Host: atacante.example` → `400`.
- [ ] `docs/ejemplos/doc_bueno.docx` → verde; `doc_malo.docx` → rojo
      (4 errores, 1 warning).
- [ ] `nix run .#test-ficha-deposito` → `✅ FLUJO COMPLETO OK` (opcional).
- [ ] Anotar versiones: `nix --version`, `python3 --version`,
      `node --version`, `git rev-parse --short HEAD`.
