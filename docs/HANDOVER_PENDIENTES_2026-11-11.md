# Handover de pendientes — 2026-11-11

**Snapshot:** 2026-11-11T16:30Z
**Base de referencia:** `origin/master` = `d605d63` (merge del PR #91)
**Rama de este documento:** `docs/handover-pendientes-2026-11-11`
**Distribución:** publicada en `origin`; PR #92. La rama ya incorpora el
merge de #91 (`d605d63`).

**Verificación de la base:** `nix run .#test -- tests/ -q` →
**809 passed, 6 xfailed, 1 warning** en 39.22 s.

> Este documento es una **foto** del estado. Para el estado de un PR manda
> GitHub; para las reglas del proyecto manda `AGENTS.md`. Si hay conflicto,
> no “arreglar” el documento a mano: anotar la diferencia y actualizar la
> foto después de verificar.

---

## 0. Cómo leer este documento

### 0.1 Estados

| Estado | Significado |
|--------|-------------|
| `OPEN / DIRTY` | PR abierto con conflictos; no mergeable. |
| `OPEN / BEHIND` | PR abierto; la rama no está al día con `master`. |
| `MERGED` | Ya está en `master`; no se reabre. |
| `V` | Verificado con comando y salida. |
| `A` | Solo lo afirma el autor del PR; no fue verificado de forma independiente. |
| `?` | No revisado. |

### 0.2 Protocolo para agentes

1. Leer este snapshot y después verificar el PR en GitHub.
2. No editar ramas de otro autor.
3. No mergear sin aprobación humana.
4. Publicar hallazgos como comentario en el PR, con comando y salida.
5. Si el PR cambia, actualizar solo la tabla de estado y la fecha del
   snapshot; no reescribir el diagnóstico sin evidencia nueva.
6. Si GitHub y este documento difieren, manda GitHub para el estado del PR.
7. No tocar `AGENTS.md` sin aprobación explícita del usuario.

### 0.3 Regla de propiedad

- **#73 y #75:** los corrige su autor, `@IvanSanchezSil`. Otra persona no
  reemplaza la rama, no abre una rama de rescate y no mergea.
- **#91:** ya está mergeado. No se reabre.
- **Int1, Int2 y documentación:** cada tarea tiene dueño en la tabla de
  próximos pasos.

---

## 1. Estado de los PRs

| PR | Head | Estado | Última actualización | Dueño | Acción |
|----|------|--------|----------------------|-------|--------|
| #73 | `8c847a8` | **OPEN / DIRTY** | 2026-11-11T15:58Z | `@IvanSanchezSil` | El autor corrige AUD-05/06/07; no mergear. |
| #75 | `f6d3810` | **OPEN / BEHIND** | 2026-11-03T17:18Z | `@IvanSanchezSil` | Rebase y completar F-3/F-5/F-6; no mergear. |
| #91 | `d1d8485` | **MERGED** en `d605d63` | 2026-11-11T16:02Z | `@IvanSanchezSil` | Nada. No reabrir. |

`reviewDecision` está vacío en #73 y #75: no hay aprobación formal de ninguno
de los dos.

---

## 2. PR #73 — auditoría del motor

### 2.1 Qué se verificó

- `pytest tests/test_auditoria_motor.py -q` en la rama del PR:
  **12 passed**. Es una medición dirigida, no la suite completa.
- La tesis real de la auditoría no se versiona. El autor afirma que AUD-01
  da 0 fallos sobre ella, pero esa evidencia no fue reproducida por nosotros.
- La revisión inicial fue contra `72e7e38`; el autor respondió con
  `8c847a8`; la ampliación sobre AUD-07 es posterior.

### 2.2 Estado por tema

| Tema | Estado | Evidencia | Qué falta |
|------|--------|-----------|-----------|
| AUD-01 | `A`/`V` parcial | `_texto_con_tabs`, híbrido de `_norm_indice`, tests nuevos; 12/12 dirigidos. | El autor debe adjuntar evidencia sobre la tesis real. No reimplementar ni volver a la normalización que exige whitespace. |
| AUD-02 | `V` parcial | `hasta_final` en código, docs y linter; `encontrados=N/M`. | Confirmar con anexos reales que `faltan` no corta en 8. |
| AUD-03 | `V` | Adoptó `validator/detalle.py` de `master` (PR #78). | Nada. No duplicar el formato. |
| AUD-04 | `V` | Notas `EVALUADO` con fecha y decisión. | Al ajustar AUD-07, corregir la nota para que no justifique el filtro “bachiller”. |
| AUD-05 | `A` | Solo documentación; no hay cambio de motor. | Implementar el endurecimiento de `caratula_autores_tamano`. |
| AUD-06 | `A` | Solo documentación. | Implementar igualdad normalizada después de AUD-01. |
| AUD-07 | **Fallido** | El YAML conserva `bachiller` y `n_a_si_sin_nodos`; el test de Licenciado espera n/a. | Revertir el filtro y cambiar el criterio del test. |
| AUD-15 | `V` | Adoptó el escape de `master` (PR #78). | Nada. |
| AUD-20 | `V` parcial | Hay fixtures nuevos y tests con tabuladores. | Documentar que son opt-in; no afirmar que `configuracion_base()` replica la plantilla real. |

### 2.3 AUD-07 — corrección exacta

El estado actual del PR es:

```yaml
xpath: //w:body/w:p[contains(..., 'para optar')]
  [contains(..., 'bachiller')][1]/...
n_a_si_sin_nodos: true
```

y el test `test_aud07_otras_titulaciones_son_no_aplicables` espera:

```python
assert regla.passed
assert not regla.aplicable
assert regla.found == "no aplica a este documento"
```

Eso contradice la decisión del 2026-11-08.

**Cambio requerido:**

1. Quitar `[contains(..., 'bachiller')]` y dejar el XPath amplio de
   `para optar`.
2. Para la línea “Para Optar el Título Profesional de Licenciado…”:
   `aplicable=True`, `passed=False` y warning por 12 pt frente a 13 pt.
3. Conservar `n_a_si_sin_nodos` solo para el caso en que **no exista**
   ninguna línea `para optar`.
4. Cambiar el test de Licenciado para esperar evaluación. Agregar o mantener
   un test separado para un documento sin la línea y esperar n/a allí.
5. Actualizar la nota `EVALUADO` de `caratula_optar_grado_tamano`.

Archivos a tocar:

- `reglas_unt.yaml` (`caratula_optar_grado_tamano`).
- `tests/test_auditoria_motor.py` (los dos tests de AUD-07).
- `docs/HANDOVER_AUDITORIA_2026-10-26.md` (nota/estado, si corresponde).
- `docs/CONTRATO_API.md` si el ejemplo de `found` cambia.

### 2.4 AUD-05 y AUD-06 — no están implementados

**AUD-05:** endurecer solo la regla `error` `caratula_autores_tamano`:

- todos los runs con texto;
- todos los párrafos de autores hasta `ASESOR`/`ORCID`;
- mantener el selector actual de las reglas `warning`, con la limitación
  documentada.

No cambiar las reglas `warning` en este PR.

**AUD-06:** igualdad del título normalizado; `_sigpalabra` queda como
respaldo cuando el título normalizado tenga menos de 4 caracteres. Depende
de AUD-01: no implementar antes de que AUD-01 esté estable.

### 2.5 Cierre documental

- Corregir el body: no puede decir 757/4/6 si el estado real es otro.
- Actualizar la tabla §11 de `docs/HANDOVER_AUDITORIA_2026-10-26.md`.
- Actualizar `AGENTS.md` solo cuando el PR esté cerrado y con aprobación del
  usuario. No reescribir el aviso para justificar AUD-07.
- Actualizar `docs/CONTRATO_API.md`: el ejemplo todavía muestra
  `@w:val=['26']`.
- No afirmar que `_mutations.py` está sincronizado si no hay reglas nuevas.
- Resolver el conflicto con `master`; el PR sigue `DIRTY`.

### 2.6 Comentario publicado

El comentario operativo ya está publicado:

<https://github.com/retblast/vistobueno/pull/73#issuecomment-6800607073>

Resumen: quitar el filtro `bachiller`, hacer que Licenciado evalúe con
warning, conservar n/a solo para documentos sin la línea, implementar
AUD-05/06 y actualizar docs/body.

---

## 3. PR #75 — motor de ficha de depósito

> **Resuelto (2026-11-11)**: Int3 continuó el PR #75. Se corrigieron
> AUD-24 a AUD-27, F-4 (valores inservibles) y F-6 (`reglas`/`rules`); se
> retiraron los `xfail` de captura y constancia. La ficha sobre la tesis
> real devuelve dos autores, asesora, año 2026, abstract y palabras clave
> limpias. El diagnóstico de abajo queda como registro histórico.

### 3.1 Qué contiene realmente

El body dice “sin código de motor todavía”. Es falso. El diff contiene:

- `0447530` → contexto `caratula_ficha` y `is_caratula_ficha`.
- `21b08f2` → `seleccion` y `quitar_sufijo` en `AnalizadorExtraccion`.
- `833ec39` → reglas de ficha.
- `f6d3810` → `detectado=false` para valores vacíos y quita el xfail de
  AUD-25.

Medición dirigida:

```bash
nix run .#test -- tests/test_captura_ficha.py tests/test_extractor_edgecases.py -q
# 9 passed, 4 xfailed
```

La rama está `BEHIND`: necesita rebase antes de mergear.

### 3.2 Criterios de aceptación

Valores esperados sobre `tests/_caratula_real.py`:

| Campo | Valor esperado |
|-------|----------------|
| `dc.title` | `Estrategias lúdicas para mejorar la identidad cultural en estudiantes de primaria de una institución educativa, Trujillo 2024` (sin el prefijo `Título del trabajo de investigación:`; el sufijo se conserva según el plan del PR) |
| `dc.contributor.author` | `['Br. Apellido, Nombre', 'Br. Apellido2, Nombre2']` |
| `dc.contributor.advisor` | `Dra. Apellido, Nombre` |
| `dc.date.issued` | `2026` |
| `dc.description.abstract` | `El presente estudio analiza la relación entre las estrategias lúdicas y la identidad cultural en estudiantes de primaria.` |
| `dc.subject` | `['Educación', 'Cultura', 'Identidad cultural']` |

Los 4 xfail que deben pasar y luego quitarse:

```text
test_autores_un_por_parrafo
test_asesor_toma_el_parrafo_siguiente
test_anio_toma_el_anio_de_portada
test_palabras_clave_sin_puntuacion_final
```

### 3.3 Correcciones necesarias

#### Autores

`reglas_ficha.yaml` usa:

```yaml
xpath: //w:body/w:p[starts-with(..., 'autor')][1]/following-sibling::w:p[1]
```

Captura solo el primer párrafo. Debe:

- partir después de `AUTORES:`/`AUTORA:`;
- incluir todos los párrafos de autor;
- saltar líneas `https://orcid.org/...`;
- parar en `ASESOR`, `Línea`, `ORCID` u otra etiqueta conocida;
- no partir por la coma interna de “Apellidos, Nombres”.

Implementación recomendada: agregar al `AnalizadorExtraccion` un rango
`hasta`/`excluir` o un XPath de hermanos con corte; no resolverlo con
`[1]`.

#### Asesor

El XPath actual selecciona el párrafo de la etiqueta `ASESORA:` y el
`quitar_prefijo` lo deja vacío. Debe preferir el párrafo siguiente:

```yaml
xpath: //w:body/w:p[contains(..., 'asesor')][1]/following-sibling::w:p[1]
```

Si la etiqueta y el nombre están en el mismo párrafo, conservar el fallback
de `quitar_prefijo`. Agregar test para ambos formatos.

#### Año

El estado actual es:

```yaml
contexto: caratula_ficha
patron: \b(?:19|20)\d{2}\b
seleccion: ultimo
xpath: //w:body/w:p[contains(..., 'trujillo') ...][1]
```

La línea `2026` no contiene `trujillo`; el título contiene `Trujillo 2024`.
Por eso el `[1]` y `seleccion: ultimo` no alcanzan. La corrección debe ser:

```yaml
contexto: caratula_ficha
xpath: //w:body/w:p
filtro: \b(?:19|20)\d{2}\b
seleccion: ultimo
patron: \b(?:19|20)\d{2}\b
```

Así entran el título (2024) y la línea de portada (2026), y `seleccion:
ultimo` toma la última pieza con año. Alternativa: apuntar al párrafo que
porta `w:pPr/w:sectPr` y extraer el año de ahí. El test debe comprobar que
2024 no gana.

#### Resumen y palabras clave

`docs/ejemplos/doc_bueno.docx` tiene `RESUMEN` con
`w:pStyle w:val="Ttulo1"`. El fixture `tests/_caratula_real.py` lo crea como
párrafo normal. Esa es la causa de que `seccion()` no encuentre la sección.

**Decisión:** corregir el fixture, no agregar un fallback ambiguo al
analizador:

- crear `RESUMEN` con `add_heading(..., level=1)`;
- agregar exactamente este párrafo antes de la línea de palabras clave:
  `El presente estudio analiza la relación entre las estrategias lúdicas y la identidad cultural en estudiantes de primaria.`;
- mantener la línea `Palabras Clave:` como párrafo;
- comparar `dc.description.abstract` contra ese texto exacto y `dc.subject`
  contra la lista esperada.

Si la plantilla oficial demuestra otra estructura, documentarlo antes de
cambiar el analizador.

#### `detectado` con listas vacías

`validator/compilador.py` usa:

```python
"detectado": valor is not None and valor != ""
```

Una lista vacía `[]` sigue contando como detectada. Usar una comprobación
de valor utilizable (no vacío; si es lista, con elementos). Para un valor
vacío: `detectado=False`, `valor=None`, `pagina=None`.

#### Tests que faltan

- título sin prefijo y con sufijo conservado;
- resumen completo;
- dos autores;
- asesor en párrafo siguiente y en el mismo párrafo;
- año 2026 contra el 2024 del título;
- palabras clave sin punto final;
- lista vacía no detectada;
- `tests/test_constancia.py`: 2 autores → 2 constancias y 2 filas;
- F-6: `scripts/eval_contra_plantillas.py` acepta `reglas` y `rules`;
- paridad en `tests/test_paridad_formatos.py` con el caso real.

### 3.4 Body y bitácora

Corregir la afirmación “sin código” y actualizar F-1 a F-7. La rama está
`BEHIND`; el rebase debe hacerse antes de la revisión final.

---

## 4. PR #91 — mergeado

- Merge commit: `d605d63`.
- Estado: **MERGED** desde `2026-11-11T16:02Z`.
- Solo tocaba tests/docs del linter.
- No hay acción pendiente.
- No reabrir ni volver a mergear.
- La suite posterior al merge es **809 passed, 6 xfailed**.

---

## 5. Pendientes de Int1 — API y contrato

1. Agregar `ficha_deposito` a `tests/test_ejemplos_versionados.py`; hoy el
   golden no compara la ficha.
2. Corregir `docs/ejemplos/doc_bueno.docx` y `doc_malo.docx`: `_rels/.rels`
   referencia `media/logo.png` y la parte no existe. El extractor los lee,
   pero `python-docx` falla con `KeyError`.
3. Mantener el contrato v1.12.0. No cambiar `/validar`.
4. Actualizar `docs/HANDOVER_API_IA.md`: la versión real es v1.12.0.
5. Verificar `tests/test_constancia.py`, `tests/test_api_buzon.py` y
   `scripts/e2e_ficha_deposito.sh`.
6. Mantener `X-VistoBueno-Token` solo para peers remotos; el loopback no lo
   exige.
7. Completar el papeleo del piloto (Actividad 15, 16 y 17). El `.docx` lo
   adjunta el encargado; la app no lo sube.

---

## 6. Pendientes de Int2 — frontend y piloto

1. No cambiar la UI por la forma del JSON.
2. Verificar `frontend/src/components/FichaDeposito.jsx`,
   `frontend/src/ficha.js`, el timeout de 30 s y el foco del dropzone.
3. Corregir `docs/semana10_trabajo_integrante2.md`: el PR #78 ya está
   mergeado.
4. Agregar la bitácora S11 de Int2.
5. Ejecutar el clic manual real y el piloto en la sede.
6. Revisar Windows/WSL y el token del buzón antes de instalar en la máquina
   del operador.

---

## 7. Documentación y decisiones

### 7.1 Documentos que deben actualizarse al cerrar #73/#75

- `AGENTS.md`: aviso de auditoría y tabla de pendientes. **Requiere
  aprobación del usuario antes del commit.**
- `docs/HANDOVER_AUDITORIA_2026-10-26.md`: §11 y §13.
- `README.md`: estado de los PRs, reglas y flujo de ficha.
- `docs/PILOTO_OPERADOR.md`, `docs/PLAN_LOTES_PRE_PILOTO.md` y
  `docs/INSTALACION.md`: conteos y referencias al PR #78.
- `docs/diseno/16_modulo_ia.md`: estado real del módulo de IA.
- Script de evidencias del piloto, fuera del repo: agregar
  `FINES_SEMANA[12] = "2026-11-14"` (usar la ruta local del operador, no una
  ruta personal en este documento).

### 7.2 Decisiones cerradas

- Sangría literal; sin exención por estilo de cita.
- Anexos: el ítem 5 se llama «Base de datos».
- AUD-05: endurecer solo la regla `error`.
- AUD-06: igualdad normalizada después de AUD-01.
- AUD-07: no acotar a “bachiller”; el XPath amplio se mantiene.
- `palabras_clave_minimo`: `error` intencional.
- Cache compilado por hilo: no se implementa.
- `formato` en `/validar`: no se agrega.
- DSpace REST: deprecado.
- Mock de reporte: solo en desarrollo.

---

## 8. Verificación

```bash
# Suite completa en la base actual
nix run .#test -- tests/ -q
# Esperado: 809 passed, 6 xfailed

# PR #75: captura de ficha y extractor
nix run .#test -- tests/test_captura_ficha.py tests/test_extractor_edgecases.py -q
# Los 13 casos actuales deben pasar; los tests nuevos se suman.

# PR #73: auditoría del motor (solo en la rama del PR)
nix run .#test -- tests/test_auditoria_motor.py -q
# Los 12 casos actuales deben pasar; los tests nuevos se suman.

# Flujo completo de ficha
nix run .#test-ficha-deposito

# Flake y linter
nix flake check
```

La tesis real de la auditoría no se versiona: contiene datos personales. La
verificación se hace en una copia local fuera del repo y se reporta con
placeholders.

---

## 9. Lo que no se hace

- No mergear #73 ni #75.
- No abrir una rama de rescate de #73.
- No reabrir #91.
- No editar ramas de otro autor.
- No debilitar el CI ni saltar checks.
- No cambiar `palabras_clave_minimo` a `warning`.
- No agregar `formato` a `/validar`.
- No escribir en la API de DSpace.
- No subir PII, tesis reales, ORCID, DNI ni credenciales.
- No modificar `AGENTS.md` sin aprobación explícita.

---

## 10. Próximos pasos

1. `@IvanSanchezSil` corrige #73: AUD-05, AUD-06, AUD-07 y conflicto.
2. `@IvanSanchezSil` rebasea #75 y completa F-3/F-5/F-6.
3. Revisar #73 y #75 con la suite completa y la evidencia de la tesis real.
4. Int1 agrega la ficha al golden y corrige los DOCX de ejemplo.
5. Int2 cierra bitácoras y ejecuta el piloto.
6. Mover este handover a una rama/PR y actualizarlo después de cada push
   relevante. No dejarlo como commit local de `master`.
7. Actualizar `AGENTS.md` y la tabla §11 solo después de los cierres y con
   aprobación.
