# Plan de implementación: tipo de documento y grupos excluyentes

**Estado**: aprobado, pendiente de ejecución
**Fecha**: 2026-09-28
**Rama**: `semana6` (continúa el trabajo ya iniciado en esa rama; el PR es el #36)
**Diseño asociado**: `docs/diseno/15_tipo_documento_grupos.md`

Cada paso es independiente y se pide de uno en uno.

## 1. Objetivo

Corregir el defecto por el que una tesis conforme se reporta en rojo, y dejar
preparada la incorporación de las 5 estructuras que el manual define y el motor
no tiene, sin exigir plantillas que la biblioteca no posee.

El problema y su evidencia están en el documento de diseño 15. En resumen: las 4
plantillas oficiales del repositorio salen en **rojo** con 5 errores bloqueantes,
2 de los cuales son estructuras de otros tipos de tesis y por lo tanto
**imposibles de corregir**.

## 2. Regla de oro

Ningún paso se da por terminado si `nix run .#test -- tests/ -v` no queda en
verde. Si un paso rompe la suite, se arregla antes de seguir.

## 3. Pasos

### Paso 1 — Andamiaje de dos fases (sin cambio de comportamiento)

**Objetivo**: la maquinaria de `expone` / `aplicar_si`, sin usarla todavía.
Cero cambios observables.

**Archivos**: `validator/models.py`, `validator/compilador.py`,
`validator/dsl_check.py`, `tests/`

**Qué hacer**

1. `RuleResult` gana `aplicable: bool = True`. Actualizar `to_dict()`.
2. `ReglaCompilada` lee `expone` y `aplicar_si` del YAML.
3. `CompilerDSL.ejecutar()` pasa a dos fases: la primera corre las reglas **sin**
   `aplicar_si` y acumula el contexto; la segunda corre el resto. Con ninguna
   regla usando `aplicar_si`, el resultado debe ser idéntico al actual.
4. `dsl_check.py`: validar que `aplicar_si` sea un mapa no vacío y que sus claves
   las exponga alguna regla. Error de linter si apunta a una clave inexistente.

**Verificación**

- 213 tests en verde.
- `aplicable` es `True` en todos los resultados.
- Un test nuevo del linter rechaza un `aplicar_si` colgado.

**Hecho cuando**: suite verde y el diff no altera ningún resultado de regla.

---

### Paso 2 — Analizador de detección de tipo

**Objetivo**: la lógica que decide de qué tipo es un documento, aún sin conectar
al reporte.

**Archivos**: `validator/analizadores.py`, `validator/compilador.py`,
`validator/dsl_check.py`, `tests/`

**Qué hacer**

1. Clase `DeteccionTipo` con los 3 niveles de la decisión 2 del diseño:
   declaración (Anexo 10), firmas con umbral, y sin determinar.
2. Precedencia por especificidad según la decisión 2 (informe antes que
   proyecto).
3. Normalización al comparar: mayúsculas, sin acentos, sin indentación.
4. Registrar en `SECCIONES_ANALIZADOR` y `_FABRICAS` de `compilador.py`.
5. `deteccion_tipo` en `_SECCIONES` de `dsl_check.py`, validando: `expone`
   presente, `evidencia` no vacía, `minimo >= 1`, tipos de `firmas` únicos.

**Verificación**

- Tests unitarios del analizador: los 8 tipos se detectan con un conjunto
  mínimo de títulos.
- Un título que no corresponde a ningún tipo devuelve "sin determinar".
- Suite verde.

**Hecho cuando**: el analizador se puede invocar sobre un DOCX y devuelve tipo,
evidencia y nivel.

---

### Paso 3 — Regla discriminadora en el YAML

**Objetivo**: que el tipo detectado aparezca en el reporte.

**Archivos**: `reglas_unt.yaml`, `tests/_mutations.py`,
`tests/test_propiedad.py`

**Qué hacer**

1. Añadir `deteccion_tipo_documento` con `severidad: warning`,
   `expone: tipo_documento` y las 8 firmas del diseño.
2. `_mutations.py`: entrada en `REGLAS` y mutación mínima que rompa la detección.
3. Confirmar que el documento del factory se detecta como `tinv_cuantitativo`.

**Verificación**

- 295 tests en verde.
- El reporte muestra el tipo en `found`
  (`inferido=tinv_cuantitativo ("VARIABLE", "POBLACIÓN Y MUESTRA", ...)`).
- **El semáforo no cambia**: es `warning`, no bloquea.
- Las 47 reglas previas conservan su `found` intacto.

**Estado**: hecho. Requiere tocar además `validator/compilador.py`, que
fijaba `found="cumple"` también en las reglas `expone`; y la firma de revisión
del diseño hubo que corregirla (ver la nota en
`docs/diseno/15_tipo_documento_grupos.md`).

---

### Paso 4 — `aplicar_si` en las 3 estructuras (este es el arreglo)

**Objetivo**: que dejen de aparecer los errores imposibles.

**Archivos**: `reglas_unt.yaml`, `tests/_mutations.py`,
`tests/test_propiedad.py`

**Qué hacer**

1. Añadir `aplicar_si: {tipo_documento: ...}` a las 3 reglas de estructura.
2. `EXCLUIDAS_BASE` pasa a vacío: las 2 estructuras alternativas dejan de
   evaluarse.
3. Renombrar `test_doc_bueno_pasa_45` → `test_doc_bueno_pasa_47_sin_fallos`.

**Verificación**

- Documento bueno: **46 evaluadas, 0 fallos, 2 no aplicables, semáforo verde**.
- Las 5 plantillas oficiales: de 5 errores bloqueantes a **3**.
- Suite verde (322 tests).

**Estado**: hecho. Requiere tres cosas que el paso no preveía, todas
documentadas en `docs/diseno/15_tipo_documento_grupos.md`:

1. `aplicar_si`Admite un valor **lista** ("cualquiera de estos"). Las 3
   estructuras aceptan su tipo + `sin_determinar` + `contradictorio`, para que
   un tipo no clasificado se valide contra todos los esquemas en vez de dejar
   la estructura sin revisar en silencio.
2. Corrección de tres firmas que se robaban documentos ajenos. En concreto una
   tesis cualitativa se detectaba como `informe_cualitativo` y se quedaba sin
   validación estructural. Se derivó la evidencia de las estructuras que el
   repo ya codifica, y se comprobó la matriz de 8 firmas x 3 estructuras.
3. Los tests de paridad con el YAML legacy renuncian a 2 reglas: el motor
   legacy evalúa siempre las 44 y no tiene el concepto de aplicabilidad, así
   que su desacuerdo en esas reglas ES el defecto que se corrige.

---

### Paso 5 — Conteos dinámicos en el reporte

**Objetivo**: que el resumen diga la verdad.

**Archivos**: `validator/engine.py`, `tests/`

**Qué hacer**

1. `build_report` agrega `total_evaluadas` y `reglas_no_aplicables` al resumen, y
   excluye las no aplicables de `resultados`.
2. El semáforo se sigue calculando sobre las aplicables (ya lo está por
   construcción).

**Verificación**

- Documento bueno: `total_evaluadas: 46`, `reglas_no_aplicables: 2`,
  `fallidos_error: 0`, semáforo verde.
- Suite verde.

**Estado**: hecho. La proyección original decía 43 evaluadas y 4 omitidas;
los números reales son 46 y 2, porque al final solo los 3 esquemas TINV se
condicionaron al tipo (el paso 4 dejó las 5 estructuras nuevas para el 8), y el
documento bueno es un plan cuantitativo.

---

### Paso 6 — Tipo no determinado y contradicción

**Objetivo**: los dos casos límite, sin huecos de seguridad.

**Archivos**: `validator/compilador.py`, `validator/engine.py`, `tests/`

**Qué hacer**

1. Sin tipo detectado → `tipo_documento_no_determinado`, severidad `error`,
   mensaje accionable; las 8 estructuras quedan no aplicables.
2. Declaración y firma contradictorias → `tipo_documento_contradictorio`.

**Verificación**

- Documento sin marcadores → **1** error claro, no 8.
- Documento contradictorio → 1 error claro.
- Suite verde.

**Hecho cuando**: ningún camino permite que un documento mal estructurado salga
en verde.

**Estado**: hecho. Los dos centinelas se sintetizan en `compilador.ejecutar()`
cuando la detección queda en `sin_determinar` o `contradictorio`; se insertan
justo después de `deteccion_tipo_documento`. Para que existiera el hueco limpio
hubo que cambiar los 3 `aplicar_si` de las estructuras a su tipo EXACTO: con
los estados malos dentro (decisión del paso 4) el estudiante seguía viendo 2
errores de secciones en vez de 1 error que dice qué hacer. Es decir, el paso 6
**revierte** esa parte del paso 4, a propósito.

Consecuencia: las estructuras ya no son la red de seguridad para un tipo
desconocido; los estados terminales son errores propios. Las 8 estructuras
(paso 8) deben seguir el mismo patrón que estas 3.

---

### Paso 7 — Contrato de API (coordinar con Integrante 1)

> **Estado: entregado como documento, no implementado.**
> `api_models.py` es área del Integrante 1 y cambiar `resumen` altera el
> contrato publicado, así que este paso no se ejecuta aquí: se entrega
> `docs/HANDOVER_API_TIPO_DOCUMENTO.md`, que especifica el cambio exacto con
> números medidos sobre el motor actual, la decisión de contrato que le toca
> tomar al Integrante 1 y los pasos de regeneración del spec. La implementación
> queda pendiente de que el Integrante 1 la asuma.

**Objetivo**: exponer lo nuevo sin romper el contrato publicado.

**Archivos**: `validator/api_models.py`, `docs/openapi_spec.json`,
`docs/CONTRATO_API.md`

**Qué hacer**

1. **Coordinar antes de empezar.** `api_models.py` es área de Integrante 1 y
   `resumen` cambia de semántica.
2. Campos nuevos en el resumen y el contexto del documento.
3. Regenerar `openapi_spec.json` con `scripts/generate_openapi.py` y commitearlo:
   el **CI verifica el drift**.
4. Actualizar `docs/CONTRATO_API.md`.
5. Avisar a Integrante 2: el frontend recibe un resumen dinámico.

**Verificación**

- `nix flake check` en verde, incluida la verificación de drift.

**Hecho cuando**: el contrato refleja el cambio y el CI lo confirma.

---

### Paso 8 — Fase B: las 5 estructuras que faltan

**Objetivo**: implementar lo que sí está definido en el manual, aunque no se
pueda probar contra documentos reales.

**Archivos**: `reglas_unt_pendientes.yaml` (nuevo), `docs/`

**Qué hacer**

1. Extraer los 5 esquemas del manual. **Rangos corregidos**: los del plan
   original (805-866, 941-999, 1160-1213, 1264-1311, 1463-1499) no apuntan a
   los esquemas, sino a párrafos de formato y de metodología. Los reales se
  (localizaron por su encabezado `ESQUEMA ...`, y cada uno termina justo antes
   del `LISTA DE COTEJO` de su tipo:

   | Tipo | Encabezado | Párr. |
   |---|---|---|
   | proyecto_cuantitativo | `ESQUEMA DEL PROYECTO DE INVESTIGACIÓN CUANTITATIVO` | 1585-1788 |
   | proyecto_cualitativo | `ESQUEMA DEL PROYECTO DE INVESTIGACIÓN CUALITATIVO` | 2097-2297 |
   | informe_cuantitativo | `ESQUEMA DEL INFORME DE INVESTIGACIÓN CUANTITATIVA` | 2668-2721 |
   | informe_cualitativo | `ESQUEMA DEL INFORME DEL PROYECTO DE INVESTIGACIÓN CUALITATIVO` | 3073-3120 |
   | tsp | `ESQUEMA DEL TRABAJO DE SUFIENCIA PROFESIONAL` | 3628-… |
2. Escribir las 5 reglas con `aplicar_si` + `automata_secuencia`, usando
   `opcional: true` donde el manual lo indique. Cada `aplicar_si` acepta **solo
   su tipo exacto**, igual que las 3 del paso 6.
3. Documentar los alias: `informe_cuantitativo` acepta "Tesis de investigación
   cuantitativa" y `informe_cualitativo` la variante cualitativa.
4. Registrar en el archivo que el manual exige 3.3/3.3 Aspectos generales para
   el TSP, y que esa exigencia ya la cubre la regla `indice_hojas_preliminares`.

**Verificación**

- El linter acepta el archivo (esto valida la **configuración**, no el
  comportamiento).
- Al cargar el archivo aparte, un documento cuantitativo deja aplicar solo su
  estructura.

**Hecho cuando**: las 5 reglas cargan, lintean y son revisables contra el
manual. **Sin pruebas de comportamiento, por decisión explícita** — no hay
plantillas para estos 5 tipos.

---

### Paso 9 — Documentación y cierre

**Archivos**: `docs/DSL.md`, `README.md`, `AGENTS.md`,
`docs/diseno/00_indice_diseno.md`, `docs/semana6_trabajo_ivanSanchezSil.md`

**Qué hacer**

1. `DSL.md`: secciones `deteccion_tipo`, `expone`, `aplicar_si`.
2. Índice de diseño: dar de alta el documento 15.
3. `README.md` y `AGENTS.md`: actualizar conteos.
4. Las 3 desviaciones entre plantilla y manual (`Discusión`,
   `Aspectos éticos`, `Conclusiones y Recomendaciones`) con la convención
   `EVALUADO:`.
5. Corregir el nombre de rama obsoleto `semana52-brechas-manual` en la bitácora
   de semana 6 y hacer commit de la bitácora.

**Verificación**: `nix flake check` en verde y `git status` limpio.

**Hecho cuando**: la documentación cuenta la misma historia que el código.

## 4. Orden y dependencias

```mermaid
flowchart LR
    P1["1<br/>andamiaje"] --> P2["2<br/>analizador"]
    P2 --> P3["3<br/>regla discriminadora"]
    P3 --> P4["4<br/>aplicar_si en las 3"]
    P4 --> P5["5<br/>conteos dinámicos"]
    P5 --> P6["6<br/>casos límite"]
    P6 --> P7["7<br/>contrato API"]
    P1 --> P8["8<br/>5 estructuras (Fase B)"]
    P7 --> P9["9<br/>documentación"]
    P8 --> P9
```

La Fase A (pasos 1-7) es secuencial. La Fase B (paso 8) solo necesita el paso 1.

## 5. Fuera de alcance

- Módulo de IA (Fase C, posterior a este plan).
- Reglas por programa de estudio.
- OCR, correo, notificación.
- Plantillas reales de los otros tipos: **no las tiene la biblioteca**. Queda
  como petición formal pendiente, no como tarea.
