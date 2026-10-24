# Informe de diagnóstico — Validación de tesis convertidas desde PDF

Fecha: 2026-10-05
Alcance: `docs/pruebas/` (tesis Carrion Cruz, versión original y corregida `_2026`)
Reglas usadas: `reglas_unt.yaml` (DSL, 47 reglas verificables)

## Resumen

- La suite de tests pasa completa (244/244). El motor está sano.
- Ambos archivos dan semáforo rojo. El corregido (`_2026`) falla MÁS reglas
  (24 errores + 5 warnings) que el original (21 + 5), aunque en la realidad
  es el MÁS conforme.
- Causa raíz principal: los DOCX provienen de una conversión PDF→DOCX
  (perfil de pdf2docx: se declara como "Microsoft Office Word",
  AppVersion 12.0000). La conversión fabrica exactamente los metadatos
  XML que el validador inspecciona.
- Causa secundaria: seis fragilidades/bugs reales del validador, varios
  de los cuales también fallan las plantillas oficiales, o hacen que
  ningún documento pueda obtener semáforo verde.
- El PDF 2026 real es sustancialmente conforme: Times New Roman, A4,
  márgenes correctos, interlineado 1.5, cuerpo justificado, numeración
  correlativa corregida. Las correcciones del estudiante son reales.

## 1. Evidencia: la conversión fabrica el XML

| Metadato | Realidad (PDF) | DOCX convertido | Reglas afectadas |
|---|---|---|---|
| Papel | A4 exacto (595.3 x 841.9 pt) | 11910 x 16840 twips (desvío 4/2) | papel_tamano |
| Fuente | Times New Roman embebida | Arial en todos los runs | fuente_principal |
| Interlineado | gaps de 20.7 pt (~1.5) | `w:line="20" lineRule="exact"` | interlineado |
| Márgenes | sup 2.5, izq 3.0 (2026) | Por página: top 1320/1340/1860, bottom 280/960/1240 | margen_superior/inferior/derecho/izquierdo |
| Secciones | ~2-3 en doc nativo | 122 y 136 secciones (una por página) | rompe `contexto: cuerpo` |
| Números de página | Campo de Word | Texto literal en párrafos del footer | numeracion_posicion, numeracion_preliminares_romano |
| titlePg / pgNumType | Presente en nativo | Ausente | caratula_no_se_enumera |
| Alineación | Cuerpo justificado (bordes derechos 527.2-527.5 pt alineados) | `jc=left` explícito masivo | alineacion_cuerpo |
| Runs | — | Run vacío `<w:r><w:rPr/></w:r>` al inicio de párrafos de carátula | Todas las reglas que usan `w:r[1]` |

Además: `contexto: cuerpo` se implementa como "párrafos después del
último sectPr" (`validator/extractor.py:38`, `_cuerpo_paras`). Con 136
secciones, "cuerpo" queda reducido a la última página de anexos. Por eso
`tamano_cuerpo` evaluó `['13','12','13']` (fragmentos del último anexo)
en vez del cuerpo real a 12 pt.

## 2. Bugs y fragilidades reales del validador

### B1 — Suposición de primer run (`w:r[1]/w:rPr`)
Reglas: caratula_universidad_tamano, caratula_universidad_negrita_mayusculas,
caratula_asesor_negrita, caratula_ciudad_pais_negrita, caratula_titulo_negrita_mixta.
El párrafo "UNIVERSIDAD NACIONAL DE TRUJILLO" del 2026 tiene el formato en el
SEGUNDO run y en `w:pPr/w:rPr`; el primero es un run vacío → `@w:val=[]` →
falso fallo. El PDF real muestra 18 pt bold (correcto).
También afecta DOCX nativos cuando el primer run es un fragmento vacío
(p. ej. por corrector ortográfico).

### B2 — `AnalizadorLista` evalúa cada `w:t` por separado
`validator/analizadores.py:165`. `caratula_linea_investigacion` compara
'educación', 'y', 'ciencias de' individualmente contra el catálogo. El texto
unido — "Educación y ciencias de la comunicación y Desarrollo sostenible" —
SÍ es una línea aprobada (última entrada del catálogo en `reglas_unt.yaml`).
Falso positivo confirmado.

### B3 — `alineacion_caratula_todos_elementos` sin límite de carátula
El XPath matchea 40 párrafos de TODO el documento (cualquier párrafo del
cuerpo que contenga "Trujillo", "asesor" o "escuela" entra) → ve left/both/right
y falla. La carátula real está 100% centrada. Fallará en cualquier tesis real
cuyo cuerpo mencione esas palabras.

### B4 — Anexos: doble fallo estructural
(a) `AnalizadorListaObligatoria._texto()` solo une tokens PARRAFO — excluye
títulos ("Anexo 01. Matriz de consistencia" es Heading4 = TITULO) y tablas
(los anexos son tablas). (b) `seccion()` con `fin=None` corta en el primer
TITULO posterior — el código contradice su docstring ("devuelve el resto del
flujo") — así que el corte "Anexos" → "Anexo 01" queda vacío. Resultado:
los 9 ítems se reportan como faltantes aunque 3 existen (matriz pág. 62,
instrumentos ~70, base de datos 88). También falla en las plantillas oficiales.

### B5 — El semáforo jamás puede estar verde
Las 3 reglas `estructura_tinv_*` son mutuamente excluyentes y las 3 son
`error`; `build_report` (`validator/engine.py:104`) pone rojo con cualquier
error. Un documento cuantitativo perfecto siempre falla las otras 2.
Las plantillas oficiales dan rojo (5 errores). Consistente con el
"doc bueno 45/47" de AGENTS.md: los 2 fallos son las 2 estructuras no
coincidentes, y aun así el semáforo es rojo. Falta semántica de
"estructura alternativa" (una de tres debe pasar).

### B6 — `proyecto_caratula_texto` no sabe ser N/A
Regla de carátula de Proyecto que falla en toda Tesis (0 nodos → fail).
Falla también en las plantillas de tesis.

### B7 — Anclas frágiles
`caratula_titulo_negrita_mixta` busca el literal "título del trabajo",
que la carátula real no contiene (dice "TESIS / Para Optar el Título
Profesional..."). No puede evaluar → falla. En el 2026 real el título
es negrita + mayúsculas/minúsculas (correcto).

### Observación adicional
`caratula_autores_mayusculas_sin_negrita` falla también en las plantillas
oficiales ("Br. ..." en mayúsculas/minúsculas) — desviación plantilla-vs-manual
sin bajar a warning, a diferencia de las 3 que sí bajaron (tamaño título
13≠14 pt, "Para Optar" 12≠13 pt, sangría 708≠720).

## 3. Correcciones reales del estudiante (PDF viejo vs 2026)

| Aspecto | Viejo | 2026 |
|---|---|---|
| Margen izquierdo | 2.5 cm (incorrecto) | 3.0 cm (correcto) |
| Correlativo arábigos | Introducción (pág. física 11) muestra "6" | Introducción (pág. física 12) muestra "12" (preliminares i–xi + 12) |
| Sección "Presentación" | Faltante | Presente |
| Carátula | Idéntica en ambos | Idéntica en ambos |

## 4. Incumplimientos reales del 2026 (aunque se usara el DOCX nativo)

- Números de página CENTRADOS; el manual pade margen inferior derecho
  (las plantillas sí usan derecha) — numeracion_posicion.
- Autor "Br. Carrion Cruz..." en mayúsculas/minúsculas, no MAYÚSCULAS
  (las plantillas también incumplen).
- Anexos incompletos: faltan ficha técnica, consentimiento informado,
  declaración jurada, reporte de similitud y cartas (warning).
- Título 13 pt vs 14 pt del manual, etc. — desviaciones documentadas (warning).

## 5. Plan de acción propuesto

- Fase 0 (decisión de producto): NO soportar como entrada DOCX convertidos
  desde PDF; el flujo exige el DOCX nativo del estudiante.
- Fase 1: guardián de entrada — detectar el perfil "convertido desde PDF"
  (sectPr > 20, lineRule="exact" masivo, fuente única Arial, sin estilos
  reales) y reportarlo en metadatos/reporte como advertencia explícita.
- Fase 2 (motor, coordinar con Integrante 3):
  1. B2: unir texto de párrafo en `AnalizadorLista` antes de comparar.
  2. B1: comparación robusta de formato — evaluar todos los runs con rPr
     o caer a `w:pPr/w:rPr`; nueva comparación en el DSL + regenerar XPaths.
  3. B3: limitar la regla de alineación de carátula al bloque de carátula.
  4. B4: incluir TITULO (y texto de TABLA) en `AnalizadorListaObligatoria`;
     decidir semántica de `seccion()` con `fin=None` (código vs docstring).
  5. B5: semántica "una de las tres estructuras" — agrupar `estructura_tinv_*`
     (p. ej. `grupo: estructura`) y que el semáforo solo exija que UNA pase.
     Requiere acuerdo del equipo: cambia el significado del semáforo.
  6. B6: N/A de `proyecto_caratula_texto` cuando la carátula declara TESIS.
  7. B7: revisar anclas de carátula contra carátulas reales.
- Fase 3: mutaciones en `tests/_mutations.py` + fixtures regresivas con
  perfil pdf2docx (run inicial vacío, runs divididos, multisección).
- Fase 4: verificación — suite completa, `nix flake check`, y corrida del
  CLI sobre ambos convertidos + plantillas con el PDF 2026 como referencia
  de verdad.

## 6. Incertidumbres

- Semántica de `seccion()` con `fin=None`: ¿bug de código o de docstring?
  `tests/test_f2_automatas.py` puede fijar el comportamiento actual.
- B5 cambia el significado del semáforo: decisión de equipo.
- No se tiene el DOCX nativo del estudiante; la clasificación "PDF real =
  conforme" se basa en medir el PDF renderizado, sólido pero no idéntico a
  inspeccionar XML nativo.

---

## 7. Verificación final de recursos/ (2026-10-05, misma sesión)

### 7.1 Validador vs plantillas oficiales

| Documento | Resultado | Fallidos |
|---|---|---|
| EDUCACION INICIAL-PLANTILLA CUANTITATIVA | rojo | 15/47 |
| PROGRAMA ... EDUCACION TEMPRANA-PLANTILLA | rojo | 15/47 |
| PROGRAMA ... ESTIMULACIÓN-PLANTILLA | rojo | 15/47 |
| TECNOLOGIA EDUCATIVA-ADMINISTRACION | rojo | 15/47 |
| TECNOLOGIA EDUCATIVA-INFORMATICA | rojo | 15/47 |
| MANUAL (documento de referencia, no es tesis) | rojo | 37/47 |

Las 5 plantillas fallan de forma UNIFORME (15/47). Fallos crónicos en
todas: anexos_minimos_cuantitativo/cualitativo, caratula_autores_mayusculas_sin_negrita,
caratula_optar_grado_tamano, caratula_titulo_trabajo_tamano,
estructura_tinv_cualitativo, estructura_tinv_revision_literatura,
indice_subdivisiones (plantillas), palabras_clave_minimo,
proyecto_caratula_texto, referencias_minimo_* (3), resumen_longitud,
sangria_parrafo.

Clasificación de los crónicos:
- Esperables en una plantilla (contenido vacío): resumen_longitud,
  palabras_clave_minimo, referencias_minimo_*, anexos_minimos_*,
  indice_subdivisiones.
- Desviaciones plantilla-vs-manual ya documentadas: caratula_titulo_trabajo_tamano
  (13≠14 pt), caratula_optar_grado_tamano (12≠13 pt), sangria_parrafo (708≠720).
- Desviación SIN degradar a warning: caratula_autores_mayusculas_sin_negrita
  (plantillas usan "Br. ..." en mayúsculas/minúsculas) — error en el YAML.
- Problemas estructurales del motor (ver B4, B5, B6): anexos_minimos_*
  (no ve ítems que SÍ existen), estructura_tinv_cualitativo/revision
  (mutuamente excluyentes → semáforo rojo garantizado), proyecto_caratula_texto
  (no sabe ser N/A en tesis).

### 7.2 Catálogo de líneas de investigación (RCU-N°220-2022/UNT)

- `reglas_unt.yaml` declara 50 líneas en `caratula_linea_investigacion`.
  AGENTS.md dice "46 líneas" — inconsistencia de documentación (real: 50).
- Verificación contra el PDF oficial (texto nativo/OCR): 49/50 coinciden
  textualmente; la restante ("Educación y Ciencias de la Comunicación y
  desarrollo sostenible") está presente pero partida en dos renglones por
  el OCR del PDF. Resultado: 50/50 correctas. Catálogo verificado.

### 7.3 Citas textuales del manual

11/11 citas verificadas en "MANUAL REVISADO TERCERA VERSION OBSERVACIONES
11-07-2025.docx", con la numeración de párrafos calzando exactamente
(p. ej., la cita de carátula está en el párrafo 174 como declara el YAML).
Dos citas parten en dos párrafos consecutivos ("Alineación:" / "Justificada"
en 130-131; "Numeración de la página:" / "Margen inferior derecho." en
137-138) — correctas igual. El trabajo de reglas/citas es sólido.

### 7.4 Comportamiento con input PDF

- API `POST /validar`: bien guardada.
  - PDF con extensión .pdf o content-type no soportado → 415 con mensaje
    en español.
  - PDF RENOMBRADO a .docx → 422: "El archivo no es un ZIP/DOCX válido:
    cabecera incorrecta (se esperaba la firma 'PK')."
- CLI: traceback crudo `zipfile.BadZipFile` — necesita mensaje amable.
- Soporte real de PDF (validar PDFs como ciudadanos de primera clase)
  sigue pendiente: requeriría extractor con PyMuPDF (ya listado como
  pendiente en AGENTS.md, sección "Lo que NO se hace (MVP)").

### 7.5 Herramientas de evaluación

- `scripts/eval_contra_plantillas.py` SOLO soporta el YAML legacy:
  con `reglas_unt.yaml` lanza `KeyError: 'rules'`. Debería soportar el
  formato DSL (`reglas`) o al menos fallar con mensaje claro.
- El shellHook del flake lo invoca sin el argumento del YAML
  (`eval_contra_plantillas.py recursos/`), lo que rompería con argparse.

## 8. Veredicto general

1. El trabajo de reglas del catálogo y citas del manual es correcto y
   verificable (50/50 líneas, 11/11 citas). La calidad de la fuente de
   verdad está bien.
2. Los fallos observados no son de contenido de reglas, sino de:
   robustez de analizadores frente a XML no ideal (B1, B2, B3, B4, B7),
   semántica de reglas mutuamente excluyentes sin efecto en semáforo (B5),
   y ausencia de semántica N/A (B6).
3. Ningún documento — ni siquiera las plantillas oficiales — puede hoy
   obtener semáforo verde. Este es el problema de mayor prioridad.
