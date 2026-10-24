# Handover: exponer los valores detectados por el motor (ficha de depósito)

**Fecha**: 2026-10-19 (actualiza la versión del 2026-10-14)
**De**: Integrante 1 (Backend/API)
**Para**: Integrante 3 (Motor de reglas)
**Estado**: pedido con especificación — el diseño del mecanismo es tuyo
**Contexto de producto**: `docs/PLAN_FICHA_DEPOSITO.md` (leer primero)

---

## 1. El problema en una frase

Los analizadores de carátula y cuerpo **ya localizan** título, autores,
asesor, resumen y palabras clave — pero hoy solo publican pass/fail y un
`found` resumido; el flujo de depósito en DSpace necesita **el texto
completo que encontraron**, con su página.

## 2. Qué se pide, campo por campo

> **Actualización 2026-10-19**: la captura real del formulario de la
> instancia congeló el mapa de campos (PLAN_FICHA §4). El servidor de
> DSpace pre-llena 16 campos según la colección (grado, disciplina, OCDE,
> tipo, idioma, derechos, etc.), así que el motor solo necesita exponer
> los datos que el operador realmente completa.

| Dato | Destino | Regla/analizador que hoy lo localiza | Estado |
|------|---------|--------------------------------------|--------|
| Título | `dc.title` | `caratula_titulo_trabajo_*` | Sin cambio: texto completo, sin truncar |
| Autores | `dc.contributor.author` | `caratula_autores_*` | Sin cambio: lista de nombres |
| Asesor | `dc.contributor.advisor` | regla de asesor en carátula | Sin cambio |
| Resumen | `dc.description.abstract` | `resumen_longitud` | Sin cambio: texto completo |
| Palabras clave | `dc.subject` | `palabras_clave_minimo` | Sin cambio: lista de entradas |
| Año de emisión | `dc.date.issued` | — (sin regla hoy) | Detección nueva: año en carátula |
| Escuela | columna ESCUELAS del registro (no es campo del formulario) | línea "ESCUELA ACADÉMICO PROFESIONAL DE…" de la carátula | La regla de carátula que la localiza (o detección trivial si no hay): texto igual que título |
| Jurado | `renati.juror` (opcional) | firmas / anexo | **Pedido de viabilidad**: ¿los nombres del jurado salen de forma confiable de la sección de firmas, en plantillas y tesis reales? Si sí, campo opcional; si no, `detectado=false` y el operador lo teclea |

**Descartados del pedido original** (el servidor ya los pre-llena por
colección; la ficha no los necesita):

- Grado/título al que opta → `thesis.degree.name` pre-lleno.
- Línea de investigación → `dc.subject.ocde` pre-lleno. El mapeo
  línea→OCDE queda cancelado para el depósito.

Los demás campos del formulario (DNI del autor y del asesor, ORCID, DOI,
ISBN) no salen del DOCX: los teclea el operador en la pantalla. El motor
no los busca y la ficha no los publica.

Requisitos comunes:

- **Texto completo, no resumen**: `found` trunca (`vals[:3]`, conteos);
  la ficha necesita el valor íntegro.
- **Página de origen**: el mapa párrafo→página ya existe
  (`ultimo_nodo` + enriquecimiento de `location`, F2 ítem 1). Reusarlo.
- **Solo lectura**: esto no cambia el semáforo ni ninguna regla. Es
  captura de datos, no validación nueva.

## 3. Mecanismos posibles (a tu criterio)

Presento dos opciones; la decisión de diseño es del área motor.

**(a) Campo `valores` en `RuleResult`**: el analizador que ya localiza el
elemento llena un campo opcional (p. ej. `valores: dict | None`) con los
textos; `to_dict()` lo expone y la API lo mapea a la ficha.
- Pros: cambio local, regla por regla.
- Contras: `RuleResult` crece para un caso de uso específico; cada regla
  decide su formato a mano.

**(b) Sección DSL `extraccion`**: la regla declara en el YAML qué capturar
(p. ej. `extraccion: {campo: dc.title, del_nodo: texto}`); el analizador,
al encontrar el nodo, además de validar lo publica en un dict del
contexto (p. ej. `contexto["ficha"]`).
- Pros: declarativo, consistente con la filosofía del DSL; el formato es
  uniforme y la API no parsea texto libre por regla.
- Contras: toca compilador/analizadores y el linter (`SECCIONES_ANALIZADOR`,
  `_FABRICAS`, `_SECCIONES`).

Mi recomendación no vinculante: **(b)**, por la misma razón que el DSL
existe — pero si prefieres (a) por velocidad, funciona igual para la API:
lo único que contrato es "el valor viaja en algún campo estructurado de
la salida del motor, con la página".

## 4. Forma que espera la API (el contrato entre nosotros)

Cualquiera de las dos opciones debe permitir que `build_report()` (o el
`RuleResult` correspondiente) entregue, por dato:

```
{
  "campo": "dc.title",          # clave acordada (tabla de la §2)
  "valor": "Taller de ...",     # texto completo o lista de textos
  "pagina": 1,                  # página de origen (si hay mapa)
  "detectado": true             # false si la regla no encontró el elemento
}
```

Claves acordadas: `dc.title`, `dc.contributor.author`,
`dc.contributor.advisor`, `dc.description.abstract`, `dc.subject`,
`dc.date.issued`, `escuela`, `renati.juror` (opcional). Con eso, la API
arma `ficha_deposito.extraidos[]` (PLAN_FICHA §5) sin parsear `found` ni
inventar heurísticas por regla. Si un dato no aplica, `detectado: false`.

## 5. Verificación que te pido

- Tests de que cada campo de la §2 expone su valor con el factory
  determinista (carátula con contenido conocido).
- Paridad en las 5 plantillas: la ficha extrae los placeholders (es
  esperable; el operador los corrige en la pantalla).
- La suite completa en verde y las mutaciones de `tests/_mutations.py`
  sincronizadas si agregas sección DSL nueva (regla de AGENTS.md).

## 6. Lo que NO se pide

- No reglas nuevas de validación ni cambios de semáforo.
- No tocar `validator/dspace.py` ni la API: el mapeo a la ficha y el
  contrato v1.7.0 son míos.
- El mapeo línea→OCDE queda **cancelado**: `dc.subject.ocde` viene
  pre-lleno por colección en la instancia.

## 7. Después de tu parte

1. Yo publico `ficha_deposito` en el contrato (v1.7.0) y regenero
   OpenAPI.
2. Integrante 2 arma la pantalla de la ficha (extraídos + manuales,
   botón "Preparar depósito", panel de espera) sobre el flujo existente.
3. El depósito contra la instancia real no requiere gestión ante la
   sede: se hace con el userscript sobre la sesión del operador
   (PLAN_FICHA §2).

---

## 8. Nota de seguimiento (2026-10-23, tras la entrega del diseño 17)

La entrega está integrada y funcionando de punta a punta (la API activa
`reglas_ficha.yaml` en `POST /validar`; la ficha viaja con valores
reales). Un solo pulido quedó en el tintero, sin urgencia:

- **`dc.title` llega con el prefijo de la etiqueta**: la captura trae el
  párrafo completo ("Título del trabajo de investigación: Estrategias
  lúdicas…"). Hoy el operador lo recorta en la pantalla de revisión
  (Int2) y el userscript lo escribe tal cual. Si la captura puede
  dejar solo el título, mejor — es limpiar el dato en la fuente y no en
  cada uso. Tu llamada el mecanismo; las reglas de validación no se
  tocan (la captura es solo lectura, como la firmamos en el §6).

Referencia viva: el ensayo general (`nix run .#test-ficha-deposito`)
usa tu captura en el flujo completo — cualquier cambio tuyo queda
verificado ahí de gratis.

### 8.1 Hallazgos verificados contra la plantilla oficial (2026-10-23, revisión del PR #55)

Verificados con `validate_docx` + `load_ficha_rules()` sobre la
plantilla real de Educación Inicial (reproducción: ver `recursos/`).
Ambos son de `reglas_ficha.yaml` — área tuya, mecanismo a tu criterio:
solo los documento para tu cola.

- **`dc.contributor.advisor` viaja `detectado=true` con `valor=""`**:
  contradictorio para el contrato (la ficha dice "detectado" cuando no
  hay nada). Sospecha: el `quitar_prefijo` de la regla deja la cadena
  vacía cuando la línea de la plantilla no tiene el asesor real, y la
  captura la publica igual. Normalizar a `detectado=false, valor=null`
  cuando el resultado queda vacío.
- **`dc.date.issued` captura la línea de lugar** (`"Trujillo - Perú"`),
  no un año: en la carátula de la plantilla la línea "TRUJILLO –
  PERÚ … 2026" se captura parcialmente. Hoy el userscript lo resuelve
  por su cuenta (extrae 4 dígitos; sin año → queda "a mano", fallo
  visible), pero la captura debería traer el año directo.

Nota menor (ítem 4 de la misma revisión): documentar en el diseño 17
que el XPath de autores espera **párrafos hermanos** (funciona con
párrafos separados y con "Autor1, Autor2" en una línea vía separador,
pero vale dejarlo escrito).
