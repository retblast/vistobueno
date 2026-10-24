# Revisión transversal del proyecto — 2026-10-13

**Alcance**: revisión de todo el repositorio (motor, capa DSL, API, IA, tests,
scripts, frontend y configuración) buscando errores y mejoras.
**Método**: 5 exploraciones por área + **verificación manual línea por línea**
de cada hallazgo. Los hallazgos dudosos se descartaron explícitamente (ver
[§ Descartados](#descartados-falsos-positivos-verificados)) para que nadie los
reinvestigue.

> Reparto según los límites de responsabilidad de `AGENTS.md`. El mapa de
> usuario↔integrante es el de las bitácoras vigentes (semana 5/7/8) y **debe
> confirmarse con el equipo** si cambió.

| Integrante | Rol | Usuario (bitácora) |
|------------|-----|--------------------|
| Integrante 1 | Backend / API | `retblast` |
| Integrante 2 | Frontend / UX | `renzo` (`Rodo00`) |
| Integrante 3 | Motor de reglas / Procesamiento | `ivanSanchezSil` |

Estado sano de referencia: `reglas_unt.yaml` = 49 reglas, legacy = 44 (32
mecanizables), doc bueno evalúa 43/49, suite = **455 tests**, CI verde,
`nix flake check` OK.

---

## Resumen ejecutivo

| Hallazgo | Prioridad | Área | Integrante | Estado |
|----------|-----------|------|------------|--------|
| `POST /validar` sin auth ni rate-limit (posible uso como relay de correo si las notificaciones están activas) | Alta\* | API | 1 | |
| Zip bomb: se descomprimen partes del DOCX sin cota de tamaño descomprimido | Alta | Extractor | 3 | ✅ Resuelto (PR #56) |
| Test de paridad vacuo (`assert True` en bucle) | Media | Tests | 1 (coord. 3) | |
| El DSL se recompila en cada request | Media | Motor | 3 (coord. 1) | ❌ Descartado (1.5% medido) |
| `fetch` del upload sin `timeout` ni `AbortController` | Media | Frontend | 2 | |
| `load_rules` sin manejo de error (YAML inválido → excepción cruda) | Baja | Motor | 3 | ✅ Resuelto |
| Campos del contrato sin consumidor en el frontend (`total_evaluadas`, `reglas_no_aplicables`, `aplicable`) | Baja | API/Frontend | 1 + 2 | |
| Restauración de foco del dropzone se altera bajo `StrictMode` (dev) | Baja | Frontend | 2 | |
| `.gitignore` sin `*.docx` / `*.pdf` (riesgo de versionar tesis reales) | Baja | Transversal | equipo | |

\* Alta solo si se despliega con `VISTOBUENO_NOTIFICACIONES=1` y SMTP configurado;
en local/CI el envío está desactivado.

---

## Integrante 1 — Backend / API (`retblast`)

Área: `api.py`, `api_models.py`, `notificacion.py`, `scripts/verificar_secretos.py`,
`tests/`, `docs/CONTRATO_API.md`, `docs/FLUJO_API.md`.

### Sin autenticación ni rate-limiting en `POST /validar` — Alta\*
`validator/api.py:214` expone un único endpoint público. Cuando la notificación
está habilitada (`VISTOBUENO_NOTIFICACIONES=1` + SMTP completo), el mismo
`POST /validar` con `notificar=true` y un `correo` válido provoca un envío de
correo (`validator/notificacion.py`, `smtplib`). Sin autenticación ni límite de
tasa, un tercero podría:
- usar el servidor como **relay de correo** hacia un destinatario arbitrario;
- saturar CPU (cada request compila el DSL y analiza un XML; ver "El DSL se recompila en cada request").

**Atenuantes**: el MVP excluye auth a propósito (`AGENTS.md`) y el envío está
gated por la variable de entorno (desactivado por defecto).
**Sugerencia**: documentar como decisión de despliegue; si se expone fuera de
la red de la facultad, añadir un límite de tasa (p. ej. middleware) y/o restringir
el `correo` a dominios institucionales.

### Test de paridad vacuo — Media
`tests/test_paridad_formatos.py:412-426` (`test_paridad_estructura_incompleta`):
el bucle `for _rid in (...): assert True  # la paridad exacta ya se verificó…` no
comprueba nada; la docstring promete comparar los `faltantes` del DFA con el motor
legacy, pero no hay aserción sobre ellos.
**Sugerencia**: o bien asertar de verdad que los tres esquemas fallan y que sus
`faltantes` coinciden, o eliminar el test. Es del área de `tests/` (Int1) pero
toca paridad motor↔DSL → **coordinar con Int3**.

### Campos DTO sin consumidor (lado contrato) — Baja
`total_evaluadas`, `reglas_no_aplicables` (`api_models.py`) y `aplicable`
(por regla) se emiten en la respuesta pero **no se usan** en `frontend/src/`
(grep sin resultados). O son superficie muerta del contrato o falta integrarlos
en la UI (ver lado Int2). **Coordinar con Int2**: decidir si se consumen o se
retiran/documentan.

### Observación — `notificacion.py` (mejora opcional)
El módulo ya es best-effort y gateado por entorno; no se hallaron errores. Si en
el hallazgo de autenticación/rate-limit se añade límite de tasa, considerar también validar el dominio del `correo`
antes de intentar el envío.

---

## Integrante 2 — Frontend / UX (`renzo`)

Área: `frontend/` (React) y `docs/`.

### `fetch` de validación sin `timeout` ni `AbortController` — Media
`frontend/src/components/Upload.jsx:175-178` hace `fetch(...)` sin `signal` de
cancelación ni timeout. Si el backend acepta la conexión pero nunca responde, la
UI queda en `loading` indefinidamente (el `finally` de `:222-224` solo corre si
la promesa se resuelve). El resto del manejo de errores (`:179-221`) es correcto.
**Sugerencia**: `AbortController` con `setTimeout` (p. ej. 60-90 s, por encima
del costo real del motor) y mensaje de "timeout" reutilizando `cargarMock`.

### Restauración de foco del dropzone bajo `StrictMode` — Baja (dev)
`frontend/src/components/Upload.jsx:75-82`: el guard `primeraCarga` es un `ref`
local; en React 18 `StrictMode` (dev) el efecto de montaje corre dos veces con el
mismo ref, así que en la **carga inicial** puede ejecutarse `zonaRef.current.focus()`
y robar el foco. En producción con navegación real (volver de Reporte) funciona.
**Sugerencia**: mover el estado "ya montado" fuera del ciclo de StrictMode o
condicionar a un prop `autoFocus`; o aceptarlo como comportamiento solo-dev y
documentarlo.

### Campos del contrato sin usar (lado consumo) — Baja
Ver el hallazgo "Campos DTO sin consumidor" arriba. Decidir con Int1 si `total_evaluadas` / `reglas_no_aplicables` /
`aplicable` se muestran en el reporte o se retiran.

### Sin hallazgos
`frontend/src/App.jsx`, `components/Report.jsx`, `mocks.js`: revisados sin
problemas relevantes (el manejo de errores de red → modo demo es intencional).

---

## Integrante 3 — Motor de reglas / Procesamiento (`ivanSanchezSil`)

Área: `engine.py`, `models.py`, `extractor.py`, `checks.py`, `prompts.py`,
`tokenizer.py`, `analizadores.py`, `automata.py`, `compilador.py`, `dsl_check.py`,
`llm.py`, `asistente.py`, YAML de reglas.

### Zip bomb: descompresión sin cota — Alta — ✅ RESUELTO
`validator/extractor.py` (`extract`): se hacía
`etree.fromstring(z.read("word/document.xml"))` (y headers/footers/footnotes) sin
limitar el tamaño **descomprimido**. La validación de `api.py` limita el upload
**comprimido** a 10 MB, pero un `.docx` (ZIP) de pocos KB puede expandir
`document.xml` a GBs → agotamiento de memoria al parsear.
**Resolución (PR #56)**: nueva `_leer_parte()` que acota a
`TAMANO_MAXIMO_PARTE_BYTES` (50 MB) **durante la lectura** (no confía en el
`file_size` declarado del central directory, falseable en un ZIP hostil) y lanza
`zipfile.BadZipFile`, que la API ya mapea a 422 sin cambios. Cubierto por
`tests/test_extractor_zipbomb.py` (rechazo de la bomba, bomba comprimida
diminuta, no-regresión de un DOCX normal e integración API→422).

### El DSL se recompila en cada request — Media — ❌ DESCARTADO (medido)
`validator/engine.py`: `validate_docx` instanciaba `CompilerDSL()` y llamaba
`ejecutar(...)`, que compila analizadores/autómatas **por petición**. `_get_rules`
cacha el YAML crudo, pero no el resultado compilado.
**Verificación (2026-10-20)**: se midió el costo real —
`CompilerDSL().compilar(reglas_unt.yaml)` = **0.32 ms**, frente a
`validate_docx` completo = **21.1 ms** por documento: la compilación es **1.5%**
del request. El costo dominante es la extracción + evaluación (XPath, parseo XML),
no la compilación.
**Por qué NO se cachea**: las `ReglaCompilada` comparten analizadores con estado
mutable por ejecución (`ultimo_nodo`, `valor`, `ultima_ruta`); servir la lista
compilada a requests concurrentes sería un data race. Un caché seguro exigiría
clonar los analizadores por request, y el clonado no es más barato que recompilar.
Ganar 1.5% a costa de complejidad (y riesgo de concurrencia) no se justifica.
Si en el futuro se perfila el request, atacar la extracción/evaluación (~98.5%),
no la compilación. **Coordinar con Int1** antes de tocar el despacho a threadpool.

### `load_rules` sin manejo de error — Baja — ✅ RESUELTO
`validator/engine.py:25-37`: `load_rules()` lanzaba excepciones crudas de
PyYAML/`TypeError` si el archivo faltaba, tenía sintaxis inválida o su contenido
no era un diccionario. **Resolución (PR actual)**: se añadió manejo de errores
controlado con `try/except FileNotFoundError`, `yaml.YAMLError` y validación
`isinstance(data, dict)`, lanzando `ValueError` con mensajes claros en español
('No se encontró el archivo...', 'sintaxis YAML inválida', 'no devolvió un
diccionario'). Cubierto por verificación manual: casos de archivo inexistente,
YAML malformado y escalar no-dict todos lanzan `ValueError` apropiado; la carga
normal de `reglas_unt.yaml` (49 reglas) sigue funcionando sin cambios).

### Sin hallazgos
`checks.py`, `models.py`, `prompts.py`, `tokenizer.py`, `analizadores.py`,
`automata.py`, `compilador.py`, `dsl_check.py`, `llm.py`, `asistente.py`: no se
encontraron errores en esta pasada (los trabajos recientes —track changes,
explicabilidad, ubicación de NotaPie— están correctos y probados).

---

## Transversal — equipo

### `.gitignore` sin `*.docx` / `*.pdf` — Baja
`.gitignore` ignora `recursos/` (correcto) pero no patrones globales. Hay tesis
reales sin trackear en la raíz (`TESIS_LINARES_*.docx`, `TESIS_CARRION*.pdf`,
`Plan_PPP_*.docx`, `ESTRUCTURA_PORTAFOLIO.md`); un `git add .` accidental las
versionaría (documentos con datos personales).
**Sugerencia**: añadir `*.docx` y `*.pdf` a `.gitignore` (o al menos excluir los
archivos reales), dejando excepciones explícitas si se necesitan plantillas.
No hay un dueño único: lo puede hacer cualquiera con visto bueno del equipo.

### Documentación
Conteos ya sincronizados (49 reglas / 43 evaluadas / 455 tests) en `README.md`,
`AGENTS.md` y `docs/diseno/00_indice_diseno.md`. No se detectó documentación
desactualizada más allá de lo anterior.

---

## Descartados (falsos positivos verificados)

Revisados y **no** son problemas (no perder tiempo en ellos):

| Reporte inicial | Verificación | Resultado |
|-----------------|--------------|-----------|
| `checks.py` pasa mal las `flags` a `re.compile` | `checks.py:83-89` usa `check["patron"]` directo; no existe tal código | Falso |
| `scripts/verificar_secretos.py:93` `except OSError, UnicodeDecodeError:` sería error de sintaxis | **Válido en Python 3.14** (PEP 758, sin paréntesis); `ast.parse` OK | Falso |
| `tests/test_cli_integracion.py:92-100` es vacuo | Sí tiene aserciones reales (`all(r["severity"] == "error" ...)`) | Falso |
| `tests/test_notificacion.py` usa conteo 47 (desactualizado) | Es payload *mock*; el número es arbitrario, no se asierta contra reglas reales | Falso |
| `engine.py` `_RULES_CACHE` global mutable | No existe; `load_rules` no cachea y el cacheo real es `@cache` en `api.py:60` | Falso |
| XXE en el parser del extractor | lxml por defecto bloquea entidades externas (`Entity 'xxe' not defined`) | Falso |

---

## Próximos pasos propuestos

1. **Int1**: auth/rate-limit en `POST /validar` (documentar/limitar) y arreglar el test de paridad vacuo.
2. **Int3**: cachear el DSL compilado — *descartado vía medición (1.5%); si hay perfilado futuro, atacar la extracción/evaluación (~98.5%)*. **`load_rules` con manejo de errores: resuelto** (PR actual).
3. **Int2**: `AbortController` en el upload y foco del dropzone bajo `StrictMode`.
4. **Equipo**: decidir uso/retiro de campos del contrato y ampliar `.gitignore`.

Ninguno de estos hallazgos rompe el CI actual; son mejoras de robustez,
seguridad de despliegue y calidad de pruebas.
