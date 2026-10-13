# HANDOVER API ↔ Motor — Módulo de IA (Paso 0 + Funcionalidades 2, 3 y 5)

> **Para**: Integrante 1 (Backend/API)
> **De**: Integrante 3 (Motor de reglas / DSL)
> **Rama**: `semana8-modulo-ia`
> **Diseño**: `docs/diseno/16_modulo_ia.md`, `docs/discusion_modelo_ia.md`
> **Estado**: el **motor** (Paso 0, Func 2, Func 3 y Func 5) está implementado y
> probado; falta el **wiring** de la API y el frontend.

Este documento fija el contrato exacto para que I1 exponga el módulo de IA sin
tocar el motor. Nada de lo de aquí cambia `POST /validar` ni `incluir_prompts_ia`.

---

## 1. Qué ya está hecho (motor, área I3)

| Archivo | Contenido |
|---------|-----------|
| `validator/llm.py` | `LLMConfig`, `LLMClient` (Protocol), `OllamaClient`, `StubLLM`, `get_llm_client()`, `estado_ia()`, errores `ErrorIA` / `LLMNoDisponible` / `LLMError` |
| `validator/asistente.py` | `explicar_y_priorizar()`, `Explicacion` / `Prioridad` / `ExplicacionYPrioridad` (dataclasses advisory), `RespuestaIAInvalida`, `construir_prompt_explicar()`, `parse_explicacion()`, `ESQUEMA_EXPLICACION` |
| `validator/asistente.py` (Func 3) | `proponer_clasificacion()`, `EvidenciaClasificacion` / `ClasificacionPropuesta` (dataclasses advisory), `construir_prompt_clasificar()`, `parse_clasificacion()` |
| `validator/asistente.py` (Func 5) | `redactar_respuesta()`, `RedaccionRespuesta` (dataclass advisory), `construir_prompt_redactar()`, `parse_redaccion()`, `ESQUEMA_REDACCION` |
| `tests/test_llm.py`, `tests/test_asistente.py`, `tests/test_asistente_clasificacion.py`, `tests/test_asistente_redaccion.py` | tests, todos con `StubLLM`/`MockTransport` (sin red, sin GPU) |

**No hay dependencias nuevas**: `httpx` ya está en `flake.nix`. **No hay
secretos**: `OLLAMA_URL`/`OLLAMA_MODEL`/`OLLAMA_TIMEOUT` son configuración.

### 1.1 Firma del motor (lo que la API debe llamar)

```python
# validator/llm.py
def get_llm_client(config: LLMConfig | None = None) -> LLMClient:
    """Lanza LLMNoDisponible si no hay OLLAMA_URL.""" ...

async def estado_ia(
    config: LLMConfig | None = None, *, client: LLMClient | None = None
) -> dict[str, Any]:  # {"disponible": bool, "modelo": str}
    """Nunca lanza.""" ...
```

```python
# validator/asistente.py
async def explicar_y_priorizar(
    resultados: list[RuleResult],
    *,
    client: LLMClient,
    tipo_documento: str | None = None,
) -> ExplicacionYPrioridad: ...
```

`ExplicacionYPrioridad` = `explicaciones: list[Explicacion]`,
`prioridades: list[Prioridad]`, `modelo: str`.
`Explicacion(rule_id, explicacion)`; `Prioridad(orden, rule_id, razon, esfuerzo)`.

Errores a mapear:

| Excepción | Origen | HTTP sugerido |
|-----------|--------|---------------|
| `LLMNoDisponible` | falta `OLLAMA_URL` | `503` |
| `LLMError` | servicio LLM caído / respuesta HTTP no-200 | `503` |
| `RespuestaIAInvalida` | JSON no interpretable (tras reintento) | `422` |

### 1.2 Firma del motor — Funcionalidad 3 (clasificación asistida)

```python
# validator/asistente.py
@dataclass(frozen=True)
class EvidenciaClasificacion:
    estado: str                       # "sin_determinar" | "contradictorio" | "sin_estructura"
    tipos_candidatos: list[str]       # catálogo de tipos válidos (obligatorio)
    tipo_detectado: str | None = None
    detalle: str = ""                 # el `found` de `deteccion_tipo_documento`
    titulos: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class ClasificacionPropuesta:
    tipo_propuesto: str
    confianza: float                  # 0.0–1.0
    justificacion: str
    evidencia: list[str]
    alternativas: list[str]
    modelo: str = ""

async def proponer_clasificacion(
    evidencia: EvidenciaClasificacion,
    *,
    client: LLMClient,
) -> ClasificacionPropuesta: ...
```

**Cómo armar la `EvidenciaClasificacion`** (I1, desde el reporte determinista):

- `estado`: del `_extraer_metadata_tipo_documento(...)` que ya existe en `api.py`
  (`sin_determinar` / `contradictorio`), o `"sin_estructura"` si el centinela
  `tipo_documento_sin_estructura` está presente.
- `tipo_detectado`: `tipo_documento` efectivo (o `None`).
- `detalle`: el `found` del `RuleResult` de `deteccion_tipo_documento`.
- `titulos`: opcional; los títulos detectados (el motor ya los usa en la
  heurística). Si no se tienen a mano, se puede dejar vacío.
- `tipos_candidatos`: el catálogo de 8 tipos del `valor_esperado` de la regla
  `deteccion_tipo_documento` (`tinv_cuantitativo`, `tinv_cualitativo`,
  `tinv_revision_literatura`, `proyecto_cuantitativo`, `proyecto_cualitativo`,
  `informe_cuantitativo`, `informe_cualitativo`, `tsp`).

Errores a mapear: igual que la Func 2 (`LLMNoDisponible`/`LLMError` → `503`,
`RespuestaIAInvalida` → `422`). Además, `ValueError` si `tipos_candidatos` viene
vacío (error de uso, no de la IA): no debería llegar al endpoint si el catálogo
se arma bien.

### 1.3 Firma del motor — Funcionalidad 5 (redacción de la respuesta)

```python
# validator/asistente.py
@dataclass(frozen=True)
class RedaccionRespuesta:
    texto: str
    asunto: str
    modelo: str = ""

async def redactar_respuesta(
    resultados: list[RuleResult],
    *,
    client: LLMClient,
    tipo_documento: str | None = None,
) -> RedaccionRespuesta: ...
```

- Recibe el **mismo `resultados`** que la Func 2 (`validate_docx`); el motor
  ordena los fallos por severidad (errores primero) dentro del prompt.
- Si no hay fallos, **no llama a la IA** y devuelve `texto=""`, `asunto=""`
  (nada que comunicar); el endpoint puede devolver eso o un `204`/`200` vacío.
- Errores: igual que las Func 2/3 (`503`/`422`).
- El texto es **editable**: el encargado lo revisa/edita antes de enviarlo. El
  envío sigue siendo el flujo SMTP de `notificacion.py` (I1); este endpoint **no
  envía** nada.

---

## 2. Cambios que debe hacer I1

### 2.1 DTOs en `validator/api_models.py` (campos en español)

```python
class EstadoAsistenteAPI(BaseModel):
    disponible: bool
    modelo: str = ""

class ExplicacionAPI(BaseModel):
    rule_id: str
    explicacion: str

class PrioridadAPI(BaseModel):
    orden: int
    rule_id: str
    razon: str
    esfuerzo: str          # "bajo" | "medio" | "alto"

class ExplicacionYPrioridadAPI(BaseModel):
    modelo: str = ""
    explicaciones: list[ExplicacionAPI]
    prioridades: list[PrioridadAPI]
```

### 2.2 Endpoints en `validator/api.py`

**`GET /asistente/estado`** → `200 EstadoAsistenteAPI`
(usa `await estado_ia(...)`; nunca 503: el "deshabilitado" se expresa con
`disponible=false` para que el frontend pinte el botón).

**`POST /asistente/explicar`** → `200 ExplicacionYPrioridadAPI`
- `multipart/form-data` con `archivo` (.docx). Reutiliza **la misma validación
  de entrada** de `POST /validar` (extensión, content-type, tamaño, magic bytes).
- Flujo: guardar temporal → `validate_docx()` en `run_in_threadpool` (igual que
  `/validar`) → `build_report()`/`_extraer_metadata_tipo_documento()` para el
  `tipo_documento` efectivo → `await explicar_y_priorizar(resultados, client=..., tipo_documento=...)`.
- La llamada al LLM es async (`httpx`); **no** la despaches al threadpool.

**Inyección del cliente (para tests):** define una dependencia

```python
def obtener_cliente_ia() -> LLMClient:
    return get_llm_client()
```

y en el endpoint usa `client: LLMClient = Depends(obtener_cliente_ia)`.
Así los tests la sobrescriben con `app.dependency_overrides[obtener_cliente_ia] = lambda: StubLLM(...)`.

**Manejo de errores** (dentro del endpoint, antes del `except` genérico):

```python
except LLMNoDisponible as e:
    raise HTTPException(status_code=503, detail="Módulo de IA no disponible. " + str(e))
except LLMError as e:
    raise HTTPException(status_code=503, detail=f"Servicio de IA no disponible: {e}")
except RespuestaIAInvalida as e:
    raise HTTPException(status_code=422, detail=f"La IA no devolvió un formato interpretable: {e}")
```

Los errores de **archivo** (no docx, tamaño, corrupto) se comportan igual que en
`/validar` (400/413/415/422).

### 2.3 Documentación y OpenAPI

- Añadir los endpoints a `docs/CONTRATO_API.md`.
- Regenerar `docs/openapi_spec.json` con `python3 scripts/generate_openapi.py`.
- Bump de versión: `1.5.0` → `1.6.0` (cambio **aditivo**).

---

## 3. Configuración (operación)

| Variable | Efecto |
|----------|--------|
| `OLLAMA_URL` | **Obligatoria para habilitar** el módulo (p. ej. `http://127.0.0.1:11434`). Sin ella → 503 / `disponible=false`. |
| `OLLAMA_MODEL` | Modelo (por defecto `qwen2.5:3b`; GPU: `qwen2.5:7b`). |
| `OLLAMA_TIMEOUT` | Segundos (por defecto `180`). |

No van al escáner de secretos (no son credenciales). Procedimiento de descarga
del modelo y arranque del servicio: ver `docs/diseno/16_modulo_ia.md` §5.

---

## 4. Tests que debe agregar I1

`tests/test_api_ia_contrato.py`, con `StubLLM` inyectado (sin red):

1. `GET /asistente/estado` con IA deshabilitada → `200 {disponible: false}`.
2. `GET /asistente/estado` con `StubLLM` → `200 {disponible: true, modelo: "stub"}`.
3. `POST /asistente/explicar` con docx del factory + `StubLLM` → `200` con
   `explicaciones`/`prioridades` y sin alterar `POST /validar`.
4. `POST /asistente/explicar` sin `OLLAMA_URL` (`LLMNoDisponible`) → `503`.
5. `StubLLM` devolviendo basura → `422`.
6. `POST /asistente/explicar` sin archivo / archivo no-docx → `400`/`415`.

Los tests existentes de `/validar` **no deben cambiar**.

Para la Func 3 (`POST /asistente/clasificar`), en el mismo archivo:
7. `POST /asistente/clasificar` con un DOCX limítrofe + `StubLLM` → `200` con
   `tipo_propuesto`/`confianza`/`justificacion`/`evidencia`/`alternativas`.
8. `POST /asistente/clasificar` sin `OLLAMA_URL` (`LLMNoDisponible`) → `503`.
9. `StubLLM` devolviendo un tipo fuera del catálogo o basura → `422`.
10. `POST /asistente/clasificar` sin archivo / archivo no-docx → `400`/`415`.

Para la Func 5 (`POST /asistente/redactar`), en el mismo archivo:
11. `POST /asistente/redactar` con docx del factory + `StubLLM` → `200` con
    `texto`/`asunto`.
12. `POST /asistente/redactar` sin `OLLAMA_URL` (`LLMNoDisponible`) → `503`.
13. `StubLLM` devolviendo basura (sin `texto`/`asunto`) → `422`.
14. `POST /asistente/redactar` sin archivo / archivo no-docx → `400`/`415`.

---

## 5. Reglas de oro (recordatorio)

- La salida de IA **jamás** toca el semáforo ni produce `RuleResult`.
- La IA **no lee la tesis**: el prompt de la Func 2 y de la Func 5 usa solo el
  bloque de fallos; el de la Func 3, solo la evidencia que la heurística extrajo.
- La Func 3 es **human-in-the-loop**: la IA propone el tipo, el encargado lo
  confirma; la IA nunca cambia el tipo por sí sola.
- La Func 5 produce un **borrador editable**: la IA no envía nada (el envío es el
  flujo SMTP de `notificacion.py`).
- El módulo es **opt-in**: sin `OLLAMA_URL`, todo sigue funcionando con 503.

---

## 6. Pendiente (fuera de este handover)

- **Motor (I3)**: Funcionalidad 1 (semántico) — paso 4 de
  `docs/diseno/16_modulo_ia.md` §10. Las **Func 3 y 5 ya están listas en el
  motor** (`proponer_clasificacion` §1.2, `redactar_respuesta` §1.3); falta su
  endpoint.
- **API (I1)**: los endpoints `POST /asistente/clasificar` y
  `POST /asistente/redactar` (§2.2/§4) y el `POST /validar?tipo_confirmado=`
  para la re-validación human-in-the-loop (toque acotado en el flujo de
  compilación: `sobreescribir_tipo`).
- **Frontend (I2)**: necesita el estado (`GET /asistente/estado`) y los
  endpoints de las Func 2, 3 y 5 antes de sus botones.
