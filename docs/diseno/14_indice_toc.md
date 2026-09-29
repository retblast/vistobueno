# 14. Índice de contenidos (F2 ítems 11 y 12)

- **Fecha**: 2026-09-22
- **Estado**: implementado
- **Commits**: `(Semana 5 — Bloque D)`

## Problema

El índice de contenidos (TOC) es el mapa declarado de la tesis: sus entradas
deben corresponder a secciones reales y su numeración debe reflejar la
jerarquía del documento. Hasta ahora el motor no validaba ninguna de las dos
cosas (el XPath de `indice_subdivisiones` solo exigía que los tres títulos
"INDICE DE …" quedaran en páginas separadas).

El 2026-09-22 los ítems 11-12 se habían diferido (commit `dfced63`) por un
supuesto falso positivo contra las plantillas UNT. Al revisarlo con evidencia:

- **Ítem 11**: el manual NO prohíbe números de página en el índice de
  contenidos; de hecho el índice de TABLAS los exige (párr. 195). El criterio
  "apuntar" es de **estructura** (la entrada corresponde a una sección real),
  no de ausencia de páginas. El diferido se basaba en un malentendido.
- **Ítem 12**: los saltos "1.3. EL PROBLEMA" → "1.5 VARIABLE(S)…" que se
  tomaron como falso positivo eran entradas del **factory de tests** (que usaba
  1.3→1.5 del esquema oficial), no de las plantillas. La estructura oficial
  omite secciones que "no aplican" (1.4); la regla débil la acepta.

## Decisiones

1. **Dos reglas nuevas en el DSL**, ambas `warning` (no cambian el semáforo de
   las plantillas ya validadas):
   - `indice_apunta_secciones` (tipo `toc_apunta`, op `entradas_corresponden`).
   - `indice_numeracion_jerarquica` (tipo `toc_numeracion`, op
     `jerarquia_consistente`).
   - Con nota `EVALUADO:` en el YAML referenciando el manual (párr. 194) y el
     desvío documentado.

2. **Semántica "sin índice pasa" (n/a)**: un documento sin región de índice
   no es un desvío en sí (lo cubren otras reglas de estructura); la regla
   pasa con detalle n/a, igual que `nota_pie`. El desvío se detecta solo
   cuando hay índice y sus entradas no corresponden / no respetan la
   jerarquía.

3. **Nuevas secciones DSL `toc_apunta` y `toc_numeracion`**, despachadas por
   el compilador a los analizadores nuevos (registradas en
   `SECCIONES_ANALIZADOR`, `_FABRICAS` y `dsl_check._SECCIONES`). El campo
   `regex_indice` (regex acotable) añadido a `dsl_check._CAMPOS_REGEX`.

## Criterio de `AnalizadorTocApunta`

1. Localizar la región del índice: va de un encabezado que matchea
   `regex_indice` (defecto `^indice(\s+de\s+contenidos)?$`) al siguiente
   encabezado de cualquier nivel. La comparación es IGNORECASE y **sin
   acentos** (`_sin_acentos`), porque `re` no iguala "Í" con "I".
   Los párrafos con estilo `TDC*` (que Word genera en el índice) NO son
   encabezados → quedan dentro de la región.
2. Por cada entrada del índice: `_normalizar` quita el prefijo de numeración
   (romano `I.` o decimal `1.1.`), el número de página final (arábigo o romano
   `iii`), paréntesis, puntuación y tildes.
3. Se toma la **palabra significativa** (`_sigpalabra`): el primer token de ≥ 4
   caracteres. Así "1.1. EL PROBLEMA ……. 3" → `EL PROBLEMA`.
4. Debe ser subcadena de algún **título del cuerpo** normalizado. La subcadena
   (no igualdad) cubre el caso anexos: la entrada "Anexo 1. …" matchea el
   título "ANEXOS" (`ANEXO` ⊂ `ANEXOS`).
5. Sin región → pasa, detalle `sin_indice (n/a)`. Fallo: lista de entradas
   que no corresponden a ninguna sección (`entrada_sin_seccion=[...]`).

## Criterio de `AnalizadorTocNumeracion`

Sobre las entradas de la misma región (mismo algoritmo de detección):

1. Capítulos en romano (`I.`, `II.`, …) deben ser **consecutivos**: el valor
   de cada capítulo debe ser `último + 1`.
2. Subsecciones decimales (`K.1`, `K.1.1`, …): el primer componente debe ser
   el número del capítulo actual (`subseccion_sin_capitulo`,
   `capitulo_descolgado`).
3. La **primera** subsección de cada capítulo debe ser `K.1`
   (`primera_subseccion_no_K1`).
4. Las subsecciones siguientes deben estar en **preorder estricto**:
   comparación de tuplas `prev < valor` (`fuera_de_orden`). Ej:
   `1.1 < 1.1.1 < 1.2 < 1.3`.
5. **NO** se exige contigüidad de hermanos: omisiones tipo "1.3" → "1.5"
   (sección que "no aplica" respetando la numeración oficial) **pasan**. Es la
   variante débil que evita marcar las plantillas UNT.
6. Entradas sin número (p. ej. "REFERENCIAS", "ANEXOS") se ignoran, igual que
   los niveles que no sean romanos/decimales.
7. Sin región → pasa, detalle `sin_indice (n/a)`.

## Invariante de propiedad (factory)

La base ahora emite un TOC válido (`TDC_ENTRADAS_BASE`, 20 entradas
`(nivel, texto)` con página), permitiendo que las dos reglas nuevas pasen en
`test_doc_bueno_pasa_sin_fallos`. La cadena de mutación agrega:

- `indice_apunta_secciones` → `_insertar_tdc` (entrada "1.6. DELIMITACIÓN DE
  LA INVESTIGACIÓN" tras 1.5, cuyo token "DELIMITACIÓN" no existe en el cuerpo
  → `entrada_sin_seccion`). Se inserta en orden de documento para no romper la
  jerarquía del ítem 12.
- `indice_numeracion_jerarquica` → `_renumerar_tdc` ("1.2. ENUNCIADO DEL
  PROBLEMA" → "2.2. …": capítulo descolgado, token intacto).

Además `REGLAS_ACOPLADAS` documenta que renombrar "SITUACIÓN PROBLEMÁTICA" en
el cuerpo (`estructura_tinv_cuantitativo`) rompe `indice_apunta_secciones`
porque el título deja de existir para la entrada "1.1. SITUACIÓN
PROBLEMÁTICA 2" — es la mutación `estructura_tinv_cuantitativo` la que
detecta el acople real.

Nota: en éxito el motor reporta `found="cumple"` (no el detalle del
analizador), por eso renombrar la región del índice (n/a) no es observable y
`indice_subdivisiones` conserva solo su acople original.

## Conteos tras el cambio

| Concepto | Antes | Ahora |
|----------|-------|-------|
| Reglas en `reglas_unt.yaml` | 45 | **47** |
| `_migracion.total_reglas_con_f3` | 45 | 47 |
| Doc bueno | 43/45 | **45/47** |
| Mutaciones | 45 | 47 |
| Tests | 190 | **197** |

## End-to-end

`curl -F "archivo=mi_tesis.docx" localhost:8000/validar` devuelve
`indice_apunta_secciones` e `indice_numeracion_jerarquica` en `resultados`.
Si la tesis no tiene índice, aparecen como **cumple** (n/a); si tiene entradas
fantasma o capítulos descolgados, fallan como `warning` y su `ubicacion` se
enriquece con `; página N` (ítem 1 de la F2, `ultimo_nodo`).