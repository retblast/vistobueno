# Diseño: extracción de la ficha de depósito (motor)

**Fecha**: 2026-10-20
**Semana**: 9
**Área**: Motor de reglas (Int3)
**Pedido**: `docs/HANDOVER_MOTOR_FICHA_DEPOSITO.md` (Int1)
**Plan de producto**: `docs/PLAN_FICHA_DEPOSITO.md`

## 1. Qué se construye

Los analizadores ya **localizan** título, autores, asesor, resumen, palabras
clave y escuela, pero solo publican pass/fail y un `found` resumido. La pantalla
de depósito (SPA I2) necesita **el texto completo, con su página**, para
pre-llenar el formulario oficial de DSpace.

El motor debe entregar, por dato (contrato §4 del handover):

```
{"campo": "dc.title", "valor": "...", "pagina": 1, "detectado": true}
```

Solo lectura: no cambia el semáforo, no agrega reglas de validación, no toca
`validator/api.py` ni `validator/dspace.py`.

## 2. Mecanismo elegido

El handover ofrece dos opciones. Se elige un **híbrido** porque ninguna de las
dos, sola, cubre bien los 8 campos:

- La ficha captura **párrafos de carátula** (título, autores, asesor, escuela,
  año) que **no** son las reglas ya mecanizadas de la carátula (esas validan
  tamaño/negrita, no capturan el nodo del dato). Son localizaciones nuevas,
  baratas, sobre la carátula.
- La ficha también reusa las reglas existentes de **sección** (resumen,
  palabras clave), que ya tienen su propio `xpath`/`seccion` en el YAML.

Por lo tanto:

1. **Sección DSL nueva `extraccion`** (`AnalizadorExtraccion`): un analizador
   de hoja que **captura el texto del nodo** (o de los nodos) que su XPath
   localiza, y lo publica en un acumulador de la corrida. Se usa para los
   párrafos de carátula, donde la localización es nueva y declarativa.
2. **Sección DSL `extraccion` anidada en reglas existentes**: las reglas que
   ya localizan una sección/texto (resumen, palabras clave, línea) declaran
   `extraccion` en su misma config; el analizador que ya trae el XPath lo
   reutiliza. Evita duplicar XPath en el YAML.
3. **Campo `ficha` en `RuleResult`** (opcional): el analizador, al capturar,
   deja el `(campo, valor, nodo)`; `ReglaCompilada.ejecutar` lo adjunta al
   `RuleResult`, que calcula `pagina` con `extracted.pagina_de(nodo)`.
   `to_dict()` expone `ficha`. La API recolecta los `ficha` de todos los
   resultados y arma `extraidos[]`.

Así el formato es uniforme (lo decide el motor, no cada regla a mano), la API
no parsea `found`, y el costo es acotado: un analizador de hoja nuevo + un
campo opcional en `RuleResult` + el acumulador.

## 3. Alternativas descartadas

- **Campo `valores` genérico en cada regla** (opción (a) pura): obliga a que
  cada regla decida su formato a mano; sin `extraccion` declarativa no queda
  uniforme. Se conserva solo el transporte (`ficha` en `RuleResult`), no la
  captura ad-hoc.
- **Dict de contexto** (`contexto["ficha"]`, opción (b) pura): el contexto hoy
  es `dict[str, str]` para `expone`/`aplicar_si`; meterle una lista de dicts lo
  ensucia y no viaja al DTO (la API consume `RuleResult`, no el contexto).
- **Detección de año fuera del motor** (regex en la API): rompe la regla "la
  API no parsea texto para inventar heurísticas por regla".

## 4. Campos y claves (contrato §2 y §4)

| Campo (clave) | Origen | Estado |
|---------------|--------|--------|
| `dc.title` | párrafo de título en carátula | localización nueva |
| `dc.contributor.author` | párrafo de autor(es); lista si hay varios | localización nueva |
| `dc.contributor.advisor` | párrafo de asesor | localización nueva |
| `dc.description.abstract` | sección Resumen | reusa `resumen_longitud` |
| `dc.subject` | palabras clave del resumen | reusa `palabras_clave_minimo` |
| `dc.date.issued` | año en carátula | localización nueva |
| `escuela` | línea "ESCUELA ACADÉMICO PROFESIONAL DE…" | localización nueva |
| `renati.juror` | sección de firmas / jurado | **viabilidad**: ver §6 |

`valor` es `str` o `list[str]` (autores, palabras clave, jurado). `pagina` se
calcula del nodo capturado (mayoría en carátula → página 1). `detectado` es
`false` cuando el XPath no encontró el nodo: la ficha publica el campo igual,
para que la SPA muestre el hueco vacío.

**Fuera del pedido** (handover §2, actualización 2026-10-19): el servidor de
DSpace pre-llena por colección 16 campos, así que el motor **no** captura:

- **Grado/título al que opta** (`thesis.degree.name`): pre-lleno.
- **Línea de investigación** (`dc.subject.ocde`): pre-llena. El **mapeo
  línea→OCDE queda cancelado** para el depósito (no era una fase pendiente, se
  descarta).
- DNI del autor/asesor, ORCID, DOI, ISBN: los teclea el operador; el motor no
  los busca.

Por eso `escuela` no es un campo del formulario de DSpace, sino el dato de la
columna ESCUELAS del registro de la biblioteca (el operador lo usa fuera de la
pantalla).

## 5. Notas de implementación

- El analizador de extracción **nunca falla** la validación: es captura, no
  chequeo. `analizar` devuelve `True` siempre (si el nodo existe captura; si
  no, no captura). No altera el semáforo.
- Los párrafos se localizan sobre `//w:body/w:p` con el contexto `caratula`
  donde aplique, y `pagina_de` resuelve la página física.
- La lista de autores se separa como lo hace `caratula_autores_*` (un valor
  por párrafo/autor); si la plantilla pone "Autores: A y B" en un párrafo, se
  guarda el texto completo y la SPA lo divide (no se inventa un separador).
- Se sincroniza `tests/_mutations.py` si la `extraccion` anidada cambia el
  `found` de una regla existente (regla de `AGENTS.md`): **no debería**, porque
  la captura no modifica el fallo previo; se verifica con la suite.

## 6. `renati.juror` — conclusión de viabilidad

El handover pide evaluar si los nombres del jurado salen de forma confiable de
la sección de firmas. Se inspeccionaron la plantilla oficial y una tesis real:

- **Plantilla** (`EDUCACION INICIAL-PLANTILLA...docx`, párr. 31-52): título
  "Jurado Evaluador" seguido de tres bloques `____` + "(Dr. o Mg. o Lic.)
  (Apellidos completos, Nombres completos)" + `Presidente` / `Secretario (a)` /
  `Miembro`. Son **placeholders**: el operador los rellena a mano.
- **Tesis real** (`recursos/tesis/tesis_linares_2026.docx`, párr. 43): título
  "Jurado Dictaminador" y luego **líneas en blanco** hasta "Agradecimiento".
  Los nombres no están en el DOCX.

**Conclusión**: los nombres del jurado **no** salen de forma confiable del
DOCX. Dependen de que el autor los escriba (a veces no lo hace; cuando lo
hace, la disposición varía entre "Evaluador" y "Dictaminador", con o sin
cargos). Inventar una heurística produciría datos falsos en un metadato
oficial. Por eso **no se implementa captura de `renati.juror`**: queda
`detectado: false` y el operador lo teclea en la pantalla, como preveía el
handover. Se reevaluará si la facultad estandariza la sección de firmas con
nombres reales.


## 7. Verificación pedida (handover §5)

- Tests de que cada campo de la §2 expone su valor con el factory determinista.
- Paridad: la ficha extrae los placeholders en las 5 plantillas (esperable).
- Suite completa verde y `tests/_mutations.py` sincronizado si aplica.

## 8. Wiring de la API (Int1)

El motor ya entrega `reporte["ficha"]` con el diccionario que la API espera.
Falta que `POST /validar` evalúe el ruleset de captura en la misma pasada:

```python
from validator.engine import load_ficha_rules
...
resultados_motor = await run_in_threadpool(
    validate_docx, tmp_path, rules_data, load_ficha_rules()
)
```

`_ficha_desde_reporte` y `FichaDeposito` ya están en `validator/api.py` y
`validator/api_models.py`; no requieren cambio: recorren las claves de la §2 y
rellenan `detectado=false` para las ausentes (`renati.juror`, o cualquier
campo que el XPath no encontró). Este cambio vive en el área de Int1; el motor
no lo hace (handover §6: "no tocar la API").

