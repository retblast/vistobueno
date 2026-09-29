# Handover: cambios de API pendientes (Semana 6, paso 7)

**Destinatario**: Integrante 1 (Backend / API).

**Este documento no modifica tu código.** Los pasos 1–6 de
`docs/PLAN_TIPO_DOCUMENTO.md` cambiaron el motor; la API no se actualizó a
propósito, para no romper el contrato publicado. Este es el detalle de lo que
queda por hacer en `validator/api.py`, `validator/api_models.py`,
`docs/CONTRATO_API.md` y `docs/openapi_spec.json`, que son área tuya según
`AGENTS.md`.

**Estado**: el motor ya está terminado y con tests en verde. Este handover no
bloquea ningún otro paso del plan.

---

## 1. Qué cambió en el motor que la API todavía no refleja

Los pasos 1–6 introdujeron dos conceptos nuevos:

1. **Aplicabilidad**: una regla puede no aplican a un documento concreto
   (`RuleResult.aplicable`). Hoy solo lo usan las 3 reglas de estructura
   (`estructura_tinv_*`), que dependen del tipo de documento.
2. **Reglas centinela**: ante un tipo `sin_determinar` o `contradictorio` el
   motor sintetiza un error propio (`tipo_documento_no_determinado` /
   `tipo_documento_contradictorio`) en vez de activar las estructuras. No son
   reglas del YAML: se generan en `CompilerDSL.ejecutar()`.

`build_report()` ya expone los conteos (`total_evaluadas`,
`reglas_no_aplicables`) y **filtra** las no aplicables de `resultados`.

---

## 2. El problema concreto: la API reporta como aprobado lo que nunca revisó

`validator/api.py:89` mapea `resultados_motor` (**crudos**, sin filtrar) a los
DTOs, y `_rule_result_a_dto` (`validator/api.py:65`) **no copia `aplicable`**.

Una regla no aplicable tiene `passed=True` —no falló porque no se evaluó— y por
lo tanto sale con `paso=true`, **idéntica a una regla que pasó de verdad**.

Medidas sobre el motor actual con `reglas_unt.yaml`:

| Escenario | `resultados` (lo que sale hoy) | `resumen.total` | `total_evaluadas` *(no sale)* | no aplicables *(no sale)* | centinela | semáforo |
|---|---|---|---|---|---|---|
| Documento bueno (cuantitativo) | 48 | 48 | 46 | 2 | — | verde |
| Anexo 10 contradictorio | 49 | 49 | 46 | 3 | `tipo_documento_contradictorio` | rojo |

Dos consecuencias visibles para el estudiante:

- En el **documento bueno**, el frontend muestra ✓ en
  `estructura_tinv_cualitativo` y `estructura_tinv_revision_literatura`. Nunca
  se revisaron: son 2 verdes falsos.
- `resumen.total` dice 48 (o 49) cuando solo se evaluaron 46, y **no hay forma
  de que el frontend lo sepa**, porque el dato no viaja.

---

## 3. Cambios necesarios

### 3.1 `ResultadoReglaAPI`: exponer la aplicabilidad

```python
aplicable: bool = Field(
    True,
    description="Si la regla se evaluó. False = no aplica a este tipo de documento.",
)
```

Y en `_rule_result_a_dto`, junto al mapeo de `paso` (`validator/api.py:69`),
añadir:

```python
aplicable=r.aplicable,
```

El default `True` mantiene la compatibilidad si el campo llega ausente.

### 3.2 `ResumenValidacion`: los dos conteos que el motor ya produce

```python
total_evaluadas: int = Field(..., description="Reglas realmente evaluadas")
reglas_no_aplicables: int = Field(..., description="Reglas omitidas por no aplicar")
```

Mapeados desde `reporte["resumen"]` en `validator/api.py:93-97`.

### 3.3 `metadatos.reglas_evaluadas`: decisión de semántica

Hoy vale `reporte["resumen"]["total"]` (`validator/api.py:105`), o sea 48,
pero el campo se llama `reglas_evaluadas`. **El nombre miente desde antes del
paso 5**; ahora se nota porque existe el valor real.

- **(A) Recomendada** — `reglas_evaluadas` = `total_evaluadas` (46) y agregar
  `reglas_totales` = 48. Por fin el nombre significa lo que dice.
  **Es breaking**: el valor de un campo publicado cambia de 48 a 46.
- **(B) Conservadora** — dejarlo igual y agregar solo `total_evaluadas` al
  resumen. No breaking, pero mantiene el campo mintiendo.

### 3.4 Opcional, recomendado: `tipo_documento` en metadatos

```python
tipo_documento_declarado: str | None = Field(None, description="Lo que declara el Anexo 10")
tipo_documento_inferido: str | None = Field(None, description="Lo que se dedujo de las firmas")
tipo_documento_estado: str = Field(..., description="vigente | sin_determinar | contradictorio")
```

El detalle ya viaja en el `encontrado` de `deteccion_tipo_documento`; esto solo
evita que el frontend tenga que parsear texto libre.

---

## 4. La decisión que te toca a ti

**¿El frontend recibe todas las reglas con su flag `aplicable`, o solo las aplicables?**

Hoy divergen: la API manda crudas, y `build_report()` (`validator/engine.py`)
**filtra** las no aplicables.

- **(A) Mandar todas + `aplicable`** — el frontend puede mostrar "omitida" y
  explicar por qué. No se pierde información. Requiere tocar el frontend.
- **(B) Mandar solo aplicables**, igual que `build_report()` — los números
  cuadran con la CLI y el exportador, no hace falta el campo nuevo, pero el
  estudiante nunca ve que hubo reglas omitidas.

Recomiendo **(A)**: el paso 6 existe justamente para que el estudiante entienda
*por qué* algo no se revisó. Ocultarlas lo deja con la misma pregunta que
tenía antes.

---

## 5. Después de tocar los modelos

```bash
python3 scripts/generate_openapi.py     # regenera docs/openapi_spec.json
git add docs/openapi_spec.json
```

El CI corre `python3 scripts/generate_openapi.py --check`
(`.github/workflows/ci.yml:24`) y **falla si el spec commiteado no coincide**
con los modelos. Si cambias `api_models.py` sin regenerarlo, el CI se pone rojo
por drift, no por tu cambio.

No olvides el ejemplo de la respuesta embebido en `api_models.py:116`
(hoy dice `total: 47`, que ya no corresponde a ningún escenario real).

Agrega también los tests de contrato correspondientes en
`tests/test_api_contract.py`, que también es área tuya.

## 6. Impacto en Integrante 2 (frontend)

- `resumen` gana campos: si el frontend valida la forma del JSON de forma
  estricta, hay que avisarle antes de mergear.
- Con `aplicable`, el frontend puede distinguir "aprobada" de "omitida", que
  antes no era posible.
- Mientras tanto, **no hay cambios obligatorios** para que el frontend siga
  funcionando.

## 7. Verificación

```bash
nix develop --command pytest tests/test_api_contract.py -v
python3 scripts/generate_openapi.py --check
nix flake check
```

**Hecho cuando**: el contrato refleja lo nuevo, el CI confirma que no hay
drift, y el frontend sabe que el resumen es dinámico.
