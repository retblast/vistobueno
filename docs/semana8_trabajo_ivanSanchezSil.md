# Bitácora Semana 8 — ivanSanchezSil

- **Integrante**: Iván Sánchez Silva (Integrante 3 — Motor de reglas)
- **Semana**: 8
- **Fechas**: 2026-10-12 → 2026-10-16
- **Rol**: Motor de reglas / Procesamiento (DSL, extractor, checks)

---

## Objetivos de la semana

1. **Sangría de párrafo tolerante a 1.25 cm**: la regla `sangria_parrafo`
   exigía 720 twips (1.27 cm) con igualdad exacta, pero las plantillas y tesis
   reales usan 708/709 twips (~1.25 cm). Aceptar ese desvío menor sin perder
   la detección de sangrías realmente mal puestas.
2. **Autores de carátula "altas y bajas"**: la regla
   `caratula_autores_mayusculas_sin_negrita` exigía TODO en mayúsculas, cuando
   las tesis reales aprobadas (y el placeholder de la plantilla) escriben el
   nombre en mayúsculas y minúsculas. Validar "altas y bajas" sin descuidar la
   negrita.
3. Mantener la **paridad legacy↔DSL** literal (ambos motores al mismo cambio) y
   la suite completa en verde.
4. **Módulo de IA (Paso 0 + Funcionalidades 2 y 3)**: implementar el cliente LLM
   local (`validator/llm.py`, con `StubLLM`), la explicación/priorización advisory
   de los fallos (`validator/asistente.py`) y la clasificación asistida del tipo
   documental, sin tocar el semáforo y con el contrato de API documentado para I1
   (`docs/HANDOVER_API_IA.md`).

---

## Actividades realizadas

### 2026-10-12 — Tolerancia numérica en las comparaciones de atributo

- **Diagnóstico (sangría)**: la regla es `all_eq` sobre `@w:firstLine` con
  `esperado: '720'`. En la tesis real de Linares los párrafos de cuerpo usan
  708 twips (~1.25 cm) y, con igualdad exacta, TODOS fallaban —
  `@w:firstLine=['708','708','708'] ...; incumplen=[#1=708,#2=708,#3=708]`—,
  escondiendo los párrafos realmente mal (567 twips ≈ 1.0 cm). El equipo ya
  tenía documentado (`EVALUADO:`) que las 5 plantillas oficiales usan
  708 (cuerpo) / 709 (portada), no 720.
- **Decisión (en conjunto con el usuario)**: tolerar 1.25 cm. Se implementó un
  mecanismo general y opt-in: campo **`tolerancia`** (twips) en la sección
  `atributo_xml` (DSL) y en el check `xml_atributo` (legacy). El valor cumple
  si `|valor - esperado| <= tolerancia`; si el valor o el esperado no son
  numéricos, se mantiene la igualdad exacta. `tolerancia: 12` cubre 708/709
  frente a 720.
- **Implementación**:
  - `validator/checks.py`: rama `xml_atributo` con el helper `_acepta()`
    aplicado a `eq`/`all_eq` y al filtrado de `incumplen`.
  - `validator/analizadores.py`: misma lógica en `AnalizadorXML`, con el mismo
    formato de `found` para que la paridad siga comparando literal.
  - `reglas_unt.yaml`: `tolerancia: 12` en `sangria_parrafo` + comentario
    `EVALUADO:` del desvío plantilla vs manual.
  - `unt_format_rules_schema.yaml`: `tolerancia: 12` en el check y nota
    actualizada.
  - `docs/DSL.md`: documentado `tolerancia` en `atributo_xml`.

### 2026-10-12 — Autores de carátula en "altas y bajas"

- **Diagnóstico**: la regla tiene dos comprobaciones: run del autor **sin
  negrita** (`not_exists`) y patrón de texto **todo mayúsculas**
  (`^[A-ZÁÉÍÓÚÑ0-9 .,-]+$`). En Linares el nombre completo es
  "Br. Linares Azañero, Angie Lizbeth" (altas y bajas) y marcaba
  `textos=4 incumplen=3`; los runs del nombre incluyen minúsculas y fallaban.
- **Decisión (en conjunto con el usuario)**: validar **altas y bajas**
  (mayúsculas y minúsculas), sin negrita. Es lo que usan las tesis reales
  aprobadas y el placeholder de la plantilla. Se documentó como desvío
  `EVALUADO:` frente a la cita del manual ("letras mayúsculas", párr. 179).
- **Implementación**:
  - Patrón en ambos YAML:
    `^((.*[a-záéíóúñ].*)|[^A-ZÁÉÍÓÚÑa-záéíóúñ]*)$` con `comparacion: fullmatch`
    y `coincidencia: todos`. Rechaza los fragmentos con letras que no tengan
    ninguna minúscula (todo mayúsculas) y **no penaliza** los `w:t` sin letras
    (una coma o un espacio que Word parte en un run propio), que era el falso
    positivo que dejaba `incumplen=1` en el nombre real.
  - `descripcion` y `valor_esperado` actualizados a "altas y bajas, sin
    negrita" en `reglas_unt.yaml` y `unt_format_rules_schema.yaml`; se conserva
    el `rule_id` (identificador de máquina).
  - La comprobación de negrita (`not_exists`) queda intacta.

### 2026-10-12 — Tests y verificación

- `tests/_docx_builder.py`: el autor del doc bueno pasa a mixta
  ("Ana María Pérez García"), acorde a la regla; la mutación de la regla solo
  conmuta la negrita, así que sigue siendo efectiva.
- `tests/test_paridad_formatos.py`: el autor del doc conforme pasa a mixta
  para seguir cumpliendo la regla.
- `tests/test_tipo_documento.py`: la plantilla oficial deja de marcar autores;
  queda **1 error real** (palabras clave) en vez de 2.
- **Verificación**: suite completa **397 tests pasan**; `ruff check`,
  `ruff format --check` y `mypy` limpios; paridad legacy↔DSL verde. En la tesis
  real de Linares: `sangria_parrafo` solo marca los 3 párrafos de 567 twips
  (`incumplen=[#183=567, #196=567, #198=567]`) y `caratula_autores_...` pasa
  (`cumple`).

### 2026-10-12 — Definición del módulo de IA local (discusión + diseño)

- **Contexto**: se abrió la discusión de un **módulo de IA** en el producto. El
  plan de pasantía original quedó descartado por el usuario; lo relevante es
  que "debe haber un módulo de IA".
- **Discusión** (capturada en `docs/discusion_modelo_ia.md`): usuario = **el
  encargado** (no el estudiante); 7 funcionalidades planteadas y extendidas; el usuario
  deja en la mesa las funcionalidades **1** (validación semántica), **2** (explicación y
  priorización), **3** (clasificación asistida) y **5** (redacción de
  respuesta); descarta **4** (RAG), **6** (auto-fix) y **7** (herramienta
  interna de desarrollo).
- **Decisiones tomadas** (v0.4 del doc de discusión): LLM **local**; modelo
  serie **Qwen2.5** (3B CPU / 7B GPU, Q4_K_M); **Ollama como servicio aparte**;
  orden **2 → 3 → 5 → 1**; base común `LLMClient` + `StubLLM` para CI; regla de
  oro: la salida de IA **jamás** toca el semáforo.
- **Diseño** (`docs/diseno/16_modulo_ia.md`, el segundo doc escrito antes de
  implementar): arquitectura con el motor determinista intacto, contrato API
  v1.5.0 aditivo, DTOs advisory, seguridad/privacidad (tesis local, funcionalidades 2/3/5
  sin leerla), testing con `StubLLM` (CI sigue verde sin GPU), plan por pasos y
  coordinación con I1 (backend) e I2 (frontend).
- **Guardado**: se propuso commitear; el usuario confirmó "documentar y diseñar
  primero", sin implementar aún.

### 2026-10-12 — Implementación del módulo de IA: Paso 0 + Funcionalidad 2 (motor)

- **Decisiones del usuario**: construir **Paso 0 + Funcionalidad 2**; modelo por defecto
  **`qwen2.5:3b`** (CPU, configurable a 7B); **solo el motor** (la API va en un
  HANDOVER para I1); **aprobado** levantar la restricción "sin LLM en runtime"
  de AGENTS/README (queda como módulo local advisory).
- **`validator/llm.py`** (Paso 0): `LLMConfig.desde_entorno()`, protocolo
  `LLMClient` (`modelo`, `chat`, `disponible`), `OllamaClient` (httpx async a
  `/api/chat` con `format="json"`), `StubLLM` (determinista, sin red),
  `get_llm_client()` (lanza `LLMNoDisponible` sin `OLLAMA_URL`) y `estado_ia()`
  (nunca lanza). Errores: `ErrorIA` / `LLMNoDisponible` / `LLMError`.
- **`validator/asistente.py`** (Funcionalidad 2): dataclasses advisory `Explicacion` /
  `Prioridad` / `ExplicacionYPrioridad`; `construir_prompt_explicar()` (solo el
  bloque de fallos, **nunca la tesis**); `parse_explicacion()` con validación
  estricta y descarte de `rule_id` inventados; `explicar_y_priorizar()` con
  **un reintento** ante JSON no interpretable (`RespuestaIAInvalida`).
- **Tests** (`tests/test_llm.py`, `tests/test_asistente.py`): 41 tests con
  `StubLLM`/`httpx.MockTransport`, sin red. La suite pasa de **397 a 438**.
- **Sin dependencias nuevas**: `httpx` ya estaba en `flake.nix`; `OLLAMA_*` son
  configuración (no secretos), así que `verificar_secretos.py` no cambia.
- **HANDOVER** `docs/HANDOVER_API_IA.md`: contrato exacto para I1 (DTOs,
  endpoints `GET /asistente/estado` y `POST /asistente/explicar`, códigos
  503/422, inyección del cliente para tests).

---

### 2026-10-13 — Benchmark con tesis reales (primer trabajo del motor)

- **Script** `scripts/benchmark_tesis.py`: corre el motor de producción sobre
  una carpeta de `.docx` y reporta (a) semáforo y fallos por documento, y
  (b) agregado por regla ("reglas que pasan en la práctica"); opción `--json`
  para volcar la medición.
- **Corpus**: `recursos/tesis/` (gitignored) con la tesis real de Linares.
- **Resultado sobre la tesis real** (43 evaluadas): semáforo **rojo** —
  1 `error` (`estructura_tinv_cuantitativo`) y 5 `warning`
  (`anexos_minimos_cuantitativo`, `caratula_optar_grado_tamano`,
  `caratula_titulo_trabajo_tamano`, `indice_apunta_secciones`,
  `sangria_parrafo`). Los fallos quedan listados para revisión manual, para
  distinguir defectos reales de posibles falsos positivos.
- **Tests** `tests/test_benchmark.py` (2 tests, con el doc bueno del factory).

### 2026-10-13 — Detección de track changes (segundo trabajo del motor)

- **Regla nueva** `track_changes_sin_resolver` (warning) en `reglas_unt.yaml`:
  sección DSL `conteo_nodos` con `xpath: //w:ins | //w:del` y
  `cantidad_maxima: 0`. Advierte si el documento trae cambios con seguimiento
  sin aceptar/rechazar. El manual no menciona "control de cambios"; es una
  advertencia de calidad documental (no bloquea el semáforo).
- **Sincronización de la cadena de tests**: `tests/_mutations.py` (mutación
  `cambios_seguimiento`), `tests/_docx_builder.py` (inyecta `w:ins`/`w:del` en
  el cuerpo conservando el formato) y `tests/test_propiedad.py` (49 reglas).
- **Conteos actualizados** a 49 reglas / 43 evaluadas / 445 tests en `README.md`,
  `AGENTS.md`, `docs/CONTRATO_API.md`, `docs/DSL.md`, `docs/diseno/*` y
  `docs/PLAN_BACKLOG_FUTURO.md`; `docs/openapi_spec.json` regenerado.
- **Verificación**: `pytest tests/ -q` → **445 passed**; ruff y mypy limpios;
  `generate_openapi.py --check` en sync; benchmark sobre la tesis real (43
  evaluadas, `track_changes_sin_resolver` pasa porque no hay cambios con
  seguimiento).

### 2026-10-13 — Explicabilidad de los fallos (tercer trabajo del motor)

- **Traza humanizada** en el `found` de las reglas de autómata fallidas: los
  `nombre` de máquina se traducen a la etiqueta `original`/`patron` del estado y
  se omite el estado inicial implícito `__inicio__`
  (`compilador._etiquetas_estados` + `_detalle_con_traza`). Antes:
  `... ruta=__inicio__ -> jurado_evaluador -> ... -> el_problema`; ahora:
  `... reconoció=Jurado evaluador → Índice → … → El Problema`.
- **Faltantes legibles**: `_faltantes_legacy` recorta la indentación de las
  etiquetas (`'    Situación problemática'` → `'Situación problemática'`).
- **Tests** `tests/test_explicabilidad.py` (9 tests): etiquetas (con/sin
  `original`), traza en fallo, ausencia de traza al pasar, fallback del PDA y la
  regla real `estructura_tinv_cuantitativo` sobre el doc mutado.
- **Sin tocar el contrato**: la traza sigue embebida en `encontrado` (decisión
  F5, Opción A); no se agrega campo a la API.
- **Verificación**: `pytest tests/ -q` → **454 passed**; ruff y mypy limpios.

### 2026-10-13 — Ubicación de NotaPie por página (cuarto trabajo del motor)

- **Enriquecimiento real**: `AnalizadorNotaPie` ahora consulta los nodos
  `w:footnoteReference` (no solo sus `@w:id`) y fija `ultimo_nodo` en la
  primera referencia, de modo que `compilador.ejecutar()` anexa `; página N` a
  la `location` del fallo. Ej.: `Notas al pie (pies de página del cuerpo);
  página 4`. Sin fallo no se enriquece.
- **Corrección de un test vacuo**: `test_fallo_de_notas_enriquece_ubicacion_con_pagina`
  pasaba por la palabra "página" del texto fijo de la ubicación; ahora verifica
  el sufijo `; página N` con regex, y se añadió `test_notas_que_pasan_no_llevan_pagina`.
- **Verificación**: `pytest tests/ -q` → **455 passed**; ruff y mypy limpios.

### 2026-10-13 — Funcionalidad 3 del módulo de IA: clasificación asistida (motor)

- **Contexto**: siguiente paso del orden **2 → 3 → 5 → 1**
  (`docs/diseno/16_modulo_ia.md` §10). La Func 2 ya estaba en el motor; se
  implementa el motor de la Func 3 con el mismo patrón (advisory, `StubLLM`,
  sin red).
- **`validator/asistente.py`**: `EvidenciaClasificacion` (estado, catálogo de
  tipos, tipo detectado, detalle de la heurística, títulos) y
  `ClasificacionPropuesta` (tipo propuesto, confianza, justificación,
  evidencia, alternativas); `construir_prompt_clasificar()` (solo evidencia
  determinista, **nunca la tesis**), `parse_clasificacion()` estricto (rechaza
  tipos fuera del catálogo, acota la confianza a [0,1], filtra evidencia y
  alternativas) y `proponer_clasificacion()` con un reintento ante JSON no
  interpretable. El esquema JSON usa el catálogo como `enum`.
- **Human-in-the-loop**: la IA **propone** el tipo; el encargado confirma o
  corrige y re-valida (`POST /validar?tipo_confirmado=`, endpoint pendiente de
  I1). La propuesta nunca cambia el tipo por sí sola.
- **Tests** `tests/test_asistente_clasificacion.py` (19 tests): prompt/sin
  fuga de texto, torturas de parseo (tipo inventado, confianza inválida,
  filtrado de alternativas/evidencia), e2e con `StubLLM`, reintento, error de
  servicio sin reintentar, vallas Markdown y ausencia de catálogo. La suite pasa
  de **455 a 474**.
- **HANDOVER** `docs/HANDOVER_API_IA.md`: añadida la firma del motor (§1.2),
  cómo armar la evidencia desde el reporte, los tests del endpoint
  `POST /asistente/clasificar` (§4) y el pendiente actualizado (§6). El diseño
  (`docs/diseno/16_modulo_ia.md` §10) marca el paso 2 como hecho en el motor.

### 2026-10-13 — Funcionalidad 5 del módulo de IA: redacción de la respuesta (motor)

- **Contexto**: tercer paso del orden **2 → 3 → 5 → 1**. Se implementa el motor
  de la Func 5 con el mismo patrón advisory (sin red, `StubLLM`).
- **`validator/asistente.py`**: `RedaccionRespuesta` (texto, asunto);
  `construir_prompt_redactar()` (solo el bloque de fallos, **nunca la tesis**,
  ordenado por severidad con `_orden_para_redaccion`: errores antes que avisos),
  `parse_redaccion()` estricto (texto y asunto no vacíos) y `redactar_respuesta()`
  con un reintento ante JSON no interpretable. Sin fallos, no llama a la IA
  (no hay nada que comunicar).
- **Regla dura**: la IA solo usa los fallos del reporte (prohibido inventar
  observaciones) y produce un **borrador editable**; el envío sigue siendo el
  flujo SMTP de `notificacion.py` (I1), no se automatiza aquí.
- **Tests** `tests/test_asistente_redaccion.py` (16 tests): orden por severidad,
  ausencia de texto de tesis, torturas de parseo, e2e con `StubLLM`, reintento,
  error de servicio sin reintentar, vallas Markdown y caso sin fallos. La suite
  pasa de **474 a 490**.
- **HANDOVER** `docs/HANDOVER_API_IA.md`: firma del motor (§1.3) y tests del
  endpoint `POST /asistente/redactar` (§4); diseño e índice actualizados.

---

## Evidencias producidas

- Motor: `validator/checks.py` y `validator/analizadores.py` (campo
  `tolerancia` en las comparaciones de atributo, aplicado en ambos motores).
- Reglas: `reglas_unt.yaml` y `unt_format_rules_schema.yaml`
  (`tolerancia: 12` en `sangria_parrafo`; patrón "altas y bajas" en
  `caratula_autores_mayusculas_sin_negrita`; notas `EVALUADO:`).
- Regla de track changes: `track_changes_sin_resolver` en `reglas_unt.yaml`
  (sección `conteo_nodos`), con mutación en `tests/_mutations.py` y soporte
  `w:ins`/`w:del` en `tests/_docx_builder.py`.
- Benchmark: `scripts/benchmark_tesis.py` y `tests/test_benchmark.py`.
- Explicabilidad: `validator/compilador.py` (`_etiquetas_estados`,
  `_detalle_con_traza`) y `tests/test_explicabilidad.py`.
- Ubicación de NotaPie por página: `validator/analizadores.py`
  (`AnalizadorNotaPie.ultimo_nodo`) y `tests/test_f2_notaspie.py`.
- Tests: `tests/_docx_builder.py`, `tests/test_paridad_formatos.py`,
  `tests/test_tipo_documento.py`.
- Documentación: `docs/DSL.md` (campo `tolerancia`) y esta bitácora.
- Módulo de IA (motor): `validator/llm.py`, `validator/asistente.py` (Func 2,
  Func 3 y Func 5) y sus tests (`tests/test_llm.py`, `tests/test_asistente.py`,
  `tests/test_asistente_clasificacion.py`, `tests/test_asistente_redaccion.py`);
  contrato para I1 en `docs/HANDOVER_API_IA.md`; diseño actualizado en
  `docs/diseno/16_modulo_ia.md` y registrado en `docs/diseno/00_indice_diseno.md`.
- Medición con documento real (no versionada; los DOCX/PDF de estudiantes
  quedan fuera del repo).

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: mecanismo reutilizable (tolerancia) en lugar
  de un parche puntual, con tests de paridad entre dos motores.
- **Estructura de Datos**: recorrido de nodos XML y comparación numérica de
  atributos (`firstLine` en twips) con margen de tolerancia.
- **Ingeniería de Software I**: documentación del desvío manual vs práctica
  real (`EVALUADO:`) y sincronización de la documentación del DSL.
- **Inteligencia Artificial II**: LLM local con salida JSON estructurada y
  validada; el asistente es advisory y no decide el resultado.
- **Redes de Computadoras I**: cliente HTTP async (`httpx`) contra el servicio
  Ollama local, con timeouts y manejo de errores de estado.

---

## Dificultades y aprendizajes

- **La puntuación también es un run**: exigir "alguna minúscula" por `w:t`
  penalizaba la coma que Word aísla en su propio run. El patrón se ajustó para
  aceptar los `w:t` sin letras y seguir rechazando los fragmentos todo
  mayúsculas.
- **Tolerar sin aflojar**: `tolerancia: 12` deja pasar 708/709 (1.25 cm) pero
  sigue marcando 567 (1.0 cm), así que no se pierde la detección real.
- **Paridad literal**: cualquier cambio en `found` obliga a tocar los dos
  motores con el mismo formato; el test de paridad sobre documentos sintéticos
  y la medición sobre la tesis real lo confirman.
- **La IA no debe inventar reglas**: el parser descarta las entradas cuyo
  `rule_id` no esté entre los fallos reales, y el prompt solo recibe el reporte
  (nunca la tesis). Así el asistente ayuda sin abrir la puerta a observaciones
  que el motor no detectó.
- **CI sin GPU ni red**: `StubLLM` y `httpx.MockTransport` permiten probar todo
  el módulo (incluidos errores de servicio y JSON inválido) sin descargar un
  modelo; el CI sigue verde.

---

## Próximos trabajos del motor

Acordados con el usuario tras contrastar los ítems pendientes con el manual
oficial. Cada uno se implementa en su **commit atómico**:

1. **Benchmark con tesis reales** ✅ (2026-10-13): `scripts/benchmark_tesis.py`
   + `tests/test_benchmark.py`; corpus en `recursos/tesis/` (gitignored) con la
   tesis de Linares; medición con `--json`.
2. **Detección de track changes** ✅ (2026-10-13): regla
   `track_changes_sin_resolver` (warning) — `conteo_nodos` con
   `xpath: //w:ins | //w:del` y `cantidad_maxima: 0`; mutación y builder de
   tests sincronizados.
3. **Explicabilidad de los fallos** ✅ (2026-10-13): la traza `ruta_estados`
   se humaniza en el `found` (etiquetas `original`/`patron`, sin `__inicio__`),
   sin IA y sin cambiar el contrato.
4. **Ubicación de NotaPie por página** ✅ (2026-10-13): `AnalizadorNotaPie`
   fija `ultimo_nodo` en la primera `w:footnoteReference` y el motor anexa
   "; página N" a la `location` del fallo; test vacuo corregido.

---

## Plan de la semana siguiente

1. Revisar con el usuario cualquier otro desvío menor plantilla vs manual que
   aparezca con nuevos documentos reales.
2. Validar el comportamiento con un segundo documento real cuando esté
   disponible.
3. **Módulo de IA**: el Paso 0 y las Funcionalidades 2, 3 y 5 (motor) ya están
   (`validator/llm.py`, `validator/asistente.py`). Coordinar con I1 el *wiring*
   de `GET /asistente/estado`, `POST /asistente/explicar`,
   `POST /asistente/clasificar` y `POST /asistente/redactar`
   (`docs/HANDOVER_API_IA.md`) y con I2 los botones del frontend; luego seguir
   con la funcionalidad 1 (validación semántica).
