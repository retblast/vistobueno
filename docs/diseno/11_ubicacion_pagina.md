# Diseño — Ubicación por página física (ítem 1 de la Fase 2)

> Documento: `11_ubicacion_pagina.md`
> Estado: ✅ **IMPLEMENTADA** (2026-09-21, Semana 5, rama `semana5-motor-calidad-paginacion`)
> y **corregida en M3/VA-04** (2026-11-13, Semana 12): orden y valor de los
> saltos, `pageBreakBefore` en el propio párrafo y grado de certeza de la página.
> Autor: IvanSanchezSil (Integrante 3 — Motor de reglas / DSL)
> Alcance: cerrar el [ítem 1 del backlog](../PLAN_BACKLOG_FUTURO.md) (paginación real):
> mapa párrafo→página, sección DSL `paginacion` y **enriquecimiento de `location`**
> con el número de página físico cuando una regla falla.
> Relacionado: [`validator/extractor.py`](../../validator/extractor.py) ·
> [`validator/analizadores.py`](../../validator/analizadores.py) ·
> [`validator/compilador.py`](../../validator/compilador.py) ·
> [`tests/test_f2_paginacion.py`](../../tests/test_f2_paginacion.py)

## 1. Contexto

El reporte del motor situaba cada fallo solo con la referencia al reglamento
(campo `location`, p. ej. `"Sección "Formato general" (párr. 141)"`). El ítem 1
del backlog pedía decirle al estudiante **en qué página del documento** está el
problema: `"página 14 (párr. 124-125)"`, algo mucho más útil para un DOCX de 150
páginas.

La primera parte del ítem (mapa párrafo→página) se implementó en la Semana 5
con dos marcadores que Word persiste en el XML del DOCX:

- `w:lastRenderedPageBreak` — insertado al guardar un documento ya renderizado.
- `w:br w:type="page"` — salto de página explícito.

La revisión de correctitud de 2026-11-12 (VA-04) encontró que esa primera
versión era optimista: contaba el salto en el párrafo anterior, ignoraba
`w:val="0"` y afirmaba páginas que el XML no respaldaba. M3 corrige el orden y
el valor de los saltos y añade un **grado de certeza** a cada página.

Este documento cubre la segunda parte: **conectar ese mapa a los analizadores**
para que el `location` de una regla fallida diga "página N" (o "(estimada)").

## 2. Decisión de diseño: heurística del DOCX, sin render

Inicialmente se propuso renderizar el DOCX a PDF (LibreOffice headless +
PyMuPDF) para obtener páginas reales. **Decisión (2026-09-21): NO se agrega
LibreOffice.** Razones:

- Es una dependencia pesada en Nix (cientos de MB) solo para un enriquecimiento.
- Los DOCX que valida el motor ya están renderizados por Word (el estudiante los
  escribió y guardó en su PC), así que `w:lastRenderedPageBreak` suele estar
  presente.
- Si **no** hay marcadores en el documento, el mapa no puede calcular páginas; en
  ese caso el motor **omite el sufijo** (no inunda el reporte con
  "página no disponible").

El resultado es determinista y sin dependencias nuevas. PyMuPDF ya está en el
flake pero queda disponible para otros usos (p. ej. el ítem 13, benchmark).

## 3. Implementación

### 3.1 Extractor — `_paginacion_para()` y `ExtractedDocx.pagina_de()`

```python
PAGINA_COMPROBADA = "comprobada"
PAGINA_ESTIMADA = "estimada"
PAGINA_DESCONOCIDA = "desconocida"


@dataclass(frozen=True)
class PaginaFisica:
    numero: int
    certeza: str


def _paginacion_para(document) -> dict:
    paginacion = {}
    pagina = 1
    inicio_comprobado = True
    tiene_render = next(document.iter(W + "lastRenderedPageBreak"), None) is not None

    for p in document.xpath("//w:body//w:p", namespaces=NS):
        ppr = p.find(W + "pPr")
        pbb = ppr.find(W + "pageBreakBefore") if ppr is not None else None
        if pbb is not None and not _apagado(pbb):
            pagina += 1                    # afecta al PROPIO párrafo
            inicio_comprobado = True

        certeza = (
            PAGINA_COMPROBADA if inicio_comprobado
            else PAGINA_ESTIMADA if tiene_render
            else PAGINA_DESCONOCIDA
        )
        paginacion[p] = PaginaFisica(pagina, certeza)

        saltos = saltos_estructurales = 0
        for el in p.iter():
            if el.tag == W + "lastRenderedPageBreak":
                saltos += 1
            elif el.tag == W + "br" and el.get(W + "type") == "page":
                saltos += 1
                saltos_estructurales += 1
        sect = ppr.find(W + "sectPr") if ppr is not None else None
        if sect is not None and _salta_pagina_por_seccion(sect):
            saltos += 1
            saltos_estructurales += 1

        if saltos:
            pagina += saltos
            inicio_comprobado = saltos_estructurales == saltos
        elif not _parrafo_tiene_contenido(p):
            pass
        else:
            inicio_comprobado = False

    return paginacion
```

Puntos clave:

- La clave del mapa es el **elemento lxml**, no `id()` del proxy: los proxies
  lxml se liberan y recrean (su `id()` cambia) si no hay una referencia fuerte,
  lo que rompía las consultas posteriores (bug corregido en la Semana 5).
- Los saltos se procesan **en orden de documento**. `w:pageBreakBefore` afecta
  al **propio** párrafo (antes se cobraba en el siguiente); `w:val="0"`,
  `false` u `off` lo desactivan.
- `w:br w:type="page"` y `w:sectPr` no continuo son **estructurales**;
  `w:lastRenderedPageBreak` es la **caché de render** de Word.
- Varios saltos dentro del mismo párrafo cuentan todos (`[1,3]` con dos `w:br`).
- Un párrafo que cruza página conserva la página donde empieza; el contenido
  siguiente pasa a la nueva.
- `pagina_de(node)` sube por ancestros hasta el `w:p` y devuelve el número;
  `certeza_pagina_de(node)` devuelve el grado de certeza y
  `pagina_confirmada_de(node)` responde si está comprobada. Devuelven `None`
  si el nodo no es un párrafo del cuerpo (o no está en el mapa).

#### Grados de certeza

| Certeza | Cuándo | Qué afirma |
|---|---|---|
| `comprobada` | El párrafo inicia el documento o empieza tras un salto estructural | La página relativa está respaldada por el XML |
| `estimada` | No hay salto estructural, pero el DOCX trae caché de render | La página viene de `w:lastRenderedPageBreak`, que Word pudo dejar desactualizado |
| `desconocida` | No hay marcador ni caché de render | El texto pudo fluir a otra página sin que el XML lo registre |

El número absoluto de una página `comprobada` supone que los saltos anteriores
también están marcados; si el autor borró un salto intermedio, el número puede
desviarse aunque el párrafo sí empiece en página nueva. Es un límite aceptado:
el motor no renderiza el documento.

### 3.2 Analizadores — `Analizador.ultimo_nodo`

La clase base `Analizador` gana un atributo `ultimo_nodo`, que el helper
compartido `_nodos()` rellena con el primer nodo de cada consulta XPath:

```python
def _nodos(self, extracted, parte, contexto):
    nodos = extracted.xpath(parte, self.config.get("xpath", ""), contexto)
    self.ultimo_nodo = nodos[0] if nodos else None
    return nodos
```

Casi todos los analizadores pasan por `_nodos`, por lo que quedan cubiertos
`atributo_xml`, `presencia_xml`, `patron_texto`, `paginacion`, etc. Un nodo no
párrafo (p. ej. `w:ind`) se resuelve subiendo por ancestros a su `w:p`.

### 3.3 Compilador — `ReglaCompilada.ejecutar()`

Al producirse un fallo, se anexa la página del primer analizador que falló,
declarando su certeza:

```python
if fallos and pagina is not None and ubicacion and certeza_pagina != PAGINA_DESCONOCIDA:
    sufijo = f"página {pagina}"
    if certeza_pagina == PAGINA_ESTIMADA:
        sufijo += " (estimada)"
    ubicacion = f"{ubicacion}; {sufijo}"
```

Reglas de la convención:

- **Solo cuando falla**: una regla cumplida conserva su `location` original.
- **Solo si `ubicacion` no es vacía**: no se inventa una ubicación.
- **No se inventa precisión**: si la página es `desconocida`, el sufijo se
  omite; si es `estimada`, se declara `(estimada)`.
- **Formato**: el sufijo se agrega al string `location`/`ubicacion`. El DTO de la
  API mapea `location`→`ubicacion` de forma transparente, **sin cambiar el
  contrato** (`CONTRATO_API.md` no se toca).

## 4. Evidencia

### 4.1 Tests (`tests/test_f2_paginacion.py`)

- `test_paginacion_es_monotona_y_pagina_inicial`: el mapa es monótono y page 1 =
  carátula (el manual dice que no se enumera pero **sí** se cuenta).
- `test_mapa_de_saltos_renderizados_y_explicitos`: `[1,1,2,2,3]` con ambos
  marcadores.
- `test_pagina_de_no_para_es_none` → `None` para `None` y para el documento.
- Aceptación M3: `test_break_before_afecta_al_propio_parrafo` (`[1,2]`),
  `test_dos_saltos_en_el_mismo_parrafo` (`[1,3]`) y
  `test_break_before_desactivado_no_crea_salto` / `..._off_tampoco_crea_salto`
  (`[1,1]`).
- `test_salto_de_seccion_next_page_avanza_la_pagina` /
  `test_salto_de_seccion_continuo_no_avanza_la_pagina`: `w:sectPr` según
  `w:type`.
- `test_parrafo_que_cruza_pagina_conserva_la_pagina_de_inicio`: un párrafo con
  salto interno mantiene la página donde empieza.
- `test_sin_marcadores_la_pagina_es_desconocida`: la certeza distingue
  comprobada / desconocida en vez de inventar "página 1" para todos.
- `test_salto_explicito_es_comprobado_y_render_es_estimado`: la caché de render
  solo produce páginas estimadas.
- `test_paginas_distintas_pasa` / `test_paginas_repetidas_falla` /
  `test_no_encontrado_es_no_aplica`: end-to-end del `AnalizadorPaginacion`.
- `test_sin_marcadores_no_se_inventa_paginas_repetidas`: sin marcadores la
  regla pasa como n/a (`paginas_no_verificables`).
- `test_paginas_estimadas_se_declaran_en_el_detalle`: el detalle marca
  `(estimadas)`.
- `test_indice_paginas_separadas_*`: regla real contra `reglas_unt.yaml`
  (base pasa / mutación falla / índice renombrado falla).
- `test_regla_fallida_enriquece_location_con_pagina`: `sangria_parrafo` mutada
  (firstLine=0) termina en `"página 4 (estimada)"` (3 saltos previos de los
  índices).
- `test_pagina_desconocida_no_se_anexa_a_la_location`: sin marcadores el
  sufijo se omite.
- `test_regla_cumplida_no_altera_location`: la ubicación queda intacta al pasar.

### 4.2 Marco de pruebas

El `docx_factory` configura `indices_paginas_separadas: True` en la base, por lo
que el DOCX sintético incluye `w:lastRenderedPageBreak` reales y el enriquecimiento
se puede probar de manera determinista. La mutación `sangria_parrafo` sigue
emitiendo `w:ind` con `firstLine=0`, de modo que el fallo cae sobre un párrafo
real (el primero del cuerpo, página 4).

## 5. Alcance y no-alcance

Incluido:

- Enriquecimiento de `location` con página física vía heurística, sin render.
- Orden y valor de los saltos: `pageBreakBefore` en el propio párrafo,
  `w:val="0"` desactivado, varios saltos por párrafo y `w:sectPr` no continuo.
- Grado de certeza (`comprobada` / `estimada` / `desconocida`) en el mapa, en
  el detalle del analizador y en el sufijo de `location`.
- `ultimo_nodo` en la base `Analizador` (componible, reutilizable).
- Regla `caratula_no_se_enumera` (carátula sin enumerar) **ya estaba
  mecanizada** (presencia de `w:titlePg` en `reglas_unt.yaml:366-378`); no se
  duplicó.

No incluido (límites declarados):

- **No se renderiza el DOCX**: no se detectan cortes de página naturales que
  Word no haya persistido como `w:lastRenderedPageBreak`. Sin caché de render,
  los párrafos que no inician página quedan como `desconocida` y las reglas de
  paginación pasan como n/a.
- **`evenPage`/`oddPage`** se cuentan como un salto, pero no se modela la
  página en blanco que Word puede insertar para cumplir la paridad; el número
  absoluto puede quedar desfasado.
- **Saltos no marcados**: si el autor borró un salto intermedio, los números
  absolutos posteriores pueden desviarse aunque el párrafo sí empiece en
  página nueva.
- **Encabezados/pies y notas** no están en el mapa (no reciben sufijo).
- La detección de los bloques de índice por palabras (REQ-29) no se toca en
  M3; sigue como pendiente de M12.
- Los ítems 2 (encabezados/pies), 3 (notas al pie) y 11-12 (TOC y numeración
  jerárquica) del backlog ya se cerraron en semanas posteriores; no forman
  parte de este cambio.
- El compañero de API/frontend debe exponer `formato` en `POST /validar`
  (ítem 16, bloque E).