# Plan integral: consolidación del motor DSL — VistoBueno

**Estado**: F1, F2, F3, F4 y F6 **cerradas** (2026-09-07… 2026-09-09, Semana 3). 
F5 **implementada** (2026-09-15, Semana 4) en el PR #22 — traza embebida en `found` (Opción A, ver `docs/diseno/09_f5_enlace_api_propuesta.md`).
**Fecha**: 2026-09-09
> Nota (2026-09-09): se aplicaron las correcciones de revisión del PR #11
> (Paso 14 de `CAMBIOS_MOTOR_DSL.md`): factory modular, sincronización de
> mutaciones en import y documentación de `seccion()`. Suite: **140 tests**.

## 1. Objetivo

Consolidar el motor DSL (autómatas, analizadores y gramáticas) y extenderlo
con migración completa al DSL, nuevas reglas mecanizadas, mejoras de
ingeniería, traza para el reporte y tests de propiedad. **El contrato de la
API y de `validate_docx` se preserva** (forma: `List[RuleResult]`).

## 2. Contexto medido

- 32 reglas legacy con mecanismo (de 44 totales).
- Checks legacy por tipo: `xml_atributo` 20, `xml_presencia` 13,
  `texto_regex` 5, `secuencia_titulos` 3, `imagen_presencia` 1,
  `texto_en_lista` 1.
- 12 reglas sin mecanismo: `caratula_orcid`, `resumen_longitud`,
  `palabras_clave_minimo`, `sistema_citas`, `referencias_minimo_cuantitativo`,
  `referencias_minimo_cualitativo`, `referencias_minimo_revision`,
  `anexos_minimos_cuantitativo`, `anexos_minimos_cualitativo`,
  `proyecto_formato_general`, `proyecto_caratula_texto`,
  `suficiencia_profesional_formato`.
- 19 ítems en la sección `no_deterministas` del YAML.

## 3. Fases

### F1 — Migración completa al DSL (A) ✅ cerrada 2026-09-08

Script `scripts/migrar_legacy_a_dsl.py` con tabla de mapeo legacy → DSL:

| Legacy check | Sección DSL | Nota crítica de migración |
|---|---|---|
| `xml_atributo` | `atributo_xml` | `eq`/`all_eq`/`contains` directo |
| `xml_presencia` | `presencia_xml` | `exists`/`not_exists` |
| `texto_regex` | `patron_texto` | Los 5 usan **fullmatch** — fijar `comparacion: fullmatch` (default es `search`) |
| `texto_en_lista` | `lista_texto` | `ignore_case`, misma lista |
| `imagen_presencia` | `imagen` | `cantidad_minima`/`cantidad_maxima` |
| `secuencia_titulos` | `automata_secuencia` | Generar `estados` desde `valor_esperado`: `"(opcional)"` → `opcional: true`; indentación → `nivel_titulo`; patrón desde título normalizado |

- `tests/test_paridad_formatos.py`: mismo documento → mismo `List[RuleResult]`
  en ambos formatos (rule_id, passed, found).
- Salida: DSL unificado + `engine.py` sin bifurcación + legacy archivado
  (según decisión 2).

### F2 — Extender autómatas y gramáticas (B) ✅ cerrada 2026-09-09

- `validator/tokenizer.py`: flujo tipado `TITULO(nivel, texto)`, `PARRAFO`,
  `TABLA`, `IMAGEN`, `SALTO_SECCION`. `automata_secuencia` gana
  `tipo_flujo: titulos | documento` (hoy solo consume headings).
- `PDA` (push/pop) en `validator/automata.py` para estructuras anidadas;
  nueva sección DSL `automata_pila`.
- `GramaticaEstructura` capaz de consumir tokens del tokenizer (no solo
  headings).

### F3 — Mecanizar no_deterministas (C) ✅ cerrada 2026-09-09

Nuevos analizadores (implementados y con tests):

| Analizador | Uso | Reglas que mecaniza |
|---|---|---|
| `patron_cantidad` | contar palabras / matches regex / entradas (`;`/`,`); min/máx/rango | `resumen_longitud` (≥159 palabras), `palabras_clave_minimo` (≥3) |
| `conteo_nodos` | contador genérico de nodos XPath o párrafos de una sección (refactor de `imagen`; `cantidades_multiples` opcional) | `referencias_minimo_*` (≥20/30) |
| `lista_obligatoria` | subcadenas obligatorias por sección (ignore case) | `anexos_minimos_*` |
| `hipervinculo_texto` | detecta enlaces (w:hyperlink) que matcheen regex ORCID | `caratula_orcid` |

Más `proyecto_caratula_texto` (patron_texto + atributo_xml, 13pt).

**Decisión 4 (resuelta)**: se mecanizaron las **9 reglas claramente
verificables** (32 → **41/44**), aplicando las 3 de referencias mínimas sin
detectar tipo y con su severidad `warning` original. Quedan documentadas
como no-automatizables: `sistema_citas`, `proyecto_formato_general`,
`suficiencia_profesional_formato` (ver `reglas_unt.yaml`, bloque F3).
Ver `docs/CAMBIOS_MOTOR_DSL.md` Paso 11 y `tests/test_f3_mecanizacion.py` (21 tests).

### F4 — Mejoras de ingeniería (D) ✅ cerrada 2026-09-09

- Cache de consultas XML por `(parte, contexto, xpath)` en `ExtractedDocx`
  — evita re-ejecutar XPath por analizador (`extracted.xpath()`).
- Traza del autómata (`ruta_estados`) en `DFA`/`PDA`; expuesta al DSL como
  `AutomataSecuencia.ultima_ruta` / `AutomataPila.ultima_ruta`.
- Linter del DSL (`validator/dsl_check.py`): al compilar (`compilar()`),
  detectar estados inalcanzables, ciclos épsilon, regex inválida,
  `comparacion` sin `esperado`/`atributo` y esquema "todo opcional" —
  errores en carga (`DSLValidationError`), no en runtime.
- Evaluación paralela opcional: **NO incluida** (decisión 3).

Ver `docs/CAMBIOS_MOTOR_DSL.md` Paso 13 y `tests/test_f4_ingenieria.py`
(21 tests). Suite completa: **138 tests** + `PARIDAD: OK`. Tras las
correcciones de revisión 2026-09-09 (Paso 14): **140 tests**.

### F5 — Traza en el reporte (E) ✅ implementada 2026-09-15 (Semana 4)

- `RuleResult.detalle_traza` (opcional): "reconoció CARÁTULA→INTRODUCCIÓN,
  falta RESULTADOS".
- **Impacto contrato**: `tests/test_api_contract.py::test_resultados_campos`
  exige `set(keys) == CAMPOS_RESULTADO`. Campo nuevo = cambio **aditivo**
  al contrato → subir `CONTRATO_API.md` a v1.1 + coordinar con Integrante 1
  (AGENTS.md). Alternativa sin tocar la API: codificar la traza dentro de
  `encontrado` (ya existe). (decisión 1).

**Implementación (decisión 1, Opción A)**: se embebió la traza dentro de
`found` (`ruta=__inicio__ -> …`) cuando un autómata falla, **sin** tocar el
contrato de la API (se mantiene v1.1). El enlace API→DSL quedó activo
(`REGLAS_YAML_PATH` → `reglas_unt.yaml`, 41 reglas). Detalle en
`docs/diseno/09_f5_enlace_api_propuesta.md`.

### F6 — Tests de propiedad (F) ✅ cerrada 2026-09-09

- `tests/docx_factory.py`: factory determinista OPC. `configuracion_base()`
  genera el DOCX "bueno" (pasa **39/41**), `aplicar_mutacion(rule_id, cfg)`
  aplica un desvío **mínimo** por regla y `compilar_docx(cfg)` arma el paquete
  .docx.
- `tests/test_propiedad.py` (43 tests): `test_doc_bueno_pasa_39` verifica que
  el documento base solo falla los esquemas alternativos de estructura; y
  `test_mutacion_afecta_solo_esa_regla` (41 casos paramétricos) verifica que
  cada desvío cambia el resultado **solo** de su regla (comparación punto a
  punto `(passed, found)`).
- **Exclusiones documentadas** (no quebrar el aislamiento):
  - el documento base no puede cumplir simultáneamente los esquemas de
    estructura cuantitativo/cualitativo/revisión (`EXCLUIDAS_BASE`), por ser
    mutuamente excluyentes;
  - los autómatas embeben un contador `headings=N` en `found`: para las 3
    reglas `estructura_tinv_*` el observable comparado es solo `passed`;
  - reglas con mecanismo **idéntico** (no diferenciables por contenido):
    las 3 `referencias_minimo_*` (mismo conteo, mínimos 20/30/20) y
    `caratula_universidad_negrita_mayusculas`/`caratula_ciudad_pais_negrita`
    (el XPath `[1]` de "trujillo" resuelve a la línea de la universidad).
    Ver `REGLAS_ACOPLADAS` en el factory.

Ver `docs/CAMBIOS_MOTOR_DSL.md` Paso 12. Suite completa: **117 tests**.

## 4. Dependencias y orden

```
F1 (A) migración ──► F4 (D) ingeniería ──► F5 (E) traza/UX
        │                                   │
        ▼                                   ▼
F2 (B) tokenizer+PDA ──► F3 (C) mecanizar ◄─)  (necesita B)
        ▼
F6 (F) tests de propiedad (sobre todo lo anterior)
```

## 5. Cobertura de archivos prevista

Nuevos:
- `scripts/migrar_legacy_a_dsl.py`
- `validator/tokenizer.py`
- `validator/dsl_check.py`
- `tests/test_paridad_formatos.py`
- `tests/test_propiedad.py`
- `tests/docx_factory.py`
- `reglas_unt.yaml`
- `docs/PLAN_DSL.md`

Modificados:
- `validator/automata.py` (PDA, traza)
- `validator/compilador.py` (nuevos tipos, linter)
- `validator/analizadores.py` (patron_cantidad, conteo_nodos, hipervinculo)
- `validator/models.py` (detalle_traza, según decisión 1)
- `validator/api_models.py` (según decisión 1)
- `validator/engine.py` (sin bifurcación)
- `docs/CONTRATO_API.md` (según decisión 1)
- `tests/test_api_contract.py` (según decisión 1)

## 6. Contrato preservado

- `validate_docx(path, rules) -> List[RuleResult]` — sin cambio.
- `build_report(results) -> {semaforo, resumen, resultados}` — sin cambio.
- `RuleResult.to_dict()` — campos actuales sin cambio.
- CLI `python -m validator.cli` — sin cambio.
- API `ValidarResponse` — solo cambio **aditivo opcional** en `resultados[]`
  (decisión 1).

## 7. Decisiones de confirmación (estado)

1. **Contrato API (E)**: ¿agregar `detalle_traza` a `resultados[]` (cambio
   aditivo, sube `CONTRATO_API.md` a v1.1, requiere coordinar con Integrante 1)
   o embeber la traza en `encontrado` sin tocar la API? — pendiente (F5).
2. **YAML unificado (A)**: ✅ **tomada (transición)**. Se mantienen ambos
   formatos durante la transición: `unt_format_rules_schema.yaml` (legacy,
   sin cambios) y `reglas_unt.yaml` (DSL, 41 reglas). El motor auto-detecta
   por la clave `rules`/`reglas`.
3. **Evaluación paralela (D)**: ✅ **tomada (se omitió)**. La paralelización no
   se incluyó en F4 (complejidad a cambio de velocidad en documentos grandes);
   queda como mejora futura opcional. F4 entregó linter, cache de XPath y
   traza del autómata.
4. **Scope de (C)**: ✅ **tomada**. Se mecanizaron **9 reglas**
   (`resumen_longitud`, `palabras_clave_minimo`, 3 `referencias_minimo_*`,
   2 `anexos_minimos_*`, `caratula_orcid`, `proyecto_caratula_texto`),
   aplicando las referencias mínimas sin detectar tipo (severidad `warning`).
   Las 3 restantes más difíciles quedan documentadas como no-automatizables.
5. **Exclusiones de F6**: ✅ **tomada**. El documento base pasa **39/41**
   (no existe un DOCX que pase 41/41: los esquemas de estructura son
   mutuamente excluyentes). Las reglas con mecanismo idéntico se declaran en
   `REGLAS_ACOPLADAS` (`referencias_minimo_*` y la pareja
   universidad/ciudad-nota de negrita) y se validan con su conjunto esperado.
   Los autómatas de estructura se comparan por `passed` (su `found` embebe
   `headings=N`). Detalle en la sección F6.

## 8. Notas

- La migración debe preservar la semántica `fullmatch` de los 5 checks
  `texto_regex` legacy (el DSL `patron_texto` fija `comparacion: fullmatch`).
- El DFA mantiene reconocimiento `greedy` (puntero no retrocede) para
  preservar el comportamiento histórico; `backtracking` queda disponible.
- La carátula se satisface con el primer párrafo que contenga "universidad"
  (no usa estilo de encabezado), igual que el motor legacy.