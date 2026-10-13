# Discusión — Módulo de IA de VistoBueno

> **Estado**: diseño en discusión. Nada de esto está decidido ni implementado.
> Esta nota captura la conversación para retomarla donde quedó.
> **v0.2 (extendida)**: se expanden todas las funcionalidades con detalle para poder
> leerlas, compararlas y decidir con contexto.
>
> **v0.3 (2026-10-12, recorte del usuario)**: quedan en discusión **las funcionalidades
> 1, 2, 3 y 5**. Las funcionalidades **4 (RAG), 6 (auto-fix) y 7 (herramienta interna)
> se descartan por ahora** (se mantienen documentadas para referencia).
> Todavía **no se implementa nada**.
>
> **v0.4 (2026-10-12, decisiones tomadas — pendiente de diseño)**: el usuario
> delega las decisiones; se fijan como conveniente:
>
> - **Funcionalidades en alcance**: 2, 3, 5 y 1, en **ese orden de implementación**
>   (2 → 3 → 5 → 1). 4, 6 y 7 descartadas.
> - **LLM local**: sí. **Modelo**: serie **Qwen2.5** (3B en CPU / 7B en GPU,
>   cuantizado Q4_K_M).
> - **Despliegue**: Ollama como **servicio aparte** (API compatible OpenAI,
>   `localhost`); los pesos no van al repo ni a `flake.nix`.
> - **Base común**: interfaz `LLMClient` (protocol) + `OllamaClient` +
>   `StubLLM` para CI; endpoint **503 "IA no disponible"** si no hay
>   `OLLAMA_URL` (patrón deshabilitado de la notificación).
> - **Regla de oro**: la salida del LLM **jamás** toca el semáforo ni
>   `RuleResult`; es advisory / human-in-the-loop.
> - El diseño formal queda en `docs/diseno/16_modulo_ia.md`.

---

## 1. Punto de partida

- El `PLAN_PPP_Integrante_3_OCR_IA_VistoBueno.docx` (pasantía) **no aplica** —
  el usuario lo descarta. Aun así, **debe haber un módulo de IA** en el
  producto; hay que **discutir primero** qué debería hacer.
- Hoy el proyecto tiene **una restricción dura de diseño**: validación
  determinista, **sin LLM en runtime** (`README`, `docs/diseno/01_arq_motor.md`
  → D6; `docs/PLAN_BACKLOG_FUTURO.md` → "el módulo de IA queda fuera hasta que
  el integrante lo indique").
- El `validator/prompts.py` actual es solo *templates* "cómo preguntar a una
  IA" para que el usuario pegue en un LLM externo. Decidir si hay módulo de IA
  **= decidir si esa restricción cambia**.

## 2. Usuario objetivo: el encargado

- El módulo **NO es para el estudiante**: es para **el encargado** (operador /
  bibliotecario que administra la validación en la FECyC).
- Esto cambia la naturaleza del módulo: en vez de un "tutor que le explica al
  alumno", es un **asistente del operador**.
- El encargado trabaja así hoy, aproximadamente: recibe la tesis / la valida,
  revisa el reporte (qué reglas fallaron y por qué), decide si la entrega es
  viable, y comunica al estudiante qué corregir. El módulo de IA debe hacer
  **más fácil revisar, decidir y comunicar** — no corregir por el estudiante.

## 3. Revisión: qué hay hoy en el repo (transversal a la discusión)

Lo que hicieron los compañeros y lo que dejamos ya consensuado es la base para
elegir: **nadie implementó un módulo de IA todavía**, pero el equipo dejó
escrito su rumbo.

| Quién | Qué hay hoy | Cómo se relaciona con la IA |
|-------|-------------|------------------------------|
| **I1 — Backend/API** | API `POST /validar` con `incluir_prompts_ia` (templates, semana 2). Aparte: análisis de la API de DSpace (`docs/DSPACE_API.md`, módulo de depósito institucional). | El contrato ya reserva el campo "preguntar a una IA". DSpace es el *post-entrega*; no toca IA. |
| **I2 — Frontend** | Reporte con sección "Cómo preguntar a una IA": tarjetas copiables y filtrables por el buscador (semana 7). | Solo muestra los templates. No hay chat ni IA runtime. |
| **I3 — Motor (nosotros)** | Diagnóstico rico: `tipo_documento`, centinelas (`tipo_documento_no_determinado`, `contradictorio`, `sin_estructura`), `incumplen=[#N=...]` (issue #7), cita del reglamento por regla, `location` con página. | Es **la materia prima** que alimenta cualquier IA: el reporte ya "sabe" qué falló y por qué. |

Rumbos ya consensuados en nuestro propio trabajo (los que el equipo escribió):

- `docs/diseno/15_tipo_documento_grupos.md` (§No-alcance): **el módulo de IA
  (explicación y priorización del diagnóstico) es "Fase C"**, posterior a la
  detección de tipo documental.
- `README.md` (§Extensiones futuras): **checks semánticos con LLM local**
  (Ollama / llama.cpp server, API compatible OpenAI), que corren **después** de
  que el doc pase las reglas deterministas y reciben **solo el fragmento
  relevante + la regla textual**, no el reglamento completo.
- `docs/PLAN_BACKLOG_FUTURO.md`: primero "explicabilidad **sin** IA"
  (traza `ruta_estados` + corrección por template), y la IA queda "fuera hasta
  que el integrante lo indique" — es decir, la activa quien decida hacerla.

**Conclusión de la revisión**: la decisión de usar **LLM local** ya está
adelantada por el equipo, y el rol de la IA ya está definido como **explicación
y priorización del diagnóstico**. Las funcionalidades que siguen se evaluan contra eso.

---

## 4. Menú de funcionalidades (extendidas)

> Cada funcionalidad indica: qué es · quién/momento · cómo funcionaría · dónde vive ·
> LLM local · ventajas · desventajas/riesgos · esfuerzo · encaje.
>
> **En discusión**: funcionalidades 1, 2, 3 y 5. **Descartadas por ahora**: funcionalidades 4, 6 y 7.

---

### Funcionalidad 1 — Validación semántica advisory

**Qué es.** Un LLM local evalúa lo que el motor XML no puede capturar: coherencia
del resumen con el contenido, consistencia del estilo de citas, correspondencia
del índice con los títulos reales de capítulos, presencia de objetivos/hipótesis.
En el legacy hay **12 reglas "sin mecanismo"** (semánticas, fuera del MVP) que
esto cubriría.

**Quién/momento.** El encargado, bajo demanda, sobre una tesis que ya pasó el
semáforo de formato (o `--con-ia` opcional). El README ya dice: correr **después**
de que el doc pase las reglas deterministas, para no gastar cómputo en
documentos que ya fallan por formato.

**Cómo funcionaría.**
1. El motor corre su validación determinista (sin cambios).
2. El usuario pide la revisión semántica de una tesis.
3. El extractor entrega **fragmentos acotados**: resumen, tabla de contenido,
   lista de referencias, títulos de capítulos (ya se extraen para otras reglas).
4. Por cada check semántico se arma un prompt con **la regla textual específica
   + el fragmento** (no el reglamento completo, no toda la tesis).
5. El LLM devuelve un **JSON estructurado** (hallazgo, severidad advisory,
   ubicación aproximada).
6. El frontend publica una sección separada "Revisión semántica" del reporte.

**Dónde vive.** Módulo nuevo `validator/checks_semanticos.py`; endpoint nuevo
(`POST /validar/semantico`) o parámetro; frontend: tarjetas nuevas, tipadas
distinto, **desconectadas del semáforo**.

**LLM local.** Fragmentos cortos → latencia baja. Modelo 3B–8B según hardware.

**Ventajas.** Completa el producto ("validación de contenido"); aprovecha
fragmentos que el motor ya extrae; advisory, no rompe nada determinista.

**Desventajas.** No determinista; hay que **calibrar prompts** para no generar
falsos positivos que confundan al encargado; es lo más difícil de evaluar (no
hay golden master para "coherencia").

**Esfuerzo.** Medio: ~2–3 semanas.

**Encaje.** Es lo que el `README.md` ya lista como extensión. El semáforo queda
intacto. **No estaba priorizado como "Fase C"** (eso es la Funcionalidad 2), pero es la
promesa de más largo aliento del producto.

---

### Funcionalidad 2 — Explicación y priorización del diagnóstico 🔥 (la "Fase C")

**Qué es.** Dado el **reporte determinista** (que ya trae `tipo_documento`,
centinelas, `incumplen=[#N=...]`, esperado/encontrado, cita por regla), la IA
local produce dos cosas:
- **Explicación**: por qué falla cada regla, en lenguaje llano y qué significa
  para la entrega (bloquea el semáforo o no).
- **Priorización**: qué corregir primero, ordenado por impacto (qué errores
  destraban más reglas, cuáles son rápidos de arreglar, cuáles son peleados con
  el manual).

**Quién/momento.** El encargado cuando revisa un reporte fallido: botón
"explicar" por regla y botón "priorizar correcciones" en el reporte.

**Cómo funcionaría.**
1. Se toma el reporte ya generado (estructurado, completo).
2. Se le pasa a la IA el bloque de fallos + el contexto de cada regla
   (mensaje, esperado/encontrado, cita, ubicación).
3. La IA devuelve JSON: por regla, una explicación corta con la causa probable y,
   en conjunto, una lista ordenada de prioridades.
4. Se muestra como sección auxiliar (acordeones), editable/copiable.

**No necesita ver la tesis**: solo el reporte. Eso protege privacidad, ahorra
cómputo y hace la funcionalidad barata y rápida.

**Dónde vive.** `validator/asistente.py`; endpoint `POST /validar/priorizar` (o
campo aditivo a la respuesta); frontend: botones en `Report.jsx`.

**Ventajas.** Es **exactamente lo que el equipo ya definió como Fase C**
(`docs/diseno/15_tipo_documento_grupos.md`); alto valor operativo (triage);
no toca el motor; barato de implementar porque el reporte ya está.

**Desventajas.** Salida no determinista; hay que validar la calidad de la
priorización con el encargado real (¿le parece útil el orden?).

**Esfuerzo.** Bajo–medio: ~1–2 semanas.

**Encaje.** Directo con diseño 15 y con la mejora de reporting del issue #7.
**Es mi candidata a primera implementación.**

---

### Funcionalidad 3 — Clasificación asistida del tipo documental

**Qué es.** Cuando el detector determinista devuelve `sin_determinar`,
`contradictorio` o `tipo_documento_sin_estructura`, la IA local propone el tipo
más probable **con justificación** (qué títulos/firmas/declaración vio), y el
**encargado confirma o corrige**.

**Quién/momento.** El encargado, en tesis limítrofes. Hoy el centinela emite un
warning/error que deja la clasificación "colgada"; la IA la vuelve accionable.

**Cómo funcionaría.**
1. El motor detecta el estado problemático (sin/contradictorio/sin estructura).
2. Se envían a la IA **la misma evidencia que usa la heurística**: títulos
   detectados, firmas buscadas, declaración del Anexo 10.
3. La IA propone un tipo + justificación + qué reglas de estructura aplicarían.
4. El encargado confirma (botón) → se re-valida la tesis con ese tipo.

**Dónde vive.** `validator/asistente.py` (o módulo de tipo); endpoint
`POST /clasificar`. **Sin DB**: la decisión confirmada vive en la sesión/petición,
no se persiste (limitación del MVP sin base de datos).

**Ventajas.** Ataca el punto más débil de la detección actual; **humano en el
medio** (la IA propone, el encargado decide — mandato humano sobre el
semáforo); bajo riesgo; muy pocos datos que enviar (no lee la tesis, solo el
diagnóstico).

**Desventajas.** Requiere la interfaz de confirmación; hay que dejar claro que
es **asistida**, no automática (nunca un `sin_determinar` se resuelve solo).

**Esfuerzo.** Bajo: ~1 semana.

**Encaje.** Complementa el diseño 15 (centinelas) ya implementado. Es el único
lugar donde la IA **puede influir en el resultado de la validación**, por eso
exige confirmación humana explícita.

---

### Funcionalidad 4 — RAG de consulta del reglamento ⛔ descartada por ahora

**Qué es.** El encargado pregunta en lenguaje natural sobre el manual y los
RCUs y recibe respuesta **fundamentada con cita textual** al reglamento:
"¿qué anexos exige el trabajo de suficiencia profesional?", "¿dónde dice que el
margen izquierdo es 2,5 cm?", "¿puedo usar otra línea de investigación?".

**Quién/momento.** El encargado en el mostrador / mesa de ayuda, cuando atiende
dudas de estudiantes. Es su herramienta "de consulta rápida".

**Cómo funcionaría (sistema RAG completo).**
1. **Corpus**: documentos OCR ya disponibles en `recursos/ocr/*.txt`
   (RCU-274, líneas de investigación del RCU-220, y el manual si se vuelca a
   texto). Se trocea en fragmentos (chunks).
2. **Índice**: embeddings generados localmente (modelo de embeddings aparte) e
   índice vectorial.
3. **Consulta**: pregunta → recuperar top-k fragmentos.
4. **Generación**: el LLM responde usando solo los fragmentos recuperados y
   cita textualmente.

**Dónde vive.** Módulo nuevo (`validator/consultas.py`) + endpoint
`POST /consultar`; o CLI.

**Ventajas.** El encargado deja de buscar a mano en PDFs escaneados; aprovecha
el OCR ya hecho en las semanas 2–4; útil incluso para estudiantes (aunque no es
el target).

**Desventajas.** Es la funcionalidad con **más infraestructura**: necesita embeddings +
índice + corpus limpio (los PDFs escaneados dependen de la calidad del OCR);
más componentes que operar.

**Esfuerzo.** Medio: ~2–3 semanas.

**Encaje.** Aprovecha trabajo ya hecho (OCR), pero **no estaba en el plan
consensuado**. Buena segunda etapa, no primera.

---

### Funcionalidad 5 — Redacción de la respuesta al estudiante

**Qué es.** A partir de los fallos estructurados (reporte + tipo documental +
nombre/escuela), la IA local redacta la **prosa de la observación formal** al
estudiante con tono institucional y ordenada por prioridad. Hoy
`validator/notificacion.py` (Actividad 6) ya envía un correo **determinista**
(texto plantilla); la IA mejoraría el texto manteniendo el envío.

**Quién/momento.** El encargado: revisa el reporte → genera el texto → lo edita
si quiere → lo envía (o lo copia al correo institucional).

**Cómo funcionaría.**
1. Entrada: reporte estructurado (mismo que la Funcionalidad 2).
2. La IA redacta el correo/observación (saludo, resumen de lo accionable,
   lista de correcciones por prioridad, cierre institucional).
3. El encargado **edita antes de enviar** (el control humano es el escudo).
4. Se integra con `notificacion.py` (misma vía SMTP opt-in que ya existe).

**Dónde vive.** `validator/redactor.py` + botón en el reporte + reutiliza el
flujo SMTP existente.

**Ventajas.** Valor operativo alto (escribe el documento que ya se envía hoy a
mano/plantilla); bajo riesgo porque el texto es **editable**; no lee la tesis
(solo el reporte) → privacidad y costo mínimo.

**Desventajas.** Tono institucional a calibrar (habría que mostrar ejemplos
reales); cuidado de no inventar observaciones que no estén en el reporte
(obligación: **usar solo** los fallos reales).

**Esfuerzo.** Bajo: ~1 semana.

**Encaje.** `notificacion.py` ya existe; es un "mejorar la prosa", no construir
otro módulo. Natural como tercera pieza.

---

### Funcionalidad 6 — Auto-fix del documento ⛔ descartada por ahora

**Qué es.** Corregir el documento automáticamente. Punto clave: **lo de formato
es determinista** — márgenes, fuente, interlineado, numeración, sangría se
pueden corregir reescribiendo el XML (lxml) **sin IA**. El LLM solo aportaría
en lo semántico, que es justo lo más riesgoso de tocar solo.

**Quién/momento.** El encargado decide si aplica correcciones antes de
notificar. Riesgo de fondo: cambiar el **rol del producto**, de *validador*
(quien corrige es el estudiante) a *editor* (el sistema corrige). Un docente
recibiría una tesis modificada **sin revisión humana** — responsabilidad nueva.

**Cómo funcionaría.**
- Ruta determinista (factible hoy): aplicar `w:line`/`w:jc`/`w:firstLine`,
  márgenes de sección, tamaños de fuente → nuevo DOCX con diff de cambios.
- Ruta IA (futura): solo sugerencias sobre contenido (no modificar el texto).

**Dónde vive.** `validator/autofix.py` + endpoint de descarga del DOCX corregido.

**Ventajas.** Máximo valor para el estudiante; la parte determinista es
realmente factible ya con los datos del extractor.

**Desventajas.** Riesgo de corromper el DOCX; responsabilidad institucional;
rompe el flujo pedagógico actual ("ustedes corrigen con ayuda del reporte");
amplía el MVP a algo que fue explícitamente **excluido**. Alto esfuerzo.

**Esfuerzo.** Alto: 4+ semanas (y la parte segura es la determinista, que no
necesita IA).

**Encaje.** Reutilizaría el extractor; pero **no es el siguiente paso** que
venimos discutiendo — lo anoto para no perderlo de vista.

---

### Funcionalidad 7 — IA como herramienta interna de desarrollo ⛔ descartada por ahora

**Qué es.** Nosotros (el equipo) usamos un LLM para acelerar el desarrollo del
motor: extraer reglas del manual con template → YAML, proponer definiciones
DSL, generar tests/mutaciones, auditar paridad legacy↔DSL. **No toca runtime.**

**Quién/momento.** Integrante 3 en su flujo de trabajo.

**Ventajas.** Productividad del desarrollo; sin riesgos de producto ni de
privacidad (nada de tesis de estudiantes).

**Desventajas.** No le agrega nada visible al encargado ni al producto; no
sirve como entregable de la discusión actual.

**Esfuerzo.** Puntual (horas).

**Encaje.** Sería un script auxiliar `scripts/`, no un módulo del producto.

---

## 5. Decisiones transversales (extendidas)

**LLM local vs externo → local (reafirmado).**
Las tesis de estudiantes no salen del servidor (privacidad), sin costos
recurrentes, sin claves que escanear (`verificar_secretos.py` se queda como
está), funciona sin internet, y es lo que el equipo ya adelantó en el README.
Solo se toca si la biblioteca tiene un servidor **muy** limitado y el encargado
prefiere calidad vía API — pero eso reintroduce secretos y costos.

**Hardware y tamaño de modelo.**
- Si hay GPU (≥8 GB VRAM): 7B–8B cuantizado corre bien; calidad en español
  aceptable (Qwen2.5-7B-Instruct, Llama 3.1-8B, Gemma 2-9B).
- Si solo CPU: modelos 3B–4B cuantizados (Q4_K_M) corren en 8–16 GB RAM. Un 7B
  en CPU va lento (1–3 tokens/s).
- El tamaño del modelo y la latencia fijan el diseño: **la IA es bajo demanda**
  (botón), nunca dentro de cada `POST /validar`. Una respuesta de ~200 tokens en
  CPU puede tomar 1–2 min; el frontend debe avisar "esto toma un momento".

**Despliegue del modelo.**
- Proceso aparte: servicio **Ollama** (u OpenAI-compatible) corriendo en el
  mismo servidor que la API. La API FastAPI le habla por HTTP local.
- Los pesos del modelo **no van al repo** (GB) ni se declaran en `flake.nix`
  (son artefactos descargables, no dependencias). Se documenta el procedimiento
  de descarga (modelo + hash pinneado) y un script de arranque
  (`nix run .#serve-ia`).
- Alternativa embebida (`llama-cpp-python`) evita el proceso aparte pero mete
  una dependencia pesada y compilación en el entorno Nix.

**No-determinismo y semáforo (regla de oro).**
- La salida del LLM **jamás** se convierte en `RuleResult` ni toca el semáforo.
- Se modela con tipos propios (`SmartNote`, `Prioridad`, `ClasificacionPropuesta`,
  `RespuestaConsulta`) con severidad advisory.
- La IA puede **proponer** (clasificación, prioridad, correos), nunca **decidir**
  por sí sola el verde/rojo.

**Privacidad / datos.**
- Las tesis quedan en el servidor local; el LLM local nunca las envía fuera.
- Las funcionalidades 2, 3 y 5 **no leen la tesis** (solo el reporte/diagnóstico) — eso
  reduce superficie. Las funcionalidades 1 y 4 sí manejan fragmentos (tesis) y el corpus
  de reglamentos, respectivamente.

**Costura para CI (obligatoria para que la suite siga verde).**
- El CI corre en Nix **sin GPU ni modelos**. El módulo necesita una interfaz
  limpia:
  - `LLMClient` (protocol) con `run(prompt, json_schema) -> dict`.
  - Implementaciones: `OllamaClient` (real) y `StubLLM` (determinista, con
    respuestas fijas) para tests/property.
  - Si no hay `OLLAMA_URL` configurada, el endpoint responde "módulo de IA no
    disponible" (patrón de estado deshabilitado que I1 ya implementó para la
    notificación).

**Dónde vive y contrato.**
- Módulo nuevo (`validator/asistente.py` + sub-módulos por funcionalidad), **fuera de
  `engine.py`**. La validación determinista permanece pura e intacta.
- Contrato de API **aditivo y tipado** (como v1.5.0): los campos nuevos no
  rompen lo existente (`incluir_prompts_ia` sigue igual).
- Frontend: secciones nuevas separadas del semáforo, con aviso de carga
  ("la IA está pensando…" / "no disponible").

**Idioma.** El modelo elegido debe manejar bien español (los prompts y
respuestas son en español, como todo el proyecto).

---

## 6. Matriz comparativa

| Funcionalidad | Valor para el encargado | Riesgo | Esfuerzo | ¿Lee la tesis? | Encaje con lo consensuado |
|------|--------------------------|--------|----------|----------------|---------------------------|
| 1 — Validación semántica | Alto (completa el producto) | Medio (falsos positivos) | Medio (2–3 s) | Sí (fragmentos) | README ya lo lista |
| **2 — Explicación + priorización** | **Alto (triage)** | **Bajo** | **Bajo (1–2 s)** | **No** | **Es la "Fase C" definida** |
| 3 — Clasificación asistida | Alto (desatasca sin/contradictorio) | Bajo (humano confirma) | Bajo (1 s) | No | Complementa diseño 15 |
| 5 — Redacción de respuesta | Medio–alto (escribe lo que ya se envía) | Bajo (editable) | Bajo (1 s) | No | Reutiliza `notificacion.py` |
| ~~4 — RAG del reglamento~~ | (descartada) | — | — | — | — |
| ~~6 — Auto-fix~~ | (descartada) | — | — | — | — |
| ~~7 — Herramienta interna~~ | (descartada) | — | — | — | — |

## 7. Recomendación de ruta (para discutir)

Se mantienen en la mesa las funcionalidades **1, 2, 3 y 5**; 4, 6 y 7 quedan fuera por
ahora. Aún no hay orden acordado entre las cuatro:

1. **Funcionalidad 2 (explicación y priorización)** — candidata a primera pieza: es la
   Fase C que el equipo ya definió, barata, sin leer la tesis, y le da al
   encargado su herramienta de triage inmediata.
2. **Funcionalidad 3 (clasificación asistida)** — ataca el punto más débil de la
   detección del tipo, con confirmación humana.
3. **Funcionalidad 5 (redacción de la respuesta)** — convierte el diagnóstico en el
   correo que ya se envía.
4. **Funcionalidad 1 (validación semántica)** — la promesa de más largo aliento del
   producto; conviene hacerla con calibración cuidadosa de prompts.

Las cuatro comparten la misma base técnica (cliente LLM local + JSON
estructurado + tipos advisory), así que implementarlas como módulos separados
con la misma costura permite sumarlas en cualquier orden.

## 8. Pendiente de decidir

- ✅ Ideado el **orden**: 2 → 3 → 5 → 1 (decisiones tomadas en v0.4).
- ✅ **Hardware**: a prueba de CPU (3B) y GPU (7B); configurable por
  `OLLAMA_MODEL`.
- ✅ **Modelo**: Qwen2.5 (3B/7B); **despliegue**: Ollama servicio aparte.
- El diseño formal queda en `docs/diseno/16_modulo_ia.md`.
- Siguiente: implementación (a coordinar), contrato v1.5.0 con I1, frontend con
  I2, bitácora.