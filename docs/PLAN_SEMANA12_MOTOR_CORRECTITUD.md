# Plan Semana 12 — Correctitud del motor (Int3)

**Fecha:** 2026-11-12  
**Responsable:** IvanSanchezSil (Motor de reglas / Procesamiento, Int3)  
**Base:** `upstream/master` `bf6be5e` (PR #94)  
**Rama del plan:** `semana12-plan-correctitud-motor`  
**Fuente:** [`HANDOVER_CORRECTITUD_INT3_2026-11-12.md`](HANDOVER_CORRECTITUD_INT3_2026-11-12.md), [`HANDOVER_CORRECTITUD_2026-11-12.md`](HANDOVER_CORRECTITUD_2026-11-12.md) y [`AUDITORIA_NORMATIVA_2026-11-12.md`](AUDITORIA_NORMATIVA_2026-11-12.md)

Este documento **planifica**; no declara corregido ningún hallazgo. Cada tarea
se cierra en su propio PR con regresión, suite y evidencia.

---

## 1. Objetivo

Ejecutar las tareas de Int3 del handover de correctitud (`M1a`, `M1`–`M12`)
en PRs pequeños, con regresión previa al arreglo y sin invadir las áreas de
Int1 (API, buzón, constancias, userscript) ni de Int2 (SPA).

**Fuera de alcance:** `AGENTS.md` (salvo aprobación explícita), contrato de
API, DTO, SPA, userscript y cualquier cambio de severidad para «hacer pasar»
un documento.

---

## 2. Estado de partida

| Elemento | Estado |
|---|---|
| `upstream/master` | `bf6be5e` (PR #94, docs) |
| PR #75 (`M0` / VA-13) | Abierto, `MERGEABLE`, 857 passed / 4 skipped; pendiente de re-revisión |
| Motor | 49 reglas activas + 5 estructuras en `reglas_unt_pendientes.yaml` (sin documento real) |
| Corpus DOCX | `TESIS_LINARES…docx` (dos copias locales) |
| Corpus PDF | `TESIS_CARRION…pdf`; **el motor no procesa PDF** (soporte pendiente, no prometido) |
| Plantillas | 5 `*-PLANTILLA.docx` en `recursos/` (gitignored) |
| Hallazgos Int3 | VA-01..07, VA-11..18 y NM-01..07 |

> El handover pide contrastar «dos tesis locales». Hoy solo hay **una tesis
> DOCX**; la segunda es PDF y queda fuera del alcance del extractor. Antes de
> cerrar una tarea de reglas hay que confirmar con el encargado si la segunda
> tesis se usa en PDF (no aplicable) o si se consigue otra tesis DOCX.

---

## 3. Reglas de ejecución (del handover)

1. Una rama y un PR por tarea o lote pequeño; no mezclar tareas.
2. Reproducir el fallo **antes** de corregirlo; agregar una regresión que falle.
3. Corregir la causa, no ocultar el fallo ni bajar severidades.
4. No cambiar la semántica global de `eq` ni relajar el CI.
5. Verificar regresión, suite completa y documentos reales afectados.
6. Registrar comando, resultado, límites y PR/commit en la tabla §2 del
   `HANDOVER_CORRECTITUD_2026-11-12.md`.
7. Fixtures con nombres ficticios; **sin tesis reales, HAR, credenciales ni PII**.
8. Si falta una decisión de dominio, registrar «pendiente»; no inventar estándar.

---

## 4. Mapa de hallazgos → tareas

| ID | Prioridad | Tarea | PR propuesto |
|---|---|---|---|
| VA-13 | P1 | M0 — integración PR #75 | **PR #75** (abierto) |
| VA-17 | P1 | M11 — paquete OPC del factory | 12.1 |
| VA-11 | P2 | M1a — validar entrada del extractor | 12.2 |
| VA-01, VA-02 | P1 | M1 — formato efectivo y todo el texto | 12.3 |
| VA-03 | P1 | M2 — A4 en todas las secciones | 12.4 |
| VA-04 | P2 | M3 — paginación y certeza | 12.5 |
| VA-05 | P2 | M4 — declaraciones múltiples | 12.5 |
| VA-06, VA-07 | P2 | M5 — resumen, abstract y palabras clave | 12.6 |
| VA-14 | P2 | M6 — nombre de anexo «Base de datos» | 12.6 |
| VA-15 | P2 | M7 — tamaño del logo | 12.6b |
| VA-16 | P2 | M8 — ORCID por persona y destino | 12.7 |
| VA-12 | P2 | M9 — texto literal y recursos en PDF | 12.7 |
| VA-18 | P2 | M10 — contadores de CLI/exportación | 12.7 |
| NM-01 | P1 | M12a — paginación normativa | 12.8 |
| NM-02 | P1 | M12b — escuela/asesor en carátula | 12.8 |
| NM-03 | P1 | M12c — esquemas y tipos soportados | 12.8 |
| NM-04 | P2 | M12d — longitud de título y autores | 12.9 |
| NM-05 | P2 | M12e — mínimos de referencias | 12.9 |
| NM-06 | P2 | M12f — anexos incompletos | 12.9 |
| NM-07 | P2 | M12g — citas normativas | 12.9 |

---

## 5. PRs propuestos y orden

El orden respeta las dependencias del handover: `M12` **amplía** M1, M3, M5 y
M6, así que no se adelanta. Los P1 van antes que los P2 dentro de cada bloque.

### PR 12.1 — M11: reparar el paquete OPC del factory (P1, Lote A)

- **Archivos:** `tests/_xml_constants.py`, `tests/_docx_builder.py`,
  `tests/docx_factory.py`, pruebas de construcción del motor.
- **Trabajo:** corregir la relación interna y agregar una imagen válida en el
  destino correcto del ZIP; verificar `[Content_Types].xml` y `.rels`.
- **Aceptación:** el documento base abre con `python-docx`; todos los destinos
  de relaciones internas existen; mutaciones y reglas conservan su intención.
- **Desbloquea:** B6 de Int1. Entregar comando de regeneración.
- **Riesgo:** tocar el factory puede afectar muchos tests; correr la suite
  completa y revisar que cada mutación siga cambiando solo su regla.

### PR 12.2 — M1a: validar la entrada del extractor (P2, Lote B)

- **Archivos:** `validator/extractor.py`, `tests/test_extractor_edgecases.py`.
- **Trabajo:** excepción de documento inválido para B5; validar XML, raíz,
  namespace y cuerpo; documentar las partes OPC mínimas admitidas.
- **Aceptación:** XML truncado, raíz ajena y cuerpo ausente fallan de forma
  controlada; documentos admitidos y fixtures válidos siguen extrayéndose.
- **Desbloquea:** B5 de Int1.
- **Riesgo:** no usar `except Exception` que convierta defectos del servidor en
  entradas inválidas; conservar límites anti-ZIP-bomb.

### PR 12.3 — M1: formato efectivo y revisión de todo el texto (P1)

- **Archivos:** `validator/extractor.py`, `validator/analizadores.py`,
  `reglas_unt.yaml`, `tests/`.
- **Trabajo:** leer `styles.xml`, `docDefaults`, estilos de párrafo/carácter,
  `basedOn` y propiedades directas; definir precedencia y detectar ciclos.
  Evaluar cada run con texto (incluidos hipervínculos), no solo `w:r[1]`.
- **Aceptación:** primer run vacío; segundo run Arial 36 pt; estilo incorrecto;
  formato directo y heredado equivalentes; propiedades ausentes; estilo de
  carácter; hipervínculo; cadena de estilos; ciclo; párrafo con estilo de
  título. Una infracción local se detecta sin rechazar el documento correcto.
- **Riesgo:** es el PR más grande; dividir en commits internos (extracción,
  resolución de estilos, reglas, tests) y declarar límites de numeración,
  formato condicional y temas.

### PR 12.4 — M2: A4 en todas las secciones aplicables (P1)

- **Archivos:** `reglas_unt.yaml`, `validator/analizadores.py`, pruebas de
  secciones.
- **Trabajo:** comparar todas las secciones sujetas a A4 y normalizar
  orientación; **no** cambiar la semántica global de `eq`.
- **Aceptación:** portada A4 + cuerpo Letter falla; A4 horizontal legítimo
  pasa; se señala la sección culpable; alcance de anexos y carátula documentado.

### PR 12.5 — M3 + M4: paginación y declaraciones múltiples (P2)

- **M3 (VA-04):** `_paginacion_para` en `extractor.py`, analizador de
  paginación y `tests/test_f2_paginacion.py`. Procesar saltos por orden y
  valor; `pageBreakBefore` afecta al propio párrafo; `w:val="0"` no crea salto;
  contar varios saltos en el mismo párrafo; distinguir página estimada de
  comprobada.
  **Aceptación mínima:** `[1,2]` con break-before en el segundo párrafo;
  `[1,3]` con dos saltos en el primero; `[1,1]` con break-before desactivado.
- **M4 (VA-05):** `DeteccionTipo._tipo_declarado`. Recoger todas las casillas
  marcadas antes de decidir; dos tipos distintos producen contradicción;
  repetir el mismo tipo no cambia la decisión.
  **Aceptación:** cuantitativo + cualitativo marcados no dan verde; invertir el
  orden conserva el resultado; probar párrafos, tablas y controles.

### PR 12.6 — M5 + M6: contenido y anexos (P2)

- **M5 (VA-06/07):** resumen 159–220 palabras; palabras clave 3–5; separar
  prosa y etiquetas antes del conteo; revisar Resumen y Abstract por separado;
  un título `ABSTRACT` vacío no prueba que exista contenido.
  **Aceptación:** 158/159/220/221 palabras; 2/3/5/6 claves; Abstract vacío;
  solo un idioma correcto; palabras clave excluidas del conteo de prosa.
  Mantener `palabras_clave_minimo` en `error`.
- **M6 (VA-14):** cambiar el ítem acordado a «Base de datos» y añadir nota
  `EVALUADO` (decisión 2026-11-08); mantener warning.

### PR 12.6b — M7: tamaño del logo (P2)

- **M7 (VA-15):** delimitar carátula y medir dibujo con 4,84 × 6,73 cm y
  tolerancia justificada. Si solo se implementa presencia, **renombrar** la
  regla y dejar la medición pendiente; no declararla cerrada.
- **Decisión previa:** §6 (medir o renombrar).

### PR 12.7 — M8 + M9 + M10: ORCID, exportación y contadores (P2)

- **M8 (VA-16):** delimitar carátula, asociar cada persona y resolver el
  destino del vínculo; aceptar dígito de control `X`; validar checksum; no
  verificar identidad por red.
- **M9 (VA-12):** `validator/exportador.py` y `tests/test_exportador.py`.
  Escapar sintaxis Markdown de texto no confiable; impedir que un prompt cierre
  su bloque de código; restringir el fetcher de PDF a recursos permitidos.
- **M10 (VA-18):** `validator/cli.py`, `exportador.py` y pruebas. Usar
  `total_evaluadas` bajo «evaluadas» y mostrar omitidas aparte.

### PR 12.8 — M12a + M12b + M12c: brechas normativas P1

> Requiere M1, M3, M4 y M5 mergeados (M12 los amplía).

- **M12a (NM-01):** decimal explícito correcto no falla por existir; reinicio
  romano 99 falla; PAGE a la izquierda no cumple por otro párrafo derecho;
  `titlePg=0` no significa primera página diferente.
- **M12b (NM-02):** eliminar escuela falla aunque exista facultad; asesor
  36 pt falla aunque la etiqueta esté correcta; probar cada bloque y propiedad.
- **M12c (NM-03):** el encargado ratifica tesis/informe/TINV; no afirmar
  soporte de ocho tipos; tipos ambiguos y no soportados quedan explícitos; no
  activar pendientes sin documento real.

### PR 12.9 — M12d + M12e + M12f + M12g: brechas normativas P2

> No iniciar sin las decisiones de §6.

- **M12d (NM-04):** límite inferior del título por tipo; 14/15/20/21 palabras;
  dos autores en orden e invertidos; confirmar máximo de autores.
- **M12e (NM-05):** mínimos 20/30/20 TINV; 30 para proyecto/informe; TSP separa
  mínimo 20 del informe y máximo 10 de sesión; una entrada partida no cuenta
  como varias.
- **M12f (NM-06):** el encargado ratifica REQ-51..55; eliminar cada anexo
  requerido falla en el tipo correcto; no acreditar firma ni porcentaje.
- **M12g (NM-07):** cada cita literal existe en la fuente; paráfrasis marcada;
  corregir el conteo documental 46→50 sin alterar el catálogo válido.

---

## 6. Decisiones pendientes (no inventar)

| Tarea | Decisión necesaria | Dueño |
|---|---|---|
| M5 | Límites y severidad del Abstract según el manual | Encargado / Int3 propone |
| M7 | ¿Se mide el logo o se renombra la regla a «presencia»? | Encargado |
| M12c | Ratificar tesis/informe/TINV y tipos soportados | Encargado |
| M12d | Límite inferior de título por tipo y máximo de autores | Encargado |
| M12e | Mínimos de referencias por ámbito (20/30/20) | Encargado |
| M12f | Contradicciones de anexos REQ-51..55 | Encargado |
| Corpus | ¿Hay segunda tesis DOCX o solo el PDF de Carrión? | Encargado |

Mientras una decisión falte, el requisito se registra como **pendiente** en la
matriz; no se convierte en «cumple» ni se elige un estándar por intuición.

---

## 7. Verificación por PR

```bash
nix develop -c pytest tests/ -v
nix develop -c ruff check validator/ scripts/ tests/
nix develop -c ruff format --check validator/ scripts/ tests/
nix develop -c mypy validator/ scripts/
nix develop -c python3 scripts/generate_openapi.py --check   # solo si toca contrato
nix flake check
```

Además, cuando se toquen reglas:

- contrastar la tesis DOCX local y las 5 plantillas de `recursos/`;
- verificar que cada mutación del factory siga cambiando **solo** su regla;
- no fijar como éxito el conteo histórico de tests: las regresiones nuevas lo
  cambian.

---

## 8. Evidencias de cierre

Cada PR debe dejar:

1. la regresión que falla antes del arreglo;
2. el comando y el resultado de la suite;
3. el contraste con el corpus aplicable y sus límites declarados;
4. la fila actualizada en §2 de `HANDOVER_CORRECTITUD_2026-11-12.md`;
5. la fila de §11 de `HANDOVER_AUDITORIA_2026-10-26.md` (si aplica);
6. la bitácora `docs/semana12_trabajo_ivanSanchezSil.md`.

---

## 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| M1 rompe muchas reglas al cambiar la resolución de estilos | Commits internos y contraste con tesis + plantillas en cada paso |
| M11 desestabiliza el factory y los tests de propiedad | PR aislado; correr suite completa y mutaciones |
| M2 cambia `eq` global y altera otras reglas | Comparación local para A4; no tocar `eq` |
| Falsos positivos en tesis reales | Corpus real + revisión del encargado; no solo «verde» |
| M12 se adelanta sin M1/M3/M5/M6 | Respetar el orden de §5 |
| Decisiones sin fuente | Registrar pendiente; no inventar estándar |
| PDF prometido sin soporte | Declarar PDF fuera de alcance hasta implementar extractor |

---

## 10. Definición de hecho

Una tarea está cerrada cuando:

- la regresión reproduce el fallo y pasa con el arreglo;
- la suite completa, ruff, format y mypy están limpios;
- el corpus aplicable se contrastó y los límites quedaron escritos;
- el handover y la bitácora registran PR/commit y evidencia;
- no se tocaron archivos de Int1/Int2 ni `AGENTS.md` sin aprobación;
- no hay PII ni datos reales en fixtures, bodies o capturas.

---

## 11. Calendario sugerido

La Semana 12 cubre los P1 y sus prerrequisitos; el resto pasa a la Semana 13.
Los P1 de M12 no se postergan una vez que sus prerrequisitos estén mergeados.

### Semana 12

| Día | Entregable |
|---|---|
| Lunes | PR 12.1 (M11) y PR 12.2 (M1a) |
| Martes–Miércoles | PR 12.3 (M1) |
| Miércoles–Jueves | PR 12.4 (M2) |
| Jueves–Viernes | PR 12.5 (M3 + M4) |

### Semana 13

| Orden | Entregable |
|---|---|
| 1 | PR 12.6 (M5 + M6) — habilita M12c y M12f |
| 2 | PR 12.8 (M12a–c, P1) |
| 3 | PR 12.6b (M7) y PR 12.7 (M8 + M9 + M10) |
| 4 | PR 12.9 (M12d–g, P2) y regresión final |

El orden puede ajustarse si Int1 necesita M11/M1a antes, o si el encargado
entrega las decisiones de §6 antes de lo previsto.

---

## 12. Próximos pasos inmediatos

1. Mergear el PR #75 (M0) y actualizar su evidencia final.
2. Abrir el PR 12.1 (M11) para desbloquear B6 de Int1.
3. Abrir el PR 12.2 (M1a) para desbloquear B5 de Int1.
4. Confirmar con el encargado las decisiones de §6 antes de M12.
