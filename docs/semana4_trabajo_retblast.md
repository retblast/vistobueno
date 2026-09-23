# Semana 4 — Trabajo realizado

**Integrante**: retblast
**Rol**: Integrante 1 — Backend / API
**Semana**: 4 de 14 (22/09/2026 – 26/09/2026)
**Proyecto**: VistoBueno — Validador automático de formato de tesis (UNT FECyC)

---

## Objetivos de la semana

1. Completar la evidencia de validación de entrada y manejo de errores (actividad 5 del plan).
2. Generar y actualizar la especificación OpenAPI del endpoint (actividad 8 del plan).
3. Consolidar la refactorización de fixtures de tests y documentar los hallazgos.

---

## Actividades realizadas

### 14/09/2026: Entorno de desarrollo y rama de trabajo

Se creó la rama `semana4-nix-apps` y se mejoró el `flake.nix` del proyecto para exponer comandos útiles directamente desde nix:

- **`apps`**: sección que permite ejecutar `nix run .#test` (pytest) y `nix run .#serve` (uvicorn) sin necesidad de recordar los paths exactos.
- **`checks`**: permite correr `nix flake check` para ejecutar la suite de tests completa desde la verificación del flake.
- **`shellHook`**: al entrar con `nix develop`, ahora se muestra un menú con todos los comandos disponibles, lo cual facilita la incorporación de nuevos integrantes.

Durante el desarrollo se encontró un error de sintaxis (punto y coma faltante en el bloque `checks`) que fue detectado y corregido inmediatamente.

**Commits**:
- `chore(env): mejorar flake.nix con apps, checks y shellHook`
- `fix(env): agregar punto y coma faltante en checks del flake`

**Verificación**: `nix develop` imprime el menú, `nix flake show` lista las apps, `nix run .#test -- tests/ -v` ejecuta 142 tests sin errores.

---

### 16/09/2026: Tests de manejo de errores de la API

#### Parte A — Test de archivo excedido (413)

Se implementó un generador de DOCXs de tamaño controlado (`tests/_docx_generator.py`) que crea archivos válidos de tamaño arbitrario rellenando un DOCX mínimo con bytes aleatorios no comprimibles dentro del ZIP. Esto permite generar archivos de >10 MB en ~1 segundo sin consumir mucha memoria.

Se escribieron tests para:
- **`test_archivo_demasiado_grande`**: verifica que un DOCX de >10 MB devuelve 413.
- **`test_archivo_limite_exacto`**: verifica que un DOCX justo bajo 10 MB es aceptado (200).

Durante el desarrollo se encontraron dos bugs:
1. La aserción de tamaño usaba `<` en vez de `>`, haciendo que el test nunca detectara archivos grandes.
2. El estimado de overhead del ZIP estaba en 1 KB cuando el real es ~3-4 KB, causando que el test de límite generara un archivo ligeramente sobre el límite.

Ambos bugs fueron detectados ejecutando los tests y corregidos en commits separados.

#### Parte B — Tests de casos borde

Se agregaron tests para validar el comportamiento de la API con entradas inesperadas:
- **`test_archivo_sin_nombre`**: verifica que un nombre de archivo vacío devuelve 400/422.
- **`test_content_type_omitido`**: verifica que sin Content-Type se acepta por extensión.
- **`test_archivo_nombre_con_espacios`**: verifica que nombres con espacios y caracteres especiales se procesan correctamente.
- **`test_content_type_octet_stream`**: verifica que `application/octet-stream` se acepta (comportamiento de algunos navegadores).

#### Parte C — Test de ZIP corrupto

Se implementó `test_zip_valido_pero_no_docx` que envía un ZIP válido pero que no contiene `word/document.xml`. Este test documenta un comportamiento inesperado de la API: devuelve 500 (KeyError no capturado) en lugar de 422, identificando una oportunidad de mejora en el manejo de excepciones.

#### Parte D — Refactorización del helper de DOCXs

Se extrajo la lógica de generación de DOCXs grandes a un módulo compartido `tests/_docx_generator.py` con la función `build_large_docx()`. Se renombró el archivo para no conflictuar con el `_docx_builder.py` existente (que forma parte del sistema de mutaciones de tests de propiedad).

#### Parte E — Validación de mensajes de error

Se agregó `test_mensajes_error_son_descriptivos` que verifica que todos los paths de error de la API devuelven un campo `detail` con información útil para el usuario.

**Commits del día** (9 commits):
1. `test(api): agregar generador de DOCX grande y test de archivo excedido`
2. `fix(tests): corregir aserción de tamaño en test de archivo excedido`
3. `test(api): agregar test de archivo en el límite exacto de 10 MB`
4. `fix(tests): corregir cálculo de tamaño en test de límite exacto`
5. `test(api): agregar tests de casos borde — nombre vacío, content-type, espacios`
6. `test(api): verificar comportamiento con ZIP válido pero sin document.xml`
7. `refactor(tests): extraer generador de DOCXs a módulo compartido`
8. `fix(tests): corregir estimación de overhead ZIP en build_large_docx`
9. `test(api): validar mensajes de error y crear helper _docx_generator`

**Resultado**: 148 tests (142 originales + 6 nuevos), todos pasan.

---

### 21/09/2026: Robustez del manejo de errores y documentación OpenAPI

#### Parte A — Corrección del manejo de errores en la API

Durante el día anterior se identificó que un ZIP válido sin `word/document.xml` producía un 500 interno en lugar de un 422 informativo. Se investigó la causa: el extractor lanza `KeyError` al intentar leer el archivo del paquete OPC, y el handler genérico solo detectaba `BadZipFile`.

Se corrigió el handler de errores en `validator/api.py` para capturar también `KeyError` y `ValueError`, devolviendo 422 con mensajes descriptivos en cada caso. Se actualizaron los tests correspondientes para exigir 422 estricto en lugar de aceptar (422, 500).

#### Parte B — Generación automatizada de OpenAPI spec

Se creó `scripts/generate_openapi.py`, un script que extrae el esquema OpenAPI generado por FastAPI y lo escribe en `docs/openapi_spec.json`. El script acepta un flag `--output` para personalizar la ruta de salida.

Durante el desarrollo se encontraron dos problemas:
1. El import usaba `from api import app` en lugar de `from validator.api import app`.
2. Al ejecutar desde la raíz del proyecto, `validator` no estaba en `sys.path`.

Ambos se corrigieron y se regeneró la especificación, actualizando la versión de 1.0.0 a 1.1.0.

#### Parte C — Refactorización de fixtures de tests

Se creó `tests/conftest.py` con los y fixtures que se comparten entre módulos de test: `CLIENTE`, `PLANTILLA`, `CAMPOS_RESULTADO`, `CAMPOS_RESUMEN`, `CAMPOS_METADATOS`, y fixtures parametrizados. Se actualizaron los imports en `test_api_contract.py` para usar el conftest en lugar de definiciones duplicadas.

#### Parte D — Test de magic bytes inválidos

Se agregó `test_zip_magic_bytes_invalidos` que verifica que un archivo con extensión `.docx` pero contenido basura (cabecera MZ de EXE) devuelve 422. Este escenario cubre el caso de un usuario que renombra un archivo no-DOCX a `.docx`.

#### Parte E — Regeneración de la especificación OpenAPI

Se ejecutó `scripts/generate_openapi.py` para sincronizar `docs/openapi_spec.json` con el estado actual de la app. La spec refleja ahora:
- Versión 1.1.0 (antes 1.0.0)
- Descripción del campo archivo con `contentMediaType`
- Documentación de todos los códigos de error (400, 413, 415, 422, 500)

**Commits del día** (13 commits):
1. `fix(api): capturar KeyError para DOCX sin document.xml`
2. `fix(api): incluir ValueError del extractor en respuesta 422`
3. `test(api): actualizar test ZIP sin document.xml para exigir 422`
4. `fix(tests): corregir aserción de mensajes de error para 500`
5. `feat(scripts): crear generate_openapi.py para regenerar spec`
6. `fix(scripts): corregir import de validator.api en generate_openapi.py`
7. `fix(scripts): agregar raíz del proyecto al sys.path`
8. `chore: regenerar openapi_spec.json con spec actualizada`
9. `refactor(tests): crear conftest.py con fixtures compartidos`
10. `fix(tests): usar fixtures de conftest en test_api_contract`
11. `test(api): agregar test de ZIP con magic bytes inválidos`
12. `docs: actualizar bitácora semana 4 con actividades del día 1`
13. `chore: limpiar imports no usados en tests`

**Resultado**: 149 tests, todos pasan. Spec OpenAPI sincronizada. Fixtures refactorizados.

---

### 23/09/2026: Cierre de la actividad 5 — validación de entrada y manejo de errores

Se completó el trabajo pendiente de los días anteriores para cerrar la
**actividad 5 del plan de prácticas** (*Implementar la validación de entrada
en el endpoint … Documentar cada caso de error en CONTRATO_API.md*).

#### Parte A — Validación de magic bytes (cabecera ZIP)

Se agregó una verificación temprana en `validator/api.py`: todo DOCX es un
paquete OPC (ZIP) y debe comenzar con la firma local `PK\x03\x04`. Archivos
renombrados a `.docx` sin cabecera ZIP ahora se rechazan con `422` y un
mensaje descriptivo en español **antes** de escribir el archivo temporal.

El orden de validación quedó: extensión → content-type → correo → lectura →
tamaño (413) → vacío (422) → magic bytes (422) → procesamiento.

**Commits**:
1. `feat(api): validar magic bytes PK del DOCX en POST /validar`
2. `test(api): exigir 422 con mensaje claro para cabecera ZIP inválida`

#### Parte B — Campo `correo` (opcional)

Se implementó el campo de formulario `correo` previsto en las actividades 2,
4 y 5 del plan (Option A: solo validación de formato, sin envío — el envío
corresponde a la actividad 6):

- Campo **opcional** (`default=None`): ausente o vacío → se omite; no rompe
  clientes existentes.
- Si se envía, se valida con la librería `email-validator` (sin verificar
  entregabilidad, para no acoplarse a DNS en tests/dev).
- Formato inválido → `422` con mensaje en español: `Correo electrónico
  inválido: '…'. Formato esperado: usuario@dominio.`
- Se añadió `email-validator` a `pythonEnv` en `flake.nix` (dependencia
  gestionada por Nix, sin `pip install`).

**Commits**:
3. `chore(env): agregar email-validator a pythonEnv en flake.nix`
4. `feat(api): aceptar y validar campo correo en POST /validar`
5. `test(api): cubrir validación de correo opcional`

#### Parte C — Sincronización de documentación (evidencia de la actividad 5)

El producto de la actividad 5 es *"Casos de error documentados en
docs/CONTRATO_API.md y pruebas asociadas"*. Se cerraron las discrepancias
pendientes:

- **CONTRATO_API.md → v1.2.0**: campo `correo`, magic bytes, MIME
  `application/octet-stream`, ejemplos de `400` / `422` (cabecera, KeyError
  sin `document.xml`, ValueError, correo), tabla de códigos actualizada,
  ejemplo `curl` con correo, changelog.
- **FLUJO_API.md → v1.1**: diagrama actualizado con nodos de nombre vacío
  (`400`), correo (`422`) y magic bytes (`422`); tabla de validaciones HTTP
  ampliada.
- **openapi_spec.json** regenerada: versión `1.2.0`, propiedad `correo`,
  respuesta `400` documentada. Verificada idempotente (sha256 estable tras
  regenerar dos veces).

**Commits**:
6. `docs(api): sincronizar CONTRATO_API con validación de entrada (v1.2.0)`
7. `docs(api): actualizar FLUJO_API con magic bytes y validación de correo`
8. `chore(api): regenerar openapi_spec.json para v1.2.0`

**Resultado**: **213 tests, todos pasan** (206 previos + 7 nuevos: 1 magic
bytes truncado, 6 de correo). `ruff` y `mypy` limpios en `validator/`.

---

## Evidencias producidas

| Evidencia | Archivo | Competencia curricular |
|-----------|---------|------------------------|
| Entorno de desarrollo con apps nix | `flake.nix` | Ingeniería de Software I |
| Menú de comandos en shellHook | `flake.nix` | Ingeniería de Software I |
| Corrección de error de sintaxis | `flake.nix` | Ingeniería de Software II |
| Generador de DOCXs grandes | `tests/_docx_generator.py` | Ingeniería de Software II |
| Tests de límites y casos borde | `tests/test_api_contract.py` | Ingeniería de Software II |
| Corrección de manejo de errores (KeyError, ValueError) | `validator/api.py` | Ingeniería de Software II |
| Script de generación OpenAPI | `scripts/generate_openapi.py` | Ingeniería de Software II |
| Especificación OpenAPI regenerada | `docs/openapi_spec.json` | Ingeniería de Software I |
| Fixtures compartidos de tests | `tests/conftest.py` | Ingeniería de Software II |
| Validación de magic bytes (cabecera PK) | `validator/api.py` | Ingeniería de Software II |
| Dependencia `email-validator` en Nix | `flake.nix` | Ingeniería de Software I |
| Campo `correo` con validación de formato | `validator/api.py` | Ingeniería de Software II |
| Tests de validación de correo | `tests/test_api_contract.py` | Ingeniería de Software II |
| Contrato v1.2.0 con todos los casos de error | `docs/CONTRATO_API.md` | Ingeniería de Software I |
| Diagrama de flujo actualizado | `docs/FLUJO_API.md` | Ingeniería de Software I |
| Especificación OpenAPI v1.2.0 | `docs/openapi_spec.json` | Ingeniería de Software I |

---

## Relación con competencias

| Competencia | Actividad |
|-------------|-----------|
| **Ingeniería de Software I** — Technical documentation, tooling | Mejora del entorno de desarrollo con nix apps y shellHook documentado |
| **Ingeniería de Software I** — API contract, OpenAPI spec | Generación y actualización de la especificación OpenAPI |
| **Ingeniería de Software I** — API contract, OpenAPI spec | Contrato v1.2.0 con magic bytes, correo y documentación completa de errores |
| **Ingeniería de Software II** — Configuration management | Gestión del entorno reproducible con Nix flake (incluye `email-validator`) |
| **Ingeniería de Software II** — Error handling, testing | Corrección del handler de errores, magic bytes, validación de correo, tests de límites y casos borde |

---

## Pendiente

- [x] Crear rama de trabajo
- [x] Mejorar flake.nix (apps, checks, shellHook)
- [x] Verificar entorno (nix develop, nix flake show, nix run)
- [x] Ejecutar suite completa de tests (142/142)
- [x] Verificar API manualmente con curl (6 escenarios)
- [x] Auditar CONTRATO_API.md vs api.py (3 discrepancias encontradas)
- [x] Revisar openapi_spec.json vs app actual
- [x] Test de archivo excedido (413) con generador de DOCX grande
- [x] Tests de casos borde (nombre, content-type, espacios)
- [x] Test de ZIP válido pero no DOCX
- [x] Refactorización de helper de DOCXs
- [x] Validación de mensajes de error
- [x] Corregir KeyError/ValueError en handler de errores → 422
- [x] Crear script `scripts/generate_openapi.py`
- [x] Regenerar `openapi_spec.json` (v1.1.0)
- [x] Crear `tests/conftest.py` con fixtures compartidos
- [x] Test de magic bytes inválidos
- [x] Corregir discrepancias menores en CONTRATO_API.md → v1.2.0
- [x] Validación de magic bytes (`PK\x03\x04`) en el endpoint
- [x] Campo `correo` opcional con validación de formato (actividad 5)
- [x] Tests de validación de correo (6 escenarios)
- [x] Documentar 400 / 422 (KeyError, ValueError, cabecera, correo) en CONTRATO_API
- [x] Actualizar FLUJO_API.md (diagrama + tabla de validaciones)
- [x] Regenerar `openapi_spec.json` a v1.2.0
- [x] Suite completa: 213/213 tests, ruff y mypy limpios
- [ ] **Actividad 5 cerrada** (evidencia consolidada en esta bitácora)
- [ ] Actualizar conteo de suite en `AGENTS.md` y `00_indice_diseno.md` (aprobado)
- [ ] Push de la rama `semana4-cierre-actividad5` + PR (esperando orden de Master)

---

## Plan siguiente

- **Actividad 6 (semanas 5–6 del plan)**: notificación por correo —
  investigar SMTP institucional, diseñar plantilla HTML con reglas fallidas,
  integrar envío al flujo de `POST /validar` cuando `semaforo == "rojo"`.
- **Actividad 9 (semana 6)**: investigar API REST de DSpace FECyC
  (endpoints de submission, metadatos, autenticación).
- Coordinar con Integrante 2 el campo adicional `correo` antes de abrir el PR.
- Solicitar credenciales SMTP y acceso DSpace al responsable de la sede
  (Salcedo Quiñones) para no bloquear las semanas 6–7.
