# Nota de coordinación — F5 (traza en el reporte) y conexión de la API al YAML DSL

**Autor**: IvanSanchezSil (Integrante 3 — Motor de reglas)
**Fecha**: 2026-09-09
**Destinatario**: Integrante 1 (Backend / API) y quien revise el PR consolidado #11
**Estado**: ✅ **implementada** (2026-09-15, Semana 4, PR #22) — Opción A:
traza embebida en `found` + `REGLAS_YAML_PATH` → `reglas_unt.yaml`. Esta nota
documenta la decisión original; el detalle de la implementación está en
`docs/diseno/09_f5_enlace_api_propuesta.md`.

---

## 1. Contexto

El motor de reglas migró a un formato declarativo (**DSL**) y quedó terminado
en su versión final consolidada en el PR #11 (`semana4-f4` → `master`):

| Fase | Contenido |
|---|---|
| F1 | Migración de las 32 reglas legacy al DSL (`reglas_unt.yaml`, `migrar_legacy_a_dsl.py`) |
| F2 | Tokenizer del documento + autómatas de pila (PDA), gramáticas con tokens |
| F3 | 9 reglas antes "no mecánicas" ahora verificables (32 → **41 reglas**) |
| F6 | Tests de propiedad con `docx_factory.py` (documento bueno 39/41; cada desvío rompe solo su regla) |
| F4 | Linter del DSL en carga, cache de consultas XPath y traza del autómata |

Este documento toca **dos temas que afectan a la capa API** (territorio del
Integrante 1 según `AGENTS.md`): la **F5** (traza en el reporte) y la
**conexión de la API al YAML nuevo**. El objetivo es que el equipo lea,
decida y coordine antes de ejecutar el switch.

---

## 2. ¿Qué es la "severidad" y por qué importa acá? (para todos los que lean)

Cada regla de validación tiene una **severidad**, que define cómo afecta a la
entrega:

- **`error`** → bloquea la entrega. Si una regla `error` falla, el **semáforo
  es rojo** ("no entregues la tesis hasta arreglarlo").
- **`warning`** → **no bloquea**. Se muestra en el reporte como advertencia,
  pero el semáforo sigue verde si no hay errores.

El semáforo se calcula **solo sobre los errores** (lo garantiza
`engine.build_report`; un filtro de visualización jamás puede ocultar un
bloqueo real).

Importa en este documento porque al conectar la API al YAML nuevo entran
**9 reglas nuevas** (hoy la API ni las evalúa), y **2 de ellas son `error`**:
son las únicas que podrían volver rojo un semáforo que hoy está verde. Las
nuevas **7 `warning`** solo agregan filas al reporte sin cambiar la entrega.

---

## 3. F5 — Traza del autómata en el reporte

### 3.1 Qué es

Cuando falla la estructura de un documento (ej. falta la sección RESULTADOS),
hoy el reporte dice algo genérico:

```
encontrado: "headings=29 faltantes=['RESULTADOS']"
```

Eso dice *qué falta* pero no *por dónde pasó* el autómata. F5 busca mostrar
el **recorrido real** para que un estudiante (o quien depure una regla) vea:

> "Reconoció CARÁTULA → RESUMEN → MARCO TEÓRICO; se quedó en BASES TEÓRICAS
> esperando METODOLOGÍA; falta METODOLOGÍA, RESULTADOS y CONCLUSIONES".

### 3.2 La materia prima ya existe

La F4 dejó lista la infraestructura a nivel motor:

- `DFA.ruta_estados` y `PDA.ruta_estados` — estados visitados del último
  reconocimiento (greedy y backtracking).
- `AutomataSecuencia.ultima_ruta` / `AutomataPila.ultima_ruta` — expuestos a
  los analizadores del DSL.

F5 es "solo" conectar eso al reporte (formatear la lista de estados a una
frase en español). No requiere tocar el motor de reconocimiento.

### 3.3 Decisión de contrato (decisión 1 del `PLAN_DSL.md`)

| Opción | Cambio | Impacto en el contrato |
|---|---|---|
| **A)** Campo nuevo `detalle_traza` en cada `resultados[]` | Campo **opcional** adicional | Cambio **aditivo** del contrato: `CONTRATO_API.md` sube a **v1.1**. El test `test_resultados_campos` exige `set(keys) == CAMPOS_RESULTADO` → hay que agregar el campo ahí. Coordinar también con Frontend (si valida esquema estricto). |
| **B)** Embeber la traza dentro de `encontrado` (campo que ya existe) | Ninguno | Sin tocar el contrato ni la API. La traza viaja dentro del texto de `encontrado`. |

- **Recomendación**: **Opción B** para el MVP — cero fricción de contrato y ya
  entrega el valor al estudiante. La API/UX puede separarlo como campo propio
  en una futura v1.1.
- **Nota**: incluso con la opción B, las reglas de estructura (`estructura_tinv_*`)
  tienen un detalle de reporte que incluye un contador interno (`headings=N`);
  la traza convivirá con ese detalle dentro de `encontrado`.

---

## 4. Conexión de la API al YAML nuevo (`reglas_unt.yaml`)

### 4.1 Estado actual

- `validator/api.py` (línea 35) carga **`unt_format_rules_schema.yaml`**
  (formato legacy, checks por XPath). Resultados que devuelve hoy: **32
  reglas** (las 32 mecanizadas de 44; las otras 12 no-deterministas no se
  evalúan).
- El motor ya soporta los **dos formatos**: `engine.validate_docx`
  auto-detecta DSL (clave `reglas`) vs legacy (clave `rules`). Por eso el
  switch es un cambio de **fuente de datos**, no de arquitectura.

### 4.2 El cambio de código es mínimo (1 línea)

```
validator/api.py: REGLAS_YAML_PATH = ... / "reglas_unt.yaml"
```

- Nada más de `api.py` cambia: `_get_rules()`, el endpoint `POST /validar`,
  la validación de entrada, el mapeo `RuleResult → ResultadoReglaAPI` y los
  metadatos son **agnósticos al formato**.
- La respuesta JSON mantiene los mismos campos (`paso`, `severidad`,
  `mensaje`, `esperado`, `encontrado`, …).

### 4.3 Qué cambia de comportamiento (lo importante)

1. **`resumen.total` y `metadatos.reglas_evaluadas` pasan de 32 → 41**.
2. **Entran 9 reglas nuevas** a evaluar en producción (ver tabla 4.4).
3. **Las 32 reglas legacy no cambian sus resultados**: la paridad 1:1 está
   garantizada por `test_paridad_formatos.py` y verificada contra plantillas
   reales (`PARIDAD: OK`). Aun así, se debe re-verificar tras el switch.
4. **Prompts IA se amplían**: `build_ai_help_section` (template) no cambia,
   pero ahora genera prompts también para las 9 reglas nuevas si fallan.

### 4.4 Las 9 reglas nuevas (y su severidad)

| Regla | Severidad | Qué valida | ¿Puede volver el semáforo rojo? |
|---|---|---|---|
| `resumen_longitud` | `warning` | El Resumen tiene ≥ 159 palabras | No |
| `palabras_clave_minimo` | **`error`** | Hay ≥ 3 palabras clave | **Sí** |
| `referencias_minimo_cuantitativo` | `warning` | ≥ 20 referencias | No |
| `referencias_minimo_cualitativo` | `warning` | ≥ 30 referencias | No |
| `referencias_minimo_revision` | `warning` | ≥ 20 referencias | No |
| `anexos_minimos_cuantitativo` | `warning` | Anexos obligatorios del esquema cuantitativo | No |
| `anexos_minimos_cualitativo` | `warning` | Anexos obligatorios del esquema cualitativo | No |
| `caratula_orcid` | `warning` | Carátula lleva hypervínculo ORCID | No |
| `proyecto_caratula_texto` | **`error`** | Línea "PROYECTO…" de la carátula a 13 pt | **Sí** |

**Implicancia directa**: las plantillas oficiales que hoy dan semáforo verde
podrían pasar a rojo si fallan `palabras_clave_minimo` o
`proyecto_caratula_texto` (por ejemplo: resumen con menos de 3 palabras clave,
o línea de proyecto con otro tamaño). Esto **es el comportamiento correcto**
según el manual — pero debe medirse y aceptarse explícitamente antes del
switch (ver sección 5).

### 4.5 Tests

- **Hay que actualizar** `tests/test_api_contract.py::test_paridad_apicli`
  (línea ~228): carga el YAML legacy **explícitamente** para comparar API vs
  motor. Hay que apuntarlo a `reglas_unt.yaml` (o comparar contra la misma
  fuente que usa la API).
- **No cambian** el resto de tests del contrato: `test_resultados_campos`,
  severidades, booleano de `paso`, metadatos, códigos de error — todos son
  agnósticos al formato.
- **Sugerido al hacer el switch**: nuevo assert de que
  `reglas_evaluadas == 41` (o al menos `> 32`) en la plantilla de prueba.

### 4.6 Documentación

- `docs/CONTRATO_API.md`: **no sube de versión** si no se agrega campo nuevo;
  agregar solo una nota de "fuente de reglas: `reglas_unt.yaml` (DSL, 41)".
- `README.md`: el párrafo que dice "La API todavía NO lo carga" queda
  obsoleto → actualizarlo.
- `metadatos.version_esquema` (hoy `"2026-09-01"`): actualizar la fecha al
  momento del switch. ✅ Hecho el 2026-09-15 (Semana 4): `reglas_unt.yaml`
  declara `version: "2026-09-01"` (reglas) y el contrato mantiene
  `metadatos.version_esquema` = fecha de la versión del esquema (sin cambio
  al campo en esta iteración F5).

### 4.7 Verificación (requiere la máquina local)

- La carpeta `recursos/` (plantillas oficiales reales) está en `.gitignore`:
  **no está en el repo**, solo local. Por eso la verificación contra
  documentos reales "no corre" en GitHub/CI — se hace en la máquina de quien
  trabaja.
- Pasos de verificación post-switch:
  1. `scripts/evaluar_paridad_plantillas.py` → `PARIDAD: OK` (las 32 legacy).
  2. Correr las plantillas con el DSL y revisar cuáles cambian de verde→rojo
     y por qué reglas `error` (¿`palabras_clave_minimo`?
     ¿`proyecto_caratula_texto`?).

---

## 5. Riesgos y decisiones para el equipo

1. **El semáforo puede cambiar** (más reglas evaluadas). Es esperado y
   correcto, pero hay que aceptarlo explícitamente. Si las 2 reglas `error`
   nuevas marcan plantillas oficiales como rojas y eso rompe expectativas,
   la alternativa histórica es bajarlas a `warning` (como se hizo el
   2026-09-01 con 3 reglas por desvío manual vs plantillas) — **pero eso es
   una decisión de producto con el usuario final, no técnica**.
2. **F5**: se recomienda **Opción B** (embeber en `encontrado`) para no
   tocar el contrato. La opción A solo si Frontend/API necesita un campo
   estructurado para navegar la traza.
3. **3 reglas siguen sin mecanizar** en ambos formatos (`sistema_citas`,
   `proyecto_formato_general`, `suficiencia_profesional_formato`): son
   semánticas, fuera del MVP.
4. **Coordinación por AGENTS.md**: el switch de `api.py` y los cambios de
   contrato son área del Integrante 1. Este documento busca ese acuerdo.

---

## 6. Checklist para Integrante 1

- [ ] Decidir la ruta de la F5: **A)** campo `detalle_traza` (contrato v1.1)
      o **B)** embeber en `encontrado` (recomendado).
- [ ] Aprobar/autorizar el switch `api.py → reglas_unt.yaml` (1 línea) y
      definir quién lo ejecuta (Backend, o Int3 con su OK).
- [ ] Actualizar `test_api_contract.py::test_paridad_apicli` a la fuente DSL.
- [ ] Re-verificar en `recursos/`: `PARIDAD: OK` + inventario de semáforos
      verde→rojo (y decidir de producto si aplica).
- [ ] Docs: `CONTRATO_API.md` (nota de fuente), `README.md`, `version_esquema`.