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
  anterior; ninguno toca `master` directo. El 2026-10-30 el trabajo siguió
  en la rama `fix/api-hardening-b0-b1` (11 commits, PR pendiente).

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

### 2026-10-30 — Endurecimiento de la API y del userscript (rama `fix/api-hardening-b0-b1`)

Trabajo de cierre de la parte de Int1, en 11 commits sobre
`fix/api-hardening-b0-b1` (sin push al momento de escribir esto).

**Acceso y host (AUD-28, AUD-30):** un middleware ASGI rechaza con `400`
cualquier `Host` que no esté en `VISTOBUENO_HOSTS` (por defecto, loopback),
y **todos** los endpoints (no solo el buzón) exigen que la conexión venga
de la máquina donde corre la app. El `__main__` de la API ata a
`127.0.0.1` y sale con error si se levanta en otra dirección sin token.

**Cupo de CPU (AUD-31):** el límite de peticiones era una ventana fija que
no venía del coste real. Ahora es un cubo que acumula los segundos de trabajo
medidos y se fuga a 2 s por minuto (1 s para el papeleo): el mismo equipo
sufre la misma presión con una máquina 4 veces más lenta.

**Fórmulas en el registro (AUD-29):** `fila_registro()` neutraliza en la
fuente los valores que empiezan por `=`, `+`, `-` o `@`, así que ni el CSV
ni el XLSX los interpretan como fórmula.

**Hora de Perú (AUD-32):** el userscript fechaba el clic con UTC, cinco
horas adelantado en Lima. Ahora formatea el instante en `America/Lima`
(`src/reloj.js`) y la API normaliza el `timestamp`: sin offset se
interpreta como Lima, con offset se convierte a Lima.

**Botón "+" real del formulario (AUD-33):** la lista de selectores del
userscript no coincidía con el DOM real: el botón es
`button.ds-form-add-more` y cada fila repetible vive en un contenedor
`[id$="_array"]`. El ejecutor busca el botón **dentro del contenedor del
propio campo**, así que agregar un autor no agrega una fila de asesor. La
página del ítem se reconoce por `meta[name="citation_title"]` y el reporte
exige que el título coincida con la ficha preparada.

**Escáner de secretos (AUD-34):** una clave JSON o YAML entre comillas
(`"DB_PASSWORD": "..."`) pasaba sin bloquear. El patrón ahora acepta comillas
opcionales alrededor del nombre.

**Verdad de los documentos:** el diagrama de `docs/FLUJO_API.md` describía un
depósito que ya no existe, el DTO y el contrato anunciaban estados que el
flujo vigente nunca emite, el valor por defecto de la sección de DSpace no
era el de la instancia real (`traditionalPeruOne`) y el README afirmaba que
las 5 plantillas oficiales pasaban. Todo corregido.

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
| Endurecimiento de acceso y host | `validator/api.py` (`MiddlewareHostConfiable`, `verificar_acceso_local`), `tests/test_api_acceso.py` |
| Cupo de CPU adaptativo | `validator/api.py` (`LimitadorCPU`), `docs/CONTRATO_API.md` v1.11.0 |
| Hora de Perú | `tools/dspace-fill/src/reloj.js`, `validator/api.py` (`_parsear_timestamp`), `tests/test_constancia.py` |
| Botón "+" y filtro de ítem | `tools/dspace-fill/src/ejecutor.js`, `src/compuertas.js`, `src/wrapper.js` |
| Propuestas del motor para Int3 | `docs/HANDOVER_AUDITORIA_2026-10-26.md` §12 |
| Bitácora | este archivo |

- Commits: `f015240` (handover), `2fd4d67` (upload + DSpace), `b45c4e2`
  (buzón local + límite), `23b8182` (contrato de la ficha + paridad),
  `6fe4a4b` y `31042c5` (escáner de secretos y corrección del PR).
- Commits del 2026-10-30 (rama `fix/api-hardening-b0-b1`): `8efffd7`
  (acceso, Host y cupo de CPU), `f0ba1f0` (hora de Perú), `22e6a19`
  (botón "+" y filtro de ítem), `efca435` (escáner y documentos), `1814bc3`
  (propuestas del motor en el handover), `3aee3cf` y `b562b4c` (limpieza),
  `081d14b` (deriva OpenAPI), `fac166a` (ruido jsdom), `955e233` (conteo de
  tests) y `c11e4dc` (bloque de aviso de `AGENTS.md`).
- Suite: **693 tests pasan** y **6 quedan como `xfail(strict=True)`**
  (los criterios de Int3). **30 tests** del userscript. `nix flake check` en
  verde y ensayo general con "FLUJO COMPLETO OK".

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
- **Crucé la frontera del área y hubo que revertir**: implementé el cache
  compilado del motor (`engine.py`, `compilador.py`), las notas `EVALUADO`
  (`reglas_unt.yaml`) y el escape del exportador. Son área de Int3, y la
  tabla de responsabilidades de `AGENTS.md` es explícita. Los tres trabajos
  eran correctos y estaban verificados, así que los revertí y los dejé
  **documentados con el diff exacto en §12 del handover**, con el criterio
  de aceptación. La lección no es "no tocar el motor": es que un cambio
  bueno en el área de otro no es un cambio gratuito, porque le ensucia el
  merge justo donde va a trabajar.
- **El spec OpenAPI es parte del contrato**: cambiar el docstring de un
  modelo Pydantic cambia `docs/openapi_spec.json`. Loolvidé al tocar los
  DTO de depósito y la CI se puso roja (`generate_openapi.py --check` lo
  detecta). El paso de deriva quedó en el script de verificación local.
- **Los placeholders del escáner tienen forma propia**: el escáner acepta
  `dummy`, `prueba`, `test`, `changeme`, `<valor>` y lo que termina en
  `-de-prueba`. Un `export VISTOBUENO_SMTP_PASSWORD="clave"` en un documento
  es una violación, aunque "clave" sea un valor inventado.
- **Un documento que promete algo que el código no hace**: la guía local
  decía que el script de verificación "se detiene en el primer fallo" y no
  lo hacía (acumula los pasos). También tenía el nombre de variable
  equivocado (`VISTOBUENO_SMTP_PASS` en vez de `..._PASSWORD`). Corregido;
  sigue sin trackear por decisión de AUD-23.
- **Archivos de otra sesión**: `PR55_REVIEW_COMMENTS.md`,
  `docs/VERIFICACION_LOCAL.md` y `scripts/verify_all.sh` siguen sin
  trackear (decisión de AUD-23). Se actualizaron **en local** para que no
  apunten a variables inexistentes ni a conteos viejos, pero no entran al
  repo.

---

## Plan de la semana siguiente

1. Mergear la pila de PRs en orden: #64 → #65 → #66 → #67 → #69.
2. Push y PR de la rama `fix/api-hardening-b0-b1` (11 commits) una vez que
   el equipo lo revise.
3. Probar a mano el rebinding de DNS en la máquina del operador: el
   ataque y el control positivo están en
   `docs/HANDOVER_DESPLIEGUE_MAQUINA_OPERADOR.md`.
4. Revisar los `XPASS` de los `xfail` cuando Int3 corrija AUD-24 a
   AUD-27 y quitar las marcas.
5. Revisar con Int2 que la pantalla de ficha respete el contrato v1.10.0
   (un campo `detectado=false` es un campo que el operador teclea).
6. Cerrar el resto de la auditoría cuando Int3 y Int2 entreguen su
   parte: recién entonces se borra el bloque de aviso de `AGENTS.md` y se
   deja la línea en `docs/cronologia_trabajo.md`.
7. Cerrar con el equipo las 7 decisiones de dominio abiertas (§8 del
   handover): de ellas dependen AUD-05, AUD-06, AUD-07 y AUD-18.
