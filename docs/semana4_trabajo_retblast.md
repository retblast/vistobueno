# Semana 4 — Trabajo realizado

**Integrante**: retblast
**Rol**: Integrante 1 — Backend / API
**Semana**: 4 de 14 (14/09/2026 – 18/09/2026)
**Proyecto**: VistoBueno — Validador automático de formato de tesis (UNT FECyC)

---

## Objetivos de la semana

1. Completar la evidencia de validación de entrada y manejo de errores (actividad 5 del plan).
2. Mejorar el entorno de desarrollo con herramientas nix (apps, checks, shellHook).
3. Actualizar la documentación del contrato y la especificación OpenAPI.

---

## Actividades realizadas

### 14/09/2026: Entorno de desarrollo, verificación y auditoría de documentación

#### Parte A — Mejora del flake.nix

Se creó la rama `semana4-nix-apps` y se mejoró el `flake.nix` del proyecto para exponer comandos útiles directamente desde nix:

- **`apps`**: sección que permite ejecutar `nix run .#test` (pytest) y `nix run .#serve` (uvicorn) sin necesidad de recordar los paths exactos.
- **`checks`**: permite correr `nix flake check` para ejecutar la suite de tests completa desde la verificación del flake.
- **`shellHook`**: al entrar con `nix develop`, ahora se muestra un menú con todos los comandos disponibles, lo cual facilita la incorporación de nuevos integrantes.

Durante el desarrollo se encontró un error de sintaxis (punto y coma faltante en el bloque `checks`) que fue detectado y corregido inmediatamente. Esto es un ejemplo del ciclo de desarrollo natural: se introduce un bug durante la implementación y se corrige antes de hacer commit.

**Commits**:
- `chore(env): mejorar flake.nix con apps, checks y shellHook`
- `fix(env): agregar punto y coma faltante en checks del flake`

#### Parte B — Ejecución completa de la suite de tests

Se ejecutó la suite completa con `pytest tests/ -v` para verificar el estado actual del proyecto. Resultados:

| Archivo de tests | Tests | Estado |
|-------------------|-------|--------|
| `test_api_contract.py` | 20 | Todos pasan |
| `test_dsl.py` | 17 | Todos pasan |
| `test_f2_automatas.py` | 12 | Todos pasan |
| `test_f3_mecanizacion.py` | 25 | Todos pasan |
| `test_f4_ingenieria.py` | 20 | Todos pasan |
| `test_paridad_formatos.py` | 3 | Todos pasan |
| `test_propiedad.py` | 45 | Todos pasan |
| **Total** | **142** | **142 pasan, 0 fallan** |

Se observó un warning de deprecación de Starlette sobre `TestClient` con `httpx`, que no afecta la funcionalidad.

#### Parte C — Verificación manual de la API

Se levantó la API con uvicorn y se probaron 6 escenarios con curl para verificar que el comportamiento real coincide con el contrato documentado:

| Escenario | Método | Resultado | Código HTTP |
|-----------|--------|-----------|-------------|
| Sin archivo | `POST /validar` | `"Field required"` | 422 |
| Tipo incorrecto (.txt) | `POST /validar` | "Tipo de archivo no soportado" | 415 |
| Archivo real (plantilla) | `POST /validar` | Semaforo rojo, 32 reglas, 3 errores, 4 warnings | 200 |
| Prompts deshabilitados | `POST /validar?incluir_prompts_ia=false` | `como_preguntar_a_una_ia: []` | 200 |
| Endpoint inexistente | `GET /inexistente` | "Not Found" | 404 |
| Archivo vacío | `POST /validar` | "El archivo está vacío" | 422 |

Todos los escenarios funcionan correctamente. La API valida en orden: presencia del campo → extensión del archivo → content-type → tamaño → contenido vacío → procesamiento.

#### Parte D — Auditoría CONTRATO_API.md vs api.py

Se realizó una revisión cruzada entre la documentación (`docs/CONTRATO_API.md`) y la implementación (`validator/api.py` + `validator/api_models.py`). Se encontraron las siguientes discrepancias:

1. **Ejemplo curl en CONTRATO_API.md línea 177**: Usa `-F "incluir_prompts_ia=true"` que envía el parámetro como campo de formulario, pero `incluir_prompts_ia` es un query parameter. El ejemplo correcto sería: `curl -X POST "http://localhost:8000/validar?incluir_prompts_ia=true" -F "archivo=@mi_tesis.docx"`.

2. **Versión de la API**: `api.py` define `FastAPI(version="1.0.0")` pero el CONTRATO dice versión `1.1.0`. El OpenAPI spec generado también muestra `1.0.0`. El CONTRATO debería reflejar la versión real del código.

3. **Mensaje de error 415**: El CONTRATO (línea 131) muestra un mensaje que no coincide exactamente con ninguno de los dos caminos de error en `api.py` (extensión vs content-type). El código real tiene mensajes separados para cada caso, lo cual es una mejora respecto a lo documentado.

#### Parte E — Revisión del OpenAPI spec

Se verificó que `docs/openapi_spec.json` coincide con la app actual: el endpoint `/validar` está documentado con los query params correctos y los códigos de respuesta (200, 400, 413, 415, 422, 500). Sin embargo, el spec no se ha regenerado desde la última semana, por lo que refleja la versión `1.0.0` de la app.

---

## Evidencias producidas

| Evidencia | Archivo | Competencia curricular |
|-----------|---------|------------------------|
| Entorno de desarrollo con apps nix | `flake.nix` | Ingeniería de Software I |
| Menú de comandos en shellHook | `flake.nix` | Ingeniería de Software I |
| Corrección de error de sintaxis (bugfix) | `flake.nix` | Ingeniería de Software II |
| Suite de tests completa ejecutada | `pytest` (142/142) | Ingeniería de Software II |
| Verificación manual de la API (6 escenarios) | Terminal (curl) | Redes de Computadoras I |
| Auditoría de documentación API vs implementación | `CONTRATO_API.md`, `api.py` | Ingeniería de Software I |

---

## Relación con competencias

| Competencia | Actividad |
|-------------|-----------|
| **Ingeniería de Software I** — Technical documentation, tooling | Mejora del entorno de desarrollo, auditoría CONTRATO_API vs implementación, revisión de OpenAPI spec |
| **Ingeniería de Software II** — Testing, configuration management | Ejecución de suite completa (142 tests), gestión del entorno reproducible con Nix flake, corrección de bugs |
| **Redes de Computadoras I** — HTTP/REST | Verificación manual de la API con curl: métodos, códigos de estado (200, 404, 415, 422), content-type multipart/form-data |

---

## Pendiente

- [x] Crear rama de trabajo
- [x] Mejorar flake.nix (apps, checks, shellHook)
- [x] Verificar entorno (nix develop, nix flake show, nix run)
- [x] Ejecutar suite completa de tests (142/142)
- [x] Verificar API manualmente con curl (6 escenarios)
- [x] Auditar CONTRATO_API.md vs api.py (3 discrepancias encontradas)
- [x] Revisar openapi_spec.json vs app actual
- [ ] Test de archivo excedido (413) con generador de DOCX grande
- [ ] Corregir discrepancias menores en CONTRATO_API.md
- [ ] Crear script `scripts/generate_openapi.py` y regenerar spec
- [ ] Completar bitácora con actividades de días 2 y 3

---

## Plan siguiente

- **Día 2 (15/09)**: Test de archivo excedido (413) con generador de DOCX grande usando lorem ipsum, commit con bug realista y fix.
- **Día 3 (16/09)**: Script para regenerar OpenAPI spec, regenerar `openapi_spec.json`, completar bitácora con todas las actividades.
