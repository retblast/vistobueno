# Bitácora Semana 9 — retblast

- **Integrante**: retblast (Integrante 1 — Backend / API)
- **Semana**: 9
- **Fechas**: 2026-10-26 → 2026-10-28 (semana en curso)
- **Rol**: Backend / API (FastAPI, contrato de la API, buzón de ficha,
  constancias y registro, escáner de secretos)
- **Ramas**: `docs/handover-auditoria-2026-10-26` (PR #64),
  `fix/api-aud13-contrato-upload` (PR #65),
  `fix/api-aud09-aud12-buzon-local` (PR #66),
  `test/api-aud21-aud24-contrato-ficha` (PR #67),
  `fix/api-aud22-cobertura-secretos` (PR #69). Cada PR se apila sobre el
  anterior; ninguno toca `master` directo.

---

## Objetivos de la semana

1. **Cerrar la parte de Int1 de la auditoría de comportamiento del
   2026-10-26** (27 hallazgos, 4 altos). Los hallazgos de Int1 son
   AUD-09, AUD-10, AUD-12, AUD-13, AUD-14, AUD-21, AUD-22 y el contrato
   de la ficha de depósito (AUD-24 a AUD-27, en coordinación con Int3).
2. **Escribir el criterio de aceptación del motor** para que Int3
   pueda corregir las capturas de la ficha y el texto de los mensajes.
3. **Mantener el contrato estable**: la forma de las respuestas no cambia
   en ningún PR de la semana (solo el endurecimiento de v1.10.0).

---

## Actividades realizadas

### 2026-10-26 — Auditoría de comportamiento y handover

- Corrí el motor contra **una tesis real** y contra **las 5 plantillas
  oficiales**. Resultado: 27 hallazgos (4 altos) y un hallazgo nuevo
  (`palabras_clave_minimo` es `error` y hace fallar las 5 plantillas).
- Escribí `docs/HANDOVER_AUDITORIA_2026-10-26.md`: evidencia medida,
  criterios de aceptación, decisiones tomadas, decisiones de dominio
  abiertas y una tabla de estado (§11) que cada responsable actualiza.
- Actualicé `AGENTS.md` con el bloque de aviso y la cláusula de cierre
  (PR #64). La cláusula obliga a que cada parte actualice la tabla §11 y
  el aviso al cerrarse.

### 2026-10-28 — Contrato de upload y deprecación del depósito (PR #65)

- `POST /validar` acepta `application/zip` además de
  `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  (AUD-13).
- El camino REST de depósito quedó **deprecado**: `depositar=true` ya no
  abre ninguna conexión y responde `deshabilitado` (AUD-11, AUD-14). El
  archivo lo adjunta el encargado en el formulario oficial; el userscript
  solo rellena los metadatos.
- Corregí la afirmación del README que decía que la app nunca escribía en
  DSpace: era falsa hasta este PR.

### 2026-10-28 — Buzón local y límite de peticiones (PR #66)

- El buzón de ficha solo se sirve desde el **loopback** (`403` desde
  cualquier otra IP) y, con `VISTOBUENO_API_TOKEN` definido, exige además
  el header `X-VistoBueno-Token` con comparación en tiempo constante
  (AUD-09).
- `POST /validar` tiene **límite de peticiones** por IP: ventana fija,
  `429` con `Retry-After`, configurable con `VISTOBUENO_RATE_LIMIT_MAX` y
  `VISTOBUENO_RATE_LIMIT_VENTANA_SEG` (AUD-12).
- El token compartido no lo necesita el userscript: siempre habla con
  `127.0.0.1`.

### 2026-10-28 — Contrato de la ficha y paridad real (PR #67)

- **Un extraído solo viaja con `detectado=true` si su valor es
  utilizable.** La API degrada a `detectado=false`, `valor=null` y
  `pagina=null` las capturas vacías y las que no tienen la forma que
  espera el campo (`dc.date.issued` tiene que contener un año). Versión
  de la API: **1.10.0**.
- `tests/test_captura_ficha.py`: DOCX con la **estructura real** de la
  carátula (etiqueta `AUTORES:` en párrafo propio, un autor por párrafo
  con ORCID intercalado, etiqueta `ASESORA:` aparte, año en la línea de
  portada, palabras clave en el RESUMEN). Los 4 criterios de Int3
  (AUD-24 a AUD-27) quedan como `xfail(strict=True)`: cuando el motor
  los cumpla, el `XPASS` estricto pone el CI en rojo.
- `tests/test_constancia.py`: el impacto en el papeleo (una constancia por
  autor real, con su matrícula), también con `xfail(strict=True)`.
- `tests/test_paridad_formatos.py`: saqué el `assert True` y agregué el
  fixture que faltaba (**tipo detectado con estructura incompleta**), que
  por fin ejercita la comparación de veredictos entre el motor DSL y el
  legacy (AUD-21).

### 2026-10-28 — Cobertura del escáner de secretos (PR #69)

- El escáner cubría 3 nombres de variables y asignaciones de una línea.
  Ahora marca cuatro clases: variable del proyecto, nombre genérico en
  mayúsculas (`*_PASSWORD`, `*_TOKEN`, `*_API_KEY`...), URL con
  credenciales embebidas y bloque YAML multilínea (AUD-22).
- Los límites quedan anotados en el docstring del script: solo nombres en
  mayúsculas, sin binarios, sin secretos codificados.

---

## Evidencias producidas

| Evidencia | Dónde |
|-----------|-------|
| Handover de la auditoría | `docs/HANDOVER_AUDITORIA_2026-10-26.md` |
| Contrato de la ficha v1.10.0 | `docs/CONTRATO_API.md`, `docs/openapi_spec.json` |
| Contrato utilizable (API) | `validator/api.py` (`_valor_utilizable`, `_forma_valida`) |
| Criterios de aceptación del motor | `tests/test_captura_ficha.py`, `tests/_caratula_real.py` |
| Paridad real | `tests/test_paridad_formatos.py` |
| Impacto en constancias | `tests/test_constancia.py` |
| Cobertura del escáner | `scripts/verificar_secretos.py`, `tests/test_verificar_secretos.py` |
| Bitácora | este archivo |

- Commits: `f015240` (handover), `2fd4d67` (upload + DSpace), `b45c4e2`
  (buzón local + límite), `23b8182` (contrato de la ficha + paridad),
  `6fe4a4b` y `31042c5` (escáner de secretos y corrección del PR).
- Suite: **660 tests pasan** y **5 quedan como `xfail(strict=True)`**
  (los criterios de Int3). `nix flake check` en verde.

---

## Relación con competencias curriculares

- **Ingeniería de Software II**: endurecimiento de contratos con
  invariantes comprobables (`detectado=true` implica valor utilizable),
  decisiones de diseño registradas (opción C del buzón, limitador in-app,
  deprecación del camino REST).
- **Estructura de Datos**: transporte de la ficha entre motor y API, y
  alineación por posición de autores y matrículas en la constancia.
- **Redes de Computadoras I**: control de acceso por loopback, token
  compartido, `429` con `Retry-After`, límites por IP.
- **Ingeniería de Software I**: contrato documentado entre áreas
  (handover ↔ diseño ↔ tests), trazabilidad de cada hallazgo a su PR.

---

## Dificultades y aprendizajes

- **Una suite verde que no comparaba nada**: el test de paridad terminó
  en un `assert True`. El fallo no era del motor, era del test. Ahora el
  caso "tipo detectado pero estructura incompleta" compara de verdad el
  veredicto de los dos motores.
- **El contrato de la ficha se rompe en dos lugares**: el motor captura
  mal y la API publica el valor tal cual. Arreglar solo el motor deja la
  API expuesta mientras el arreglo no llega; por eso la API degrada el
  valor y el motor arregla la captura. Los dos cambios son compatibles.
- **`xfail(strict=True)` como contrato entre áreas**: el criterio de
  aceptación no depende de la implementación del motor, solo del
  resultado. Cuando Int3 cumpla, el CI avisa.
- **Ampliar un escáner sin falsos positivos**: la regla "el nombre
  termina en la palabra que denota un secreto" evita marcar
  `CABECERA_TOKEN_BUZON` o `NMTOKEN`. Los falsos positivos rompen el
  hook y la gente deja de correrlo.
- **La numeración de PRs es compartida**: el #68 fue de Int2 (frontend) y
  mi PR quedó como #69. Corregí la referencia en un commit aparte.
- **Archivos de otra sesión**: `PR55_REVIEW_COMMENTS.md`,
  `docs/VERIFICACION_LOCAL.md` y `scripts/verify_all.sh` siguen sin
  trackear y no se tocaron (decisión de AUD-23). El segundo contiene una
  asignación de usuario de DSpace con valor: el escáner la marca, y por
  eso no debe entrar al repo tal cual.

---

## Plan de la semana siguiente

1. Mergear la pila de PRs en orden: #64 → #65 → #66 → #67 → #69.
2. Revisar los `XPASS` de los `xfail` cuando Int3 corrija AUD-24 a
   AUD-27 y quitar las marcas.
3. Revisar con Int2 que la pantalla de ficha respete el contrato v1.10.0
   (un campo `detectado=false` es un campo que el operador teclea).
4. Cerrar el resto de la auditoría cuando Int3 y Int2 entreguen su
   parte: recién entonces se borra el bloque de aviso de `AGENTS.md` y se
   deja la línea en `docs/cronologia_trabajo.md`.
