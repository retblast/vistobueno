# Auditoría de comportamiento — VistoBueno

**Fecha:** 2026-10-26
**Alcance:** app completa (motor DSL, API, buzón/ficha, frontend, exportación, CI).
**Método:** lectura de código con evidencia archivo:línea + verificación dinámica contra una tesis real de octubre 2026 (copia local fuera del repo; **no commitear**: contiene datos personales de estudiantes; los nombres citados como evidencia en este documento van anonimizados).
**Ubicación:** `docs/AUDIT_COMPORTAMIENTO_VISTOBUENO_2026-10-26.md` (versión aprobada para el repo).
**Estado del repo:** sin modificaciones durante la auditoría. Los archivos de trabajo viven en `/tmp/auditoria/`.

---

## Cómo leer este documento

- **Severidad:** `alta` (afecta veredictos o bloquea un flujo operativo), `media` (afecta la calidad del resultado o tiene riesgo operativo real), `baja` (pulido, docs, asperezas), `info` (registro, sin acción).
- **Estado:** `confirmado` (evidencia verificada), `decisión` (requiere una decisión de dominio del equipo), `pendiente conocido` (ya anotado antes en AGENTS/TODOs).
- **Responsable:** área dueña de los archivos según la tabla de roles del `AGENTS.md` (Int1 = Backend/API, Int2 = Frontend, Int3 = Motor).

## Resumen

27 hallazgos: **4 altos, 10 medios, 10 bajos, 3 informativos** (los AUD-24 a 27 salieron de la pasada 2: traza instrumentada del motor, ver Adenda). El núcleo está sano: el semáforo se calcula bien, los flujos best-effort (correo, DSpace) nunca rompen la respuesta, y los hallazgos de revisión previos (B3-B6, 14, 16a/16b) están efectivamente corregidos. Los problemas reales se concentran en cuatro frentes:

1. Dos bugs del motor descubiertos contra una tesis real (AUD-01, AUD-02) — invisible para la suite porque el factory no replica la estructura de las plantillas (AUD-20).
2. El texto `encontrado` es ilegible y señala mal (AUD-03); se propaga al correo, los prompts IA, el exportador y la UI.
3. La superficie ficha/buzón no tiene autenticación y expone datos personales en la red (AUD-09), y su pantalla en la SPA no existe (AUD-16).
4. Asperezas de contrato (nombre del archivo depositado, content-type, mocks desactualizados).

| ID | Sev | Estado | Área (resp.) | Hallazgo |
|----|-----|--------|--------------|----------|
| AUD-01 | alta | confirmado | Motor (Int3) | `indice_apunta_secciones` falso positivo: `_norm_indice` come la "l" final de títulos sin página |
| AUD-02 | alta | confirmado | Motor (Int3) | `anexos_minimos_*` reporta los 9 ítems como faltantes: sección vacía + títulos excluidos + truncado |
| AUD-03 | media | confirmado | Motor (Int3) | `encontrado` ilegible ("@w:val=…"), valores conformes primero, culpables truncados, "página N" del primer nodo |
| AUD-04 | media | confirmado | Motor (Int3) | Desvíos manual-vs-plantilla (título 14/13pt) sin nota EVALUADO en el YAML |
| AUD-05 | media | decisión | Motor (Int3) | Muestreo frágil en reglas de carátula (`/w:r[1]`, `following-sibling[1]`) |
| AUD-06 | baja | decisión | Motor (Int3) | Heurística del índice: sig < 4 chars auto-pasa; match por subcadena puede ocultar faltantes |
| AUD-07 | baja | decisión | Motor (Int3) | `caratula_optar_grado_tamano` aplica a cualquier línea "para optar", no solo a la del Bachiller |
| AUD-08 | info | registro | Motor (Int3) | Detección por firmas es heurística 2-de-3 (documentada en el YAML) |
| AUD-09 | media | confirmado | API (Int1) | Buzón/ficha sin autenticación: PII legible en la red; la ranura se puede pisar |
| AUD-10 | baja | confirmado | API (Int1) | Buzón en memoria: exige exactamente 1 worker; falta nota de despliegue |
| AUD-11 | media | confirmado | API (Int1) | El depósito sube el .docx con nombre temporal (`tmpXXXX.docx`) |
| AUD-12 | media | pendiente conocido | API (Int1) | POST /validar sin rate-limit ni auth (ya listado en AGENTS) |
| AUD-13 | baja | confirmado | API (Int1) | 415 por content-type más estricto que la validación del frontend |
| AUD-14 | info | registro | API (Int1) | Sintaxis PEP 758 exige Python ≥ 3.14 (anclado en flake y CI) |
| AUD-15 | media | confirmado | Motor (Int3) | Exportador inyecta texto del documento sin escapar en Markdown→HTML→PDF |
| AUD-16 | alta | confirmado | Frontend (Int2) | La pantalla de ficha de depósito (handover S8) no existe en la SPA |
| AUD-17 | baja | confirmado | Frontend (Int2) | mocks.js desactualizado (mezcla twips de sangría con márgenes) |
| AUD-18 | baja | decisión | Frontend (Int2) | Fallback a MOCK_REPORT (reporte falso avisado) activo también en producción |
| AUD-19 | baja | confirmado | Docs | AGENTS "Próximos pasos" desactualizado: AbortController ya está implementado |
| AUD-20 | media | confirmado | Tests (Int3) | Brecha factory-vs-realidad: la suite no replica la estructura de anexos ni títulos con "l" final |
| AUD-21 | baja | pendiente conocido | Tests (Int1) | Test de paridad vacuo (pendiente en AGENTS) |
| AUD-22 | baja | confirmado | Scripts | verificar_secretos cubre 3 nombres de variables y asignaciones de una línea |
| AUD-23 | info | confirmado | Proceso | Archivos sin trackear de otra sesión en el árbol de trabajo |

---

## Detalle de hallazgos

### AUD-01 — Falso positivo en "índice apunta a secciones" (alta)

`_norm_indice` (`validator/analizadores.py:548`) borra del final del texto un supuesto número de página en romano minúscula (`[ivxlc]{1,5}`). Los títulos del CUERPO no llevan página, así que pierden su última letra cuando esta es i/l/v/x/c: "General" → "GENERA". Las entradas del índice sí llevan página arábiga al final, que protege la palabra: "1.2.1.General18" → "GENERAL". El match ("GENERAL" como subcadena de algún título) falla contra "GENERA".

**Evidencia (tesis real):** el cuerpo tiene los headings `General` (Ttulo3, págs. 26 y 27, bajo "Objetivos" e "Hipótesis"); el índice los lista como `1.2.1. General … 18` y `1.3.1. General … 19` (los tabs desaparecen en `text_of`). 46 de 48 entradas matchean; solo estas dos fallan. El conjunto de títulos normalizados contiene literalmente `GENERA`.

**Impacto:** warning falso hacia el estudiante por una clase entera de títulos ("General", "Perfil", "…cultural", "…civil").

**Fix propuesto:** separar la normalización: los títulos del cuerpo usan una variante SIN borrar números de página (que nunca traen); las entradas del índice mantienen la actual. Test de regresión: título "General" + entrada con página arábiga.

### AUD-02 — anexos_minimos_* no ve los anexos reales (alta)

Tres defectos apilados:

1. La regla declara `seccion: {inicio: anexo}` sin `fin` (`reglas_unt.yaml:1187-1191`), y `seccion()` corta en el PRIMER título posterior (`validator/tokenizer.py:162-163`). La estructura real (plantilla oficial incluida) es `Anexos` (Ttulo1) seguido inmediatamente de `Anexo 1. …` (Ttulo1) → el slice queda VACÍO (0 tokens, verificado).
2. `AnalizadorListaObligatoria._texto()` (`validator/analizadores.py:367`) solo junta tokens `PARRAFO`: los textos de los títulos "Anexo N. <ítem>" nunca se buscan.
3. `faltan[:8]` (`validator/analizadores.py:388`): con los 9 ítems "faltantes", el mensaje muestra 8 y esconde el noveno.

**Evidencia (tesis real):** el documento trae Anexos 1-8 como Ttulo1. Existen de verdad: Matriz de consistencia, Instrumento(s) de recolección de datos, Ficha técnica del instrumento, Consentimiento informado. Ausentes de verdad: Base de datos "cuantitativa" (el doc dice "Base de datos"), Reporte de similitud, Carta de autorización institucional, Declaración jurada, Carta de autorización de publicación. El reporte decía que faltaban los nueve.

**Impacto:** la regla no puede pasar ni con la plantilla oficial (su propia lista de anexos difiere del manual). El hallazgo pierde toda credibilidad.

**Fix propuesto:** (a) permitir que la sección corra hasta el final del documento (extensión pequeña y documentada de `seccion()`, p. ej. `hasta_final: true`, registrada en `dsl_check.py` y `docs/DSL.md`); (b) incluir los textos de TITULO en el texto buscado; (c) mostrar todos los faltantes + conteo de hallados. Sincronizar `tests/_mutations.py` (regla 5 del AGENTS).

### AUD-03 — El campo "encontrado" es ilegible y señala mal (media)

`AnalizadorXML` arma el detalle como `@w:val=['26'] esperado=28` (`validator/analizadores.py:167`). Para `all_eq` fallido muestra primero `vals[:3]` —que suelen ser valores CONFORMES— y después `incumplen[:3]` con referencias `#200` sin página (`:169-171`). El propio comentario del código admite el problema (handover issue #7, arreglado a medias). Además, la "página N" de `ubicacion` sale del PRIMER nodo del xpath (`validator/compilador.py:599-610`), no del que falla.

**Evidencia (sangría):** el mensaje abre con `['708','708','708']` (valores que SÍ pasan con la tolerancia de 12 twips) y esconde el 4º culpable. Hizo creer que la tolerancia 1.25 cm (commit `7ff5cd3`, verificado EN master y funcionando) "no había llegado". Culpables reales: 4 párrafos con 567/284 twips (págs. 49-50).

**Propagación:** DTO `encontrado` → correo al estudiante (`validator/notificacion.py:163`), prompts IA (`validator/prompts.py:14`), exportador (`validator/exportador.py:66`), frontend (`frontend/src/components/Report.jsx:560` lo imprime tal cual). La UI no puede arreglarlo: nunca recibe datos estructurados.

**Fix propuesto:** reescribir el detalle (culpables primero, con página, rango de tolerancia, "13pt (se esperaba 14pt)" para `w:sz`) y espejarlo en `validator/checks.py:76-80` porque la paridad compara el texto `found` (`tests/test_paridad_formatos.py:368`) — mismo patrón del commit `7ff5cd3` — o mover esas reglas a `solo_passed`.

### AUD-04 — Desvíos manual-vs-plantilla sin nota EVALUADO (media)

`caratula_titulo_trabajo_tamano` (esperado 14pt) y `caratula_optar_grado_tamano` (esperado 13pt) son `warning` por un desvío real: la plantilla oficial usa 13pt y 12pt en esos dos elementos (verificado en `recursos/EDUCACION INICIAL-PLANTILLA INVESTIGACIÓN CUANTITATIVA.docx`, párrafos con `w:sz` 26 y 24). La tesis real copió la plantilla. El YAML no lleva nota `# EVALUADO:` — a diferencia de `sangria_parrafo` (`reglas_unt.yaml:425-426`), que sí la tiene.

**Fix:** notas EVALUADO con fecha y decisión en `reglas_unt.yaml:223-256`.

### AUD-05 — Muestreo frágil en reglas de carátula (media, decisión)

Las reglas leen `/w:r[1]` (primer run) y `following-sibling::w:p[1]` (primer párrafo siguiente). Un run de espacios/tab inicial, un ORCID intercalado entre "AUTORES:" y el primer autor, o un segundo autor con otro tamaño desviarían o saltarían la muestra. Hoy correcto en la plantilla y en la tesis real (el xpath del título hasta acertó saltándose la línea "TESIS"), pero el historial (handover #3, #4) muestra que esta familia de selectores ya rompió contra tesis reales.

**Decisión:** endurecer (leer todos los runs con texto; validar todos los párrafos de autores) o documentar la limitación en el YAML.

### AUD-06 — Límites de la heurística del índice (baja, decisión)

`_sigpalabra` ≥ 4 caracteres: una entrada cuya primera palabra significativa es corta nunca se marca (auto-pasa, `validator/analizadores.py:655`). El match por subcadena puede ocultar una sección faltante cuyo sig aparece dentro de otro título. Documentar los límites o endurecer (igualdad del título completo normalizado cuando existe).

### AUD-07 — Alcance de `caratula_optar_grado_tamano` (baja, decisión)

El xpath casa cualquier línea con "para optar" — incluida "Para Optar el Título Profesional de Licenciado…", que la plantilla pone en 12pt — pero la cita normativa (párr. 178) es de la línea "Trabajo de Investigación para optar el grado de Bachiller". Decidir: restringir el patrón a la línea del Bachiller, o aceptar 12pt para la variante Título Profesional con nota EVALUADO.

### AUD-08 — Detección por firmas: heurística asumida (info)

`tinv_cuantitativo` requiere 2 de 3 evidencias genéricas (`reglas_unt.yaml:125-127`); el orden de especificidad lo protege (los tipos específicos se evalúan antes) y los trade-offs están documentados en el YAML. Una tesis degenerada puede misdetectarse y validarse contra el esquema equivocado. Sin acción; registro.

### AUD-09 — Buzón y ficha sin autenticación (media)

`GET /ficha-pendiente` (`validator/api.py:668-686`) entrega título, autores, asesor, resumen y — cuando el operador llena los manuales — DNI y ORCID a cualquier cliente de la red. `POST /ficha-pendiente` y `POST /deposito` sobreescriben la ranura ("última gana"): un tercero puede pisar la ficha en vuelo. La justificación "sin CORS" (`validator/buzon.py:20-24`) solo cubre páginas web en el navegador del operador; no cubre `curl` ni otros hosts de la LAN.

**Fix propuesto:** token compartido (header) entre SPA, API y userscript, o bind a localhost en producción; anotar el requisito en el handover del userscript.

### AUD-10 — Buzón en memoria: requisito de 1 worker sin documentar (baja)

Multi-worker uvicorn rompe el flujo en silencio (publicar en un worker, leer en otro → 404); un reinicio pierde la ficha. El supuesto está documentado en `validator/buzon.py:14-16`, pero el requisito "exactamente 1 worker" no aparece en la documentación de despliegue. **Fix:** nota en README/handover.

### AUD-11 — El depósito sube el archivo con nombre temporal (media)

El request guarda el upload en `NamedTemporaryFile` (`validator/api.py:467-469`) y deposita ese path (`:617-622`); `crear_workspaceitem` usa `archivo.name` (`validator/dspace.py:329-333`). El bitstream del ítem queda como `tmpXXXXXX.docx`: el repositorio pierde el nombre del archivo del estudiante.

**Fix:** renombrar el temporal con el nombre original saneado antes de depositar (reutilizar el criterio de `_nombre_seguro`), o pasar el filename explícito en el multipart.

### AUD-12 — POST /validar sin rate-limit ni auth (media, pendiente conocido)

Ya listado en AGENTS ("Próximos pasos", Int1). El motor recompila el DSL en cada request (`validator/api.py:479-483`) → costo CPU por request; un abuso de la LAN tumba el servicio. Mantener el pendiente; mitigación mínima: limitación en el reverse proxy + documentar el riesgo.

### AUD-13 — Validación de content-type desalineada (baja)

Backend: extensión `.docx` Y content-type en {docx, octet-stream} (`validator/api.py:80-83, 412-420`) → un `.docx` legítimo con `application/zip` recibe 415. Frontend: acepta por MIME O extensión (`frontend/src/components/Upload.jsx:26`) → puede enviar algo que el backend rechaza. Alinear criterios (la verificación de bytes PK ya cubre el caso hostil).

### AUD-14 — Sintaxis PEP 758 (info)

`except TypeError, ValueError:` sin paréntesis en `validator/analizadores.py:152`, `validator/checks.py:67` y `scripts/verificar_secretos.py:103` es válido solo en Python ≥ 3.14 (PEP 758). Anclado: el flake fija 3.14 y la CI lo explica (`ci.yml:24-28`). Riesgo solo para quien ejecute el paquete fuera de nix. **Fix:** nota "Python 3.14+ requerido" en el README.

### AUD-15 — Exportador inyecta texto del documento sin escapar (media)

`reporte_a_markdown` interpola `message/found/expected` en la tabla Markdown sin escapar (`validator/exportador.py:53-74`) y `reporte_a_pdf` pasa el resultado por python-markdown sin escape (`:116-119`), que deja pasar HTML crudo. Un `|` en un título rompe la tabla; contenido hostil del DOCX puede meter HTML al PDF (WeasyPrint además sigue URLs de recursos externos). Consumidores: CLI y scripts. **Fix:** escapar `|` y `<>&` antes de armar el Markdown.

### AUD-16 — La pantalla de ficha de depósito no existe en la SPA (alta)

Grep en `frontend/src`: cero usos de ficha/deposito/constancia; solo el proxy de Vite tiene las 4 rutas (`frontend/vite.config.js:20-32`). El handover `docs/HANDOVER_FRONTEND_FICHA_DEPOSITO.md` sigue pendiente: el flujo S8 (ficha → buzón → userscript → constancia) existe en backend/userscript/e2e, pero los operadores no pueden ejecutarlo desde la app.

**Fix:** implementar la pantalla del handover (Int2): ficha (extraídos + manuales por autor), "Preparar depósito", panel de espera con sondeo del buzón, verificación título-vs-handle, descargas de constancias y registro.

### AUD-17 — mocks.js desactualizado (baja)

`frontend/src/mocks.js:17-18`: `margen_derecho` con "708/709" (son twips de SANGRÍA, ~1.25 cm, no de un margen de 2.5 cm) y `sangria_parrafo` con el formato antiguo del detalle. Tras AUD-03 el mock queda aún más lejos del contrato real. Regenerar desde una respuesta real.

### AUD-18 — Fallback a MOCK_REPORT en producción (baja, decisión)

Si el backend no responde, la SPA muestra un reporte EJEMPLO completo (avisado con banner, `Upload.jsx:166-173, 211, 253`). En la herramienta interna puede confundir al operador. Decidir: mantener como modo demo o desactivar en build de producción (`import.meta.env.PROD`).

### AUD-19 — AGENTS "Próximos pasos" desactualizado (baja)

"AbortController en el upload y foco del dropzone" ya está implementado (`Upload.jsx:184-215`, con timeout de 30 s, y manejo de foco). Actualizar la lista del AGENTS.md.

### AUD-20 — Brecha factory-vs-realidad en los tests (media)

El doc bueno codifica los anexos como párrafos planos (`tests/_docx_builder.py`, `tests/_mutations.py: anexos_items`) y no ejercita títulos terminados en i/l/v/x/c ni entradas de índice con página arábiga: AUD-01 y AUD-02 pasaron con la suite en verde. **Fix:** fixture con la estructura de la plantilla real (`Anexos` + `Anexo N.` como Ttulo) + caso "General"; evaluar si `scripts/eval_contra_plantillas.py` merece un paso en CI.

### AUD-21 — Test de paridad vacuo (baja, pendiente conocido)

Listado en AGENTS (Int1). Priorizarlo junto a AUD-03, que toca la paridad de todos modos.

### AUD-22 — Cobertura del escáner de secretos (baja)

`scripts/verificar_secretos.py:35-45` cubre exactamente 3 nombres de variables y asignaciones de una línea. No cubre otros nombres, URLs con credenciales embebidas ni YAML multilínea. Suficiente para los creds conocidos; anotar la cobertura o ampliar patrones.

### AUD-23 — Archivos sin trackear de otra sesión (info)

`PR55_REVIEW_COMMENTS.md`, `docs/VERIFICACION_LOCAL.md`, `scripts/verify_all.sh` están sin trackear en el árbol (de otra sesión de trabajo, no de esta auditoría). Decidir: commitear, mover o excluir localmente (`.git/info/exclude`).

---

## Verificado y en buen estado

- **Semáforo:** se calcula sobre TODOS los errores, independiente del filtro (`engine.py:176-216`). Reglas n/a no bloquean y se cuentan aparte.
- **Centinelas de detección:** `sin_determinar`/`contradictorio` producen un ERROR bloqueante propio; tipos sin estructura cargada producen warning (`compilador.py:649-794`). No existe el "verde sin estructura" que se podría temer.
- **Upload:** tope 10 MB leído con cota (`api.py:429-443`), firma PK antes de abrir, limpieza del temporal en `finally`, scoping 422/500 (hallazgo B6), zip-bomb limitado a 50 MB por parte (`extractor.py:34-64`).
- **Bloqueantes fuera del event loop:** motor, SMTP y DSpace van al threadpool.
- **Correo:** opt-in + semáforo rojo + validación de email + Subject saneado de caracteres de control + HTML escapado + best-effort nunca-lanza (B4/B5).
- **Constancia/registro:** inyección CSV neutralizada (hallazgo 14), nombres de descarga saneados, BOM UTF-8, la app nunca escribe el registro oficial.
- **DSpace:** CSRF+JWT, best-effort, creds solo de entorno; TODOs de la primera validación real anotados en el propio código.
- **CI:** doble capa de secretos (pre-commit + CI), `nix flake check`, ruff format, OpenAPI `--check` (drift guardado), dist del userscript con drift check, e2e de ficha-deposito. Sin pasos debilitados.
- **Upload.jsx:** AbortController + timeout 30 s, guard de doble envío, a11y razonable (roles, foco, aria).
- **Buzón:** thread-safe (lock), TTL, "última gana" documentados.
- **Tolerancia de sangría:** commit `7ff5cd3` en master, espejado en ambos motores y ambos YAMLs; 708/709 pasan (verificado contra la tesis real).

## Pendientes conocidos (confirmados, sin hallazgo nuevo)

Rate-limit/auth (AUD-12), test de paridad vacuo (AUD-21), plantillas de los 5 tipos pendientes (`reglas_unt_pendientes.yaml`), endpoint de licencia y payload de workflow de DSpace (TODOs en `dspace.py`), buzón institucional definitivo de notificaciones (TODO en `notificacion.py`).

## Decisiones de dominio abiertas (para el equipo)

1. ¿La regla de sangría debe eximir estilos de bloque tipo `Textoindependiente`? (Los 4 párrafos marcados en la tesis real son legítimos según la letra de la regla; discutible según APA.)
2. ¿"Base de datos cuantitativa" debe matchear "Base de datos"? (AUD-02, item 5.)
3. AUD-05 (endurecer selectores de carátula), AUD-06 (heurística del índice), AUD-07 (alcance de la regla del Bachiller), AUD-18 (mock en producción).
4. AUD-09: ¿token compartido o bind localhost para el buzón?

## Plan de acción sugerido (orden)

1. **Motor — correctitud (Int3):** AUD-01 + AUD-02 con tests de regresión de AUD-20. Espejo en `checks.py` solo si toca `found`.
2. **Motor — comunicación (Int3):** AUD-03 + AUD-04 (mensajes legibles + notas EVALUADO), coordinando AUD-21 (paridad) en el mismo PR.
3. **API (Int1):** AUD-11 (nombre del bitstream) — fix chico, alto valor para el repositorio. AUD-09/AUD-10 según la decisión de dominio; AUD-13 de rebote.
4. **Exportador (Int3):** AUD-15 (escapado).
5. **Frontend (Int2):** AUD-16 (pantalla del handover S8); luego AUD-17/AUD-18.
6. **Proceso:** AUD-19, AUD-22, AUD-23; AUD-12 según prioridad de despliegue.

**Verificación de cada paso:** `nix run .#test -- tests/ -v` + `nix flake check`; re-ejecutar la CLI sobre la copia de la tesis real y esperar: índice 48/48, anexos 4 hallados + 5 faltantes reales, mensajes legibles con páginas correctas, semáforo verde.

## Cómo reproducir la evidencia

```bash
# Copia de trabajo (la tesis real NO se commitea: datos personales)
cp "/home/retblast/Downloads/TESIS_..._2026 07-10-2026 (1).docx" /tmp/auditoria/tesis_linares.docx

# Reporte completo
nix develop -c bash -c "python -m validator.cli /tmp/auditoria/tesis_linares.docx reglas_unt.yaml --json"
# (el banner del shellHook contamina stdout: la salida JSON empieza en la línea 18)

# Scripts de evidencia usados en esta auditoría (viven en /tmp/auditoria/):
#   dump_doc.py    — carátula con runs, xpaths exactos, sangría, índice, anexos
#   manual_dump.py — texto del manual oficial + carátula de la plantilla oficial
```

Resultados esperados tras los fixes: ver "Plan de acción", verificación.

---

## Adenda (pasada 2, 2026-10-26): traza instrumentada del motor

Se envolvió cada clase de analizador y el ejecutor de reglas (`ReglaCompilada.ejecutar`/`no_aplicable`) para registrar la ejecución completa contra la tesis real, y se contrastó con el reporte de la CLI y con controles del factory. Scripts: `trace_motor.py`, `probe_ficha.py` (en `/tmp/auditoria/`).

### Resultados de la verificación

| Verificación | Resultado |
|---|---|
| V1 traza vs reporte CLI (43 reglas: veredicto + `found`) | OK, 0 diferencias — el reporte es proyección fiel de la ejecución regla a regla |
| V2 ids del YAML vs resultados | 49 == 49 |
| V3 centinelas inyectados | ninguno (tipo vigente: `tinv_cuantitativo`, nivel inferido, evidencia VARIABLE + INSTRUMENTO) |
| V4 semáforo | verde; fallidos_error=0, fallidos_warning=5 — consistente con el conteo |
| V5 reglas aplicadas | 38/43 pasan; 6 n/a correctas (reglas de otros tipos) |
| V6 anomalías AUD-01..03 | presentes en la traza con la firma exacta documentada |
| Control positivo | doc bueno del factory: 0 fallos de 49 (invariante del AGENTS verificado en vivo) |
| Control negativo ×3 | cada mutación (sangría=0, anexos sin "Reporte de similitud", universidad a 12pt) falla EXACTAMENTE su regla y ninguna más |

Datos de la pasada: 61 llamadas a analizadores (XML 35, Regex 5, Extraccion 7, el resto 1-2 c/u). El DFA de estructura recorrió la tesis real por el esquema cuantitativo y aceptó tras 16 estados: `jurado_evaluador -> indice -> presentacion -> resumen -> abstract -> introduccion -> el_problema -> situacion_problematica -> enunciado_del_problema -> justificacion -> objetivos -> variables -> marco_teorico -> antecedentes -> bases_teoricas`.

**Verificación por accidente:** un bug del propio arnés de traza (slice de un dict de config) reventó dentro de la llamada a 6 analizadores. El motor contuvo cada excepción (`ReglaCompilada.ejecutar`), la convirtió en fallo de la regla con detalle del error y NO rompió el reporte — evidencia empírica del diseño fail-closed. La corrección del arnés devolvió la traza limpia.

### Hallazgos nuevos de la pasada 2 (ficha de depósito, diseño 17)

Tres capturas de `reglas_ficha.yaml` están rotas contra una tesis real (la ficha pre-llena el formulario de DSpace y alimenta constancias y registro):

#### AUD-24 — La captura de autores parte un autor en dos y pierde al segundo (alta)

`reglas_ficha.yaml:50` muestrea UN solo párrafo (`following-sibling[1]` de la línea "AUTORES:") y el `separador: \s*(?:,|;|\by\b|\be\b)\s*` (línea 49) parte por la coma de "Apellidos, Nombres".

**Evidencia (tesis real):** la carátula trae un autor por párrafo. Capturado: `['Br. Apellido', 'Nombre']` — apellidos y nombre del primer autor partidos por la coma: dos "autores" falsos. El segundo autor real jamás se captura. El separador por "y"/"e" también rompería nombres que lo contengan.

**Impacto:** `constancias_por_autor` genera una constancia y una fila por cada "autor" — sobre esta tesis produciría 2 constancias con nombres truncados y ninguna para el segundo autor. Las matrículas alineadas por posición quedan inservibles.

**Fix:** capturar TODOS los párrafos de autor (iterar `following-sibling` hasta párrafo vacío o etiqueta conocida) y partir la lista solo entre párrafos, no dentro de uno.

#### AUD-25 — La captura del asesor llega VACÍA marcada como detectada (media)

`reglas_ficha.yaml:66` toma el primer párrafo que contiene "asesor". En la tesis real la ETIQUETA va en un párrafo propio ("ASESORA:") y el nombre en el siguiente (el nombre de la asesora). El `quitar_prefijo` (línea 65) borra la etiqueta completa y el resultado es `''`.

**Evidencia:** `dc.contributor.advisor detectado=True valor=''`. Además, `compilador._ficha` publica `detectado: True` para CUALQUIER item capturado, aunque el valor sea vacío — incumple el contrato del handover (`detectado=false, valor=null` cuando no hay dato).

**Fix:** preferir el párrafo siguiente a la etiqueta (o exigir contenido no vacío tras limpiar) y publicar `detectado=False` cuando el valor quede vacío.

#### AUD-26 — La captura del año lee "2024" del final del TÍTULO (media)

`reglas_ficha.yaml:101` toma el primer párrafo de carátula que contiene "trujillo" (excluida la línea de la universidad) y extrae el año con `patron \b(?:19|20)\d{2}\b`. Dos cosas fallan a la vez:

1. El título de la tesis real TERMINA en ", Trujillo 2024" — el ancla "trujillo" casa el párrafo del título (párrafo 4, antes que la línea de ciudad) y el año extraído es 2024.
2. La línea del año real ("2026") vive en el párrafo que porta el salto de sección y queda FUERA del contexto "caratula" por diseño (`extractor._caratula_paras` excluye al portador del `w:sectPr`), invisible para cualquier regla con `contexto: caratula`.

**Evidencia (probe):** nodo seleccionado = el párrafo del título, que termina en ", Trujillo 2024"; capturado `dc.date.issued = '2024'` cuando la carátula dice 2026.

**Fix:** anclar el año en la línea de ciudad/año (p. ej. párrafo con "perú" o el último bloque de la carátula) y decidir si el párrafo portador del sectPr debe contar como carátula cuando es la última línea de la portada.

#### AUD-27 — Palabras clave con puntuación final (baja)

`dc.subject` capturó `['Educación', 'Cultura', 'Identidad cultural.']` — el punto de cierre de la línea APA queda pegado a la última clave (`reglas_ficha.yaml:133` parte por `,`/`;` sin limpiar puntuación final). Strip de puntuación al partir.

### Actualización del plan de acción

Insertar antes del paso de frontend: **Motor (Int3) — ficha de depósito:** AUD-24 a AUD-27 en `reglas_ficha.yaml` + `AnalizadorExtraccion`/`compilador._ficha`; tests con la estructura de la tesis real (autores por párrafo, etiqueta en párrafo propio, año en línea propia). La verificación de esta pasada (V1-V6 + controles) queda como método de regresión para cualquier cambio futuro del motor.

### Límites de esta verificación (declarados)

- `GramaticaEstructura` y `AutomataPila` NO se ejecutaron contra esta tesis (0 llamadas): solo los cubren tests sintéticos.
- Las 5 reglas de `reglas_unt_pendientes.yaml` siguen sin probarse contra plantillas reales (documentado).
- SMTP y DSpace se verificaron contra stubs/sink, no contra los servicios institucionales reales.
- La paginación física depende de `w:lastRenderedPageBreak`: documentos exportados por herramientas no-Word pueden degradarla.
- La tesis usada es UNA muestra real; las 5 plantillas de `recursos/` son el siguiente set de control natural.
