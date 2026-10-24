# Bitácora Semana 9 — ivanSanchezSil

- **Integrante**: Iván Sánchez Silva (Integrante 3 — Motor de reglas)
- **Semana**: 9
- **Fechas**: 2026-10-19 → 2026-10-23
- **Rol**: Motor de reglas / Procesamiento (DSL, extractor, checks)
- **Rama**: `semana9-ficha-deposito`, sobre `semana8-deposito-ficha` (módulo de
  depósito de I1, contrato v1.7.0), porque la extracción consume el handover y
  la ficha de depósito que aún no están en `master`.

---

## Objetivos de la semana

1. **Extracción de la ficha de depósito (motor)**: exponer, con su página, el
   texto completo de los datos que la SPA de I2 necesita para pre-llenar el
   formulario oficial de DSpace. El handover (2026-10-19) congeló el mapa en
   **8 claves** (`dc.title`, `dc.contributor.author`,
   `dc.contributor.advisor`, `dc.description.abstract`, `dc.subject`,
   `dc.date.issued`, `escuela` y `renati.juror` opcional); grado/título y
   línea de investigación quedaron **descartados** (los pre-llena el servidor).
   Pedido de I1 en `docs/HANDOVER_MOTOR_FICHA_DEPOSITO.md`; plan de producto en
   `docs/PLAN_FICHA_DEPOSITO.md`.
2. **Determinar la viabilidad de `renati.juror`** (opcional): ¿los nombres del
   jurado salen de forma confiable de la sección de firmas en plantillas y
   tesis reales?
3. **Solo lectura**: la captura no cambia el semáforo ni agrega reglas de
   validación (invariante del plan §3, decisión 14).
4. Mantener la suite completa en verde, con `ruff`, `ruff format` y `mypy`.

---

## Actividades realizadas

### 2026-10-19/20 — Diseño del mecanismo de exposición

- **Decisión (híbrido)**: el único pedido de I1 permite dos opciones (campo
  `valores` en `RuleResult` vs sección DSL `extraccion` con contexto). Se eligió
  una **sección DSL nueva `extraccion`** + un campo de transporte
  (`RuleResult.ficha`), porque:
  - el formato lo decide el motor (uniforme), no cada regla a mano;
  - la API no parsea `found` ni inventa heurísticas por regla;
  - aprovecha el `xpath`/`seccion` que las reglas ya declaran.
- Documentado en `docs/diseno/17_extraccion_ficha.md` (mecanismo, alternativa
  descartada, mapa de campos, verificación).

### 2026-10-20 — Implementación del analizador y el transporte

- **`AnalizadorExtraccion`** (`validator/analizadores.py`): analizador de hoja
  de SOLO LECTURA (siempre `passed=True`). Soporta `xpath` o `seccion`
  (tokenizer), `modo` texto/lista, `separador`, `etiqueta`, `patron`,
  `quitar_prefijo`, `filtro`, `unir`, y resuelve la **página** del nodo
  (con mapa texto→nodo para las capturas por sección).
- **`RuleResult.ficha`** (`validator/models.py`): canal de lectura con
  `{campo, valor, pagina, detectado}`; `RuleResult.captura` marca los resultados
  de captura para que `build_report` los excluya del semáforo y del resumen.
- **Compilador** (`validator/compilador.py`): sección `extraccion` registrada en
  `SECCIONES_ANALIZADOR` y `_FABRICAS`; `ReglaCompilada._ficha()` resuelve la
  página y normaliza.
- **Linter** (`validator/dsl_check.py`): `extraccion` en `_SECCIONES`.
- **Engine** (`validator/engine.py`): `validate_docx(..., ficha_data=None)`
  evalúa el ruleset de captura sobre el MISMO DOCX extraído;
  `load_ficha_rules()`; `build_report` publica `reporte["ficha"]` como
  `dict[campo] = {valor, pagina, detectado}` (contrato del handover §4).

### 2026-10-20 — Ruleset de captura y ajuste de XPaths

- **`reglas_ficha.yaml`** (7 capturas en carátula/cuerpo) en archivo aparte de
  `reglas_unt.yaml`: no comparte el invariante de mutaciones de
  `tests/_mutations.py` (una captura read-only no tiene desvío mínimo con
  sentido) ni altera el conteo de 49 reglas verificables. La 8ª clave
  (`renati.juror`) no tiene regla: ver la actividad de viabilidad.
- Ajustes verificados contra el factory determinista:
  - `dc.title` / `dc.contributor.author`: XPath anclado a la carátula, con la
    exclusión de las líneas institucionales (universidad, facultad, escuela,
    programa) para no capturar el membrete.
  - `dc.contributor.advisor`: `quitar_prefijo` de la etiqueta "Asesor(a): ".
  - `escuela`: XPath sobre la línea "ESCUELA ACADÉMICO PROFESIONAL DE…" (o
    "Programa"), el dato para la columna ESCUELAS del registro.
  - `dc.date.issued`: `patron` con año de 4 dígitos, excluyendo la línea
    "UNIVERSIDAD NACIONAL DE TRUJILLO" (contiene "trujillo", quirk heredado).
  - `dc.subject`: `filtro` + `etiqueta` + `separador` para las claves de la
    línea "Palabras clave: a, b, c".
  - `dc.description.abstract`: `unir` + `filtro` negando la línea de palabras
    clave.

### 2026-10-20 — Viabilidad de `renati.juror`

- Inspección de la plantilla oficial y de la tesis real
  (`recursos/tesis/tesis_linares_2026.docx`): la plantilla trae placeholders
  ("Jurado Evaluador" + `____` + Presidente/Secretario/Miembro) y la tesis real
  deja la sección ("Jurado Dictaminador") en **blanco**. La disposición varía
  entre plantillas y tesis.
- **Conclusión**: no se implementa captura de `renati.juror`; queda
  `detectado=false` y el operador lo teclea (como preveía el handover). Evita
  publicar un dato falso en un metadato oficial de RENATI.

### 2026-10-20 — Tests y verificación

- **`tests/test_ficha_extraccion.py`** (5 tests): captura de los 7 campos con
  regla (los valores esperados, con su página de origen), la ausencia de
  `renati.juror` como `detectado=false`, el invariante de solo lectura (mismo
  semáforo y mismo `resumen` con/sin ficha) y ruleset ausente → `{}`.
- Suite completa en verde (**482 tests**, 5 de ellos nuevos), `ruff check` /
  `ruff format --check` / `mypy` sin hallazgos. La rama parte de
  `semana8-deposito-ficha` (módulo de depósito de I1, contrato v1.7.0), así que
  la base de la suite es la de esa rama (477) más los 5 tests de la ficha.

### 2026-10-20 — Rebase del PR #49 (semana 8) sobre `master`

- **Contexto**: el PR #49 (`semana8-modulo-ia`) salía desincronizado respecto a
  `master`, que ya incluía el módulo de depósito en DSpace (PR #53) y los fixes
  del frontend con el contrato v1.5 (PR #54). Mergearlo tal cual habría
  revertido esos cambios; retblast pidió rebase explícito antes de aprobar.
- **`git rebase origin/master`**: 15 commits reaplicados; conflictos en
  `AGENTS.md`, `README.md` y `docs/diseno/00_indice_diseno.md`. Criterio de
  resolución: partir de la versión de `master` (que ya trae DSpace, prompt
  único, auditoría UX hasta C41 y el contrato v1.6.0) y **re-aplicar encima las
  diferencias reales del motor**: la fila de tests de IA en `AGENTS.md`, la
  mención del módulo local advisory en `README.md`, el incremento a **49 reglas**
  mecanizadas y "control de cambios" en el listado del DSL.
- **Sin pérdidas**: `origin/master` quedó como ancestro de HEAD y
  `git diff --name-status origin/master HEAD` no muestra borrados — DSpace,
  `verificar_secretos.py` con credenciales DSpace y los fixes del frontend
  permanecen intactos.
- **Verificación post-rebase**: suite de **547 tests** en verde, `ruff check`,
  `ruff format --check` y `mypy` limpios, `openapi_spec.json` regenerado
  (v1.6.0, sin cambios).
- **Sincronización de conteos**: el rebase dejó los documentos con la cifra
  previa (519); un commit atómico alineó la suite real (**547 tests**) en
  `README.md`, `AGENTS.md`, `docs/diseno/00_indice_diseno.md` y
  `docs/diseno/16_modulo_ia.md`.
- **Push**: `--force-with-lease` a `fork/semana8-modulo-ia` (rama del PR),
  seguro porque el remoto seguía en el commit del que se partió. CI verde
  (`check` y `Build frontend (vite)`) y PR en estado `MERGEABLE` / `CLEAN`.

---

## Evidencias producidas

- `docs/diseno/17_extraccion_ficha.md` — diseño y conclusión de viabilidad.
- `reglas_ficha.yaml` — 7 reglas de captura (las 8 claves del contrato menos
  `renati.juror`, que no se captura; archivo nuevo).
- `validator/analizadores.py` — `AnalizadorExtraccion`.
- `validator/models.py` — `RuleResult.ficha`, `RuleResult.captura`.
- `validator/compilador.py`, `validator/dsl_check.py` — sección `extraccion`.
- `validator/engine.py` — `validate_docx` con `ficha_data`, `load_ficha_rules`,
  `reporte["ficha"]`.
- `tests/test_ficha_extraccion.py` — 5 tests.
- `validator/api.py` / `validator/api_models.py` / `validator/buzon.py` —
  módulo de depósito de I1 ya integrado localmente (contrato v1.7.0).

---

## Relación con competencias curriculares

- **Estructura de Datos**: transporte estructurado de datos
  (`dict[campo] → {valor, pagina, detectado}`) desde el motor a la API.
- **Ingeniería de Software II**: separación captura vs validación; diseño con
  alternativas, invariante de solo lectura con test.
- **Ingeniería de Software I**: contrato documentado entre áreas (handover ↔
  diseño) y trazabilidad al manual oficial.

---

## Dificultades y aprendizajes

- **La carátula reaparece**: los mismos quirks de los XPaths legacy
  ("trujillo" en la universidad, la etiqueta del asesor) hubo que resolverlos
  igual en las capturas; sirvió reutilizar los XPaths ya probados.
- **Capturas por sección sin nodo**: el tokenizer no lleva el nodo, así que la
  página se resuelve por un mapa texto→`w:p`; sin él, resumen y palabras clave
  habrían quedado sin página.
- **No inflar el reporte**: anexar resultados de captura cambia los totales del
  `resumen`; el flag `captura` los excluye sin perder las capturas.
- **Un ruleset aparte**: meterlas en `reglas_unt.yaml` habría obligado a 8
  mutaciones y a tocar todos los conteos; el archivo separado mantiene el
  invariante de la suite.

---

## Plan de la semana siguiente

1. Coordinar con **I1** el *wiring* de la API: pasar `load_ficha_rules()` a
   `validate_docx` en `POST /validar` (una línea; documentado en el diseño §8).
2. Revisar cualquier desvío de los XPaths de captura con nuevas tesis reales.
3. Cerrar el **módulo de IA** pendiente: *wiring* de endpoints
   (`GET /asistente/estado`, `POST /asistente/explicar|clasificar|redactar|semantico`)
   y botones del frontend con I2.
