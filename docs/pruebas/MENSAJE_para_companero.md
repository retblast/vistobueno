# Mensaje para el Integrante 3 (motor de reglas)

(Sugerencia: copiar desde "Hola" hasta el final. El informe técnico completo
con toda la evidencia está en `docs/pruebas/INFORME_diagnostico_conversion_pdf.md`.)

---

Hola. Estuve haciendo una pasada de verificación completa al validador usando
una tesis real (la de Carrion Cruz, incluida la versión corregida 2026) y
encontré varias cosas del motor que creo que te van a interesar. Todo está
documentado con evidencia en `docs/pruebas/INFORME_diagnostico_conversion_pdf.md`;
aquí te dejo solo lo que te toca a ti, y aparte lo que me queda a mí, para
que no haya confusiones de terreno.

## Contexto: qué probé

- La suite de tests pasa completa (244/244). El motor está estable.
- Probé el validador contra la tesis en dos versiones (original y corregida
  2026) convertidas de PDF a DOCX, y contra las 6 plantillas oficiales y el
  manual de `recursos/`.
- Ambas versiones de la tesis dan semáforo rojo. La corregida falla MÁS
  reglas (24 errores) que la original (21), aunque en la realidad es más
  conforme. La culpa es de la conversión, no del documento.

## Primero lo bueno: tu parte está verificada y correcta

- El catálogo de líneas de investigación del YAML tiene 50 entradas y las
  50 coinciden con el RCU-N°220-2022 (lo comprobé contra el texto del PDF;
  una aparece partida en dos renglones por el OCR del documento, pero está).
- Las 11 citas textuales del manual que muestrean las reglas calzan exacto,
  incluida la numeración de párrafos (la cita de carátula está en el párr.
  174, como declara el YAML).
- Las 5 plantillas oficiales fallan de forma uniforme (15/47): el motor es
  consistente y determinista.

O sea: la fuente de verdad (reglas, catálogo, citas) está bien. Lo que sigue
es robustez del motor frente a XML no ideal y semántica de un par de reglas.

## Lo que te toca a ti (motor de reglas)

### 1. El semáforo no puede estar verde NUNCA — prioridad máxima

Las 3 reglas `estructura_tinv_*` son mutuamente excluyentes y las 3 son
`severidad: error`. `build_report` (validator/engine.py:104) marca rojo con
cualquier error que falle, así que un documento cuantitativo perfecto siempre
falla las estructuras cualitativa y de revisión. Ni las plantillas oficiales
dan verde (las 5 dan rojo). Encaja con el "doc bueno 45/47" documentado:
los 2 fallos son las 2 estructuras no coincidentes.

Fix propuesto: semántica de grupo ("una de las tres debe pasar") para el
semáforo, en `engine.py` + `reglas_unt.yaml`. Como cambia el significado
del semáforo, primero lo validamos entre todos, pero la implementación
sería tuya.

### 2. Los analizadores asumen que el primer run tiene el formato

Varias reglas de carátula usan XPaths tipo `.../w:r[1]/w:rPr/w:sz`. En la
carátula del 2026, el párrafo "UNIVERSIDAD NACIONAL DE TRUJILLO" tiene un
run vacío primero (`<w:r><w:rPr/></w:r>`) y el formato en el segundo run y
en `w:pPr/w:rPr`. Resultado: `caratula_universidad_tamano`,
`caratula_universidad_negrita_mayusculas`, `caratula_asesor_negrita`,
`caratula_ciudad_pais_negrita` y `caratula_titulo_negrita_mixta` reportan
`@w:val=[]` / "exists 0 nodos" y fallan, aunque el PDF real tiene 18 pt en
negrita como manda el manual. También puede pasar en DOCX nativos cuando el
corrector parte el primer run.

Fix propuesto: evaluar todos los runs con `rPr` o caer a `w:pPr/w:rPr`
(probablemente una comparación nueva en el DSL + regenerar los XPaths del YAML).

### 3. `caratula_linea_investigacion` evalúa fragmentos, no la frase

`AnalizadorLista` (validator/analizadores.py:165) compara cada nodo `w:t`
por separado contra la lista. Si la línea viene partida en runs
('Educación', 'y', 'ciencias de', ...), cada fragmento falla. El texto
unido ("Educación y ciencias de la comunicación y Desarrollo sostenible")
SÍ está en el catálogo aprobado. Falso positivo confirmado con la tesis
real; la misma fragmentación puede darse en DOCX nativos.

Fix propuesto: unir el texto del párrafo antes de comparar
(analizadores.py:175).

### 4. `alineacion_caratula_todos_elementos` no tiene límite de carátula

El XPath matchea cualquier párrafo del documento que contenga "universidad",
"facultad", "escuela", "asesor", "trujillo", etc. En la tesis real matchea
40 párrafos de TODO el cuerpo (por mencionar Trujillo en las referencias)
y falla, aunque la carátula real está 100% centrada. Va a fallar en
cualquier tesis real cuyo cuerpo mencione esas palabras.

Fix propuesto: acotar el XPath al bloque de carátula (hasta el primer
salto de sección/página).

### 5. Los anexos no se ven aunque existan

Doble causa, ambas tuyas:
- `AnalizadorListaObligatoria._texto()` (analizadores.py:310) solo une
  tokens PARRAFO; excluye títulos (los "Anexo 01. ..." son Heading4 =
  TITULO) y tablas (los anexos son tablas).
- `seccion()` (tokenizer.py) con `fin=None` corta en el primer TITULO
  posterior — el código contradice su docstring, que dice "devuelve el
  resto del flujo". El corte "Anexos" → "Anexo 01" queda vacío.

Resultado: la regla reporta los 9 ítems como faltantes cuando al menos 3
existen (matriz de consistencia en pág. 62, instrumentos, base de datos).
También falla así en las plantillas. Fix propuesto: incluir TITULO (y texto
de TABLA) en `_texto()` y definir la semántica real de `fin=None`
(revisando qué fija `tests/test_f2_automatas.py` hoy).

### 6. `proyecto_caratula_texto` no sabe ser N/A

Es una regla de carátula de Proyecto que falla en toda tesis (0 nodos →
fail). Falla también en las plantillas de tesis. Fix propuesto: N/A cuando
la carátula declara TESIS/Trabajo de Investigación.

### 7. Anclas frágiles en reglas de carátula

`caratula_titulo_negrita_mixta` busca el literal "título del trabajo",
que la carátula real no contiene (dice "TESIS / Para Optar el Título
Profesional..."). No puede evaluar y falla, aunque el título real sí es
negrita con mayúsculas y minúsculas. Fix propuesto: revisar las anclas de
carátula contra carátulas reales (muestra: esta tesis).

### 8. `caratula_autores_mayusculas_sin_negrita` en las plantillas

Las plantillas oficiales usan "Br. ..." en mayúsculas y minúsculas, la regla
pide MAYÚSCULAS, y sigue siendo `error`. Las 3 desviaciones hermanas
(tamaño título 13≠14 pt, "Para Optar" 12≠13 pt, sangría 708≠720) sí fueron
degradadas a warning con su nota EVALUADO. Falta decidir si esta se degrada
igual o se mantiene; la decisión es del motor.

## Lo que NO te toca (yo me encargo)

Para que no te mezcle en el mensaje: nada de esto requiere nada tuyo.

- CLI: hoy truca con traceback crudo (`zipfile.BadZipFile`) si le pasan un
  PDF. La API ya responde 415/422 con mensajes claros. Le pongo manejo
  amable en la CLI.
- `scripts/eval_contra_plantillas.py`: solo soporta el YAML legacy (con
  `reglas_unt.yaml` lanza `KeyError: 'rules'`) y el shellHook del flake lo
  invoca sin el argumento del YAML. Lo arreglo de mi lado.
- AGENTS.md dice 46 líneas de investigación y el YAML tiene 50. Propongo
  la corrección con aprobación del equipo, como pide la guía.
- Tests: si me confirmas el scope de los puntos 2-8, armo los tests de
  regresión y las mutaciones sincronizadas (`tests/_mutations.py`) con el
  XML real de esta tesis (run vacío, runs partidos, multisección).
- Aceptación de PDFs en la API (más adelante): contrato, metadatos de
  formato y validaciones son míos. Cuando lleguemos ahí, el extractor PDF
  con PyMuPDF sí sería terreno tuyo, pero eso es otra conversación.

## Qué necesito de ti

1. Tu opinión sobre el punto 1 (semáforo) antes de tocar nada — es lo que
   más urge porque hoy el semáforo es rojo garantizado para cualquier doc.
2. Confirmar el orden/prioridad de los puntos 2-8 para coordinar los tests
   de mi lado.
3. Leer el informe completo cuando puedas:
   `docs/pruebas/INFORME_diagnostico_conversion_pdf.md` (tiene la evidencia
   y las líneas exactas de cada hallazgo, más la verificación de tu
   catálogo y citas).

Dale una mirada y me dices cómo arrancamos.
