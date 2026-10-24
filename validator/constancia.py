"""Generación de la constancia de depósito (Modelo B) y la fila de registro.

Produce los dos artefactos del registro de la biblioteca a partir de la
ficha de depósito completada y del reporte del buzón (handle + timestamp):

- **Constancia** (`TESIS DIGITAL MODELO B`): un `.docx` por autor, con
  los MERGEFIELD de la plantilla reemplazados por texto plano con los
  valores. La plantilla oficial vive en `recursos/` (no versionada); su
  ruta es configurable por `VISTOBUENO_PLANTILLA_CONSTANCIA`.
- **Fila de registro**: una fila TSV por autor en el orden exacto de
  columnas del XLSX oficial (N°, TESIS/TSP, BACHILLER/LICENCIADO,
  N° MATRIC., DD, MM, AA, HORA, DIRECCION URL, FIRMA, FECHA DEL DOC.,
  ESCUELAS, AÑO). El registro oficial JAMÁS se escribe desde la app:
  el operador pega la fila (decisión del plan, PLAN_FICHA §7).

Convenciones tomadas de la evidencia (registro real de la biblioteca):

- Una fila y una constancia POR AUTOR: las tesis con dos autores ocupan
  dos filas con el mismo handle (evidencia: filas consecutivas del
  XLSX). Matrícula y DNI del autor viajan alineados por posición.
- DD y MM con barra final ("20/", "01/") y AA a cuatro dígitos, como
  las celdas del registro.
- HORA en formato 24 h "HH:MM:SS" (el registro guarda un serial de
  Excel; el texto pegado lo parsea como hora del día).
- FECHA_DEL_DOC en español largo ("Trujillo, 20 de enero de 2026"),
  derivada de la fecha del depósito.

Errores:

- `ErrorDatosConstancia`: falta un dato de la ficha (422 en la API).
- `ErrorConfiguracionConstancia`: plantilla ausente o firma sin
  configurar (500 en la API).
"""

import copy
import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path

from docx import Document as abrir_documento
from docx.document import Document as DocumentoDocx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Meses en español (sin depender del locale del proceso).
MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)

# Columnas del registro oficial en orden (la fila TSV las respeta).
COLUMNAS_REGISTRO = (
    "N°",
    "TESIS/TSP",
    "BACHILLER/LICENCIADO",
    "N° MATRIC.",
    "DD",
    "MM",
    "AA",
    "HORA",
    "DIRECCION URL",
    "FIRMA",
    "FECHA DEL DOC.",
    "ESCUELAS",
    "AÑO",
)


class ErrorDatosConstancia(Exception):
    """Falta un dato necesario de la ficha o el índice de autor no existe."""


class ErrorConfiguracionConstancia(Exception):
    """La plantilla no existe o la firma no está configurada."""


@dataclass
class DatosConstancia:
    """Datos de UNA constancia (un autor) y su fila de registro.

    Atributos:
        titulo: Título de la tesis.
        autor: Nombre del estudiante de esta constancia.
        matricula: Código interno UNT de este estudiante.
        momento: Momento del depósito (clic en Depositar).
        handle: URI del ítem en el repositorio.
        firma: Nombre del responsable (columna FIRMA del registro).
        escuela: Escuela/programa (columna ESCUELAS); opcional.
    """

    titulo: str
    autor: str
    matricula: str
    momento: datetime
    handle: str
    firma: str
    escuela: str | None = None

    def mapa_mergefields(self) -> dict[str, str]:
        """Valores por nombre de MERGEFIELD del Modelo B.

        DD/MM llevan barra final y AA va a cuatro dígitos, igual que las
        celdas del registro de donde proviene la convención.
        """
        m = self.momento
        return {
            "TESIS__TSP": self.titulo,
            "BACHILLER__LICENCIADO": self.autor,
            "N_MATRIC": self.matricula,
            "DD": f"{m.day}/",
            "MM": f"{m.month:02d}/",
            "AA": str(m.year),
            "HORA": m.strftime("%H:%M:%S"),
            "AÑO": str(m.year),
            "DIRECCION_URL": self.handle,
            "FECHA_DEL_DOC": self.fecha_del_doc(),
            # La plantilla real también tiene MERGEFIELD ESCUELAS
            # (verificado contra el Modelo B oficial): sin escuela va vacío.
            "ESCUELAS": self.escuela or "",
        }

    def fecha_del_doc(self) -> str:
        """Fecha del documento en español largo ("Trujillo, 20 de enero de 2026")."""
        m = self.momento
        return f"Trujillo, {m.day} de {MESES[m.month - 1]} de {m.year}"

    def fila_registro(self) -> str:
        """Fila TSV con las columnas del registro oficial en orden.

        La columna N° va vacía: la numeración pertenece al registro de la
        biblioteca. Los valores se limpian de tabuladores y saltos para
        no romper la estructura al pegarlos.
        """

        def limpiar(valor: str) -> str:
            return " ".join(valor.replace("\t", " ").split())

        return "\t".join(
            (
                "",
                limpiar(self.titulo),
                limpiar(self.autor),
                limpiar(self.matricula),
                f"{self.momento.day}/",
                f"{self.momento.month:02d}/",
                str(self.momento.year),
                self.momento.strftime("%H:%M:%S"),
                limpiar(self.handle),
                limpiar(self.firma),
                self.fecha_del_doc(),
                limpiar(self.escuela or ""),
                str(self.momento.year),
            )
        )


# ---------------------------------------------------------------------------
# Extracción de datos desde la ficha
# ---------------------------------------------------------------------------


def _valor_extraido(ficha: dict, campo: str) -> str | list[str] | None:
    """Devuelve el valor de un campo extraído de la ficha."""
    for item in ficha.get("extraidos", []):
        if item.get("campo") == campo:
            return item.get("valor")
    return None


def _valor_manual(ficha: dict, campo: str) -> str | list[str] | None:
    """Devuelve el valor de un campo manual de la ficha."""
    for item in ficha.get("manuales", []):
        if item.get("campo") == campo:
            return item.get("valor")
    return None


def _como_lista(valor: str | list[str] | None) -> list[str]:
    """Normaliza un valor de ficha a lista de textos."""
    if valor is None:
        return []
    if isinstance(valor, list):
        return [v for v in valor if isinstance(v, str) and v.strip()]
    return [valor] if valor.strip() else []


def constancias_por_autor(
    ficha: dict,
    handle: str,
    momento: datetime,
    firma: str,
) -> list[DatosConstancia]:
    """Una DatosConstancia por autor, con matrículas alineadas por posición.

    Raises:
        ErrorDatosConstancia: si falta el título, los autores, la
            matrícula de algún autor o el handle.
    """
    titulo = _valor_extraido(ficha, "dc.title")
    if not isinstance(titulo, str) or not titulo.strip():
        raise ErrorDatosConstancia(
            "La ficha no trae el título (dc.title): corríjalo en la pantalla antes de generar la constancia."
        )

    autores = _como_lista(_valor_extraido(ficha, "dc.contributor.author"))
    if not autores:
        raise ErrorDatosConstancia(
            "La ficha no trae autores (dc.contributor.author): corríjalos en la pantalla antes de generar la constancia."
        )

    matriculas = _como_lista(_valor_manual(ficha, "matricula"))
    if len(matriculas) < len(autores):
        faltan = len(autores) - len(matriculas)
        raise ErrorDatosConstancia(
            f"Faltan {faltan} matrícula(s): la ficha trae {len(autores)} autor(es) "
            f"y {len(matriculas)} matrícula(s). La constancia necesita una por estudiante."
        )

    escuela = _valor_extraido(ficha, "escuela")
    escuela_texto = escuela if isinstance(escuela, str) and escuela.strip() else None

    if not handle or not handle.strip():
        raise ErrorDatosConstancia("Falta el handle del ítem depositado.")

    return [
        DatosConstancia(
            titulo=titulo.strip(),
            autor=autor,
            matricula=matriculas[i],
            momento=momento,
            handle=handle.strip(),
            firma=firma,
            escuela=escuela_texto,
        )
        for i, autor in enumerate(autores)
    ]


# ---------------------------------------------------------------------------
# Llenado de la plantilla: reemplazo de MERGEFIELD por texto plano
# ---------------------------------------------------------------------------

# MERGEFIELD con o sin comillas; AÑO lleva Ñ. Los switches (\* MERGEFORMAT)
# van después del nombre y no afectan el match.
_RE_MERGEFIELD = re.compile(r'MERGEFIELD\s+"?([A-Za-zÑñ0-9_]+)"?')


def _runs_del_campo(parrafo, run_actual) -> list:
    """Runs del párrafo en orden de documento (w:r, incluidos anidados)."""
    return list(parrafo.iter(qn("w:r")))


def _reemplazar_mergefields(doc: DocumentoDocx, valores: dict[str, str]) -> int:
    """Reemplaza cada MERGEFIELD del documento por texto plano con el valor.

    Recorre los campos complejos de Word (begin → instrText → separate →
    resultado cacheado → end) y también `fldSimple`. Del constructo
    completo queda un solo run de texto: los runs del mecanismo (begin,
    instrText, separate, end) se eliminan y el primer run de resultado
    lleva el valor. Campos desconocidos quedan intactos.

    Returns:
        Cantidad de campos reemplazados.
    """
    reemplazados = 0

    for parrafo in doc.element.body.iter(qn("w:p")):
        estado = "fuera"  # fuera | campo | resultado
        runs_borrar: list = []
        nombre: str | None = None
        runs_resultado: list = []

        for run in list(parrafo.iter(qn("w:r"))):
            fld = run.find(qn("w:fldChar"))
            if fld is not None:
                tipo = fld.get(qn("w:fldCharType"))
                if tipo == "begin":
                    estado, nombre = "campo", None
                    runs_borrar, runs_resultado = [run], []
                elif tipo == "separate" and estado == "campo":
                    estado = "resultado"
                    runs_borrar.append(run)
                elif tipo == "end" and estado in ("campo", "resultado"):
                    runs_borrar.append(run)
                    if nombre in valores:
                        _aplicar_valor(runs_resultado, runs_borrar, valores[nombre])
                        reemplazados += 1
                    else:
                        # Campo desconocido: no se toca (sin borrar nada).
                        runs_borrar = []
                    estado, nombre, runs_resultado = "fuera", None, []
                continue

            instr = run.find(qn("w:instrText"))
            if instr is not None and estado == "campo":
                match = _RE_MERGEFIELD.search(instr.text or "")
                if match:
                    nombre = match.group(1)
                runs_borrar.append(run)
                continue

            if estado == "resultado":
                runs_resultado.append(run)

    # Campos simples: <w:fldSimple w:instr=" MERGEFIELD X ">…</w:fldSimple>
    for fld_simple in list(doc.element.body.iter(qn("w:fldSimple"))):
        match = _RE_MERGEFIELD.search(fld_simple.get(qn("w:instr")) or "")
        if match and match.group(1) in valores:
            nuevo = OxmlElement("w:r")
            texto = OxmlElement("w:t")
            texto.text = valores[match.group(1)]
            nuevo.append(texto)
            fld_simple.addprevious(nuevo)
            fld_simple.getparent().remove(fld_simple)
            reemplazados += 1

    return reemplazados


def _aplicar_valor(runs_resultado: list, runs_borrar: list, valor: str) -> None:
    """Deja el valor en el primer run de resultado y elimina el mecanismo.

    Si el campo no tenía resultado cacheado (plantilla nunca previsualizada),
    el valor toma el formato del run de instrText para no perder el estilo.
    """
    if runs_resultado:
        primero = runs_resultado[0]
        for t in primero.findall(qn("w:t")):
            primero.remove(t)
        texto = OxmlElement("w:t")
        texto.text = valor
        primero.append(texto)
        for extra in runs_resultado[1:]:
            if extra.getparent() is not None:
                extra.getparent().remove(extra)
    else:
        # Sin resultado cacheado: crear el run con el estilo del instrText.
        estilo = None
        for run in runs_borrar:
            pr = run.find(qn("w:rPr"))
            if pr is not None:
                estilo = pr
                break
        nuevo = OxmlElement("w:r")
        if estilo is not None:
            nuevo.append(_copia_xml(estilo))
        texto = OxmlElement("w:t")
        texto.text = valor
        nuevo.append(texto)
        runs_borrar[-1].addprevious(nuevo)

    for run in runs_borrar:
        if run.getparent() is not None:
            run.getparent().remove(run)


def _copia_xml(elemento):
    """Copia profunda de un elemento lxml (para heredar el estilo del run)."""
    return copy.deepcopy(elemento)


# ---------------------------------------------------------------------------
# Formatos de archivo del registro (hallazgo 11 de la revisión del PR #55)
# ---------------------------------------------------------------------------

# Prefijos que Excel/LibreOffice interpretan como fórmula al abrir un
# archivo (hallazgo 14: inyección desde el DOCX del estudiante). La
# mitigación estándar es anteponer una comilla simple, que el
# visualizador muestra como texto plano.
PREFIJOS_FORMULA = ("=", "+", "-", "@")


def _neutralizar_formula(campo: str) -> str:
    """Antepone ' a los campos que empiezan con un prefijo de fórmula.

    El título, el autor y la escuela salen del DOCX del estudiante
    (input no confiable). Sin esto, un título "=WEBSERVICE(...)" llega
    crudo al .csv y al .xlsx y Excel lo evalúa al abrir: la víctima es
    la PC de la biblioteca. La comilla simple es la mitigación estándar
    (OWASP CSV Injection cheat sheet): Excel la muestra como texto.
    """
    if isinstance(campo, str) and campo.startswith(PREFIJOS_FORMULA):
        return "'" + campo
    return campo


def filas_a_tsv(filas: list[str]) -> str:
    """Filas TSV listas como archivo: BOM UTF-8 + una fila por línea.

    Las filas ya vienen separadas por tabuladores (`fila_registro`); el
    BOM hace que Excel/LibreOffice detecten UTF-8 al abrir el .tsv.
    Los campos con prefijo de fórmula (=, +, -, @) se neutralizan.
    """
    neutras = ["\t".join(_neutralizar_formula(c) for c in f.split("\t")) for f in filas]
    return "\ufeff" + "\n".join(neutras) + "\n"


def filas_a_csv(filas: list[str]) -> str:
    """Filas en CSV con separador ';' y citas RFC 4180, BOM UTF-8.

    El separador ';' es el que Excel espera en configuración regional
    española; los campos que contienen ';' o comillas van citados. Los
    saltos y tabuladores ya se limpiaron al armar la fila TSV. Los
    campos con prefijo de fórmula (=, +, -, @) se neutralizan.
    """
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\n")
    for fila in filas:
        escritor.writerow([_neutralizar_formula(c) for c in fila.split("\t")])
    return "\ufeff" + buffer.getvalue()


def filas_a_xlsx(filas: list[str], columnas: tuple[str, ...] = COLUMNAS_REGISTRO) -> bytes:
    """Filas como libro .xlsx de una hoja, con la fila de encabezado.

    Encabezado = COLUMNAS_REGISTRO (las 13 columnas del registro
    oficial). openpyxl se importa aquí a propósito: solo este formato
    lo necesita. Los campos con prefijo de fórmula se neutralizan
    (openpyxl trata '=' como fórmula: data_type 'f').
    """
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Registro"
    hoja.append(list(columnas))
    for fila in filas:
        hoja.append([_neutralizar_formula(c) for c in fila.split("\t")])
    buffer = BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _nombre_seguro(autor: str) -> str:
    """Nombre de archivo seguro: ASCII simple, sin caracteres especiales.

    Se restringe a alfanuméricos, espacios y guiones: los acentos se
    pierden en el NOMBRE del archivo (no en el contenido), para que
    Content-Disposition no dé problemas en ningún navegador ni en el
    sistema de archivos de la biblioteca.
    """
    return re.sub(r"[^A-Za-z0-9 _-]", "", autor).strip()[:40] or "autor"


def constancia_en_zip(ruta_plantilla: Path, datos: DatosConstancia) -> bytes:
    """Constancia + fila del registro del autor en UN solo .zip.

    Variante del hallazgo 11 ("POST /constancia podría incluirlo"):
    una descarga por estudiante con todo su papeleo — la constancia
    del Modelo B y su fila de registro como .csv listo para abrir en
    Excel. El registro oficial sigue sin escribirse nunca desde la app.
    """
    docx = llenar_constancia(ruta_plantilla, datos)
    csv = filas_a_csv([datos.fila_registro()])
    nombre_seguro = _nombre_seguro(datos.autor)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as paquete:
        paquete.writestr(f"constancia - {nombre_seguro}.docx", docx)
        paquete.writestr("registro.csv", csv)
    return buffer.getvalue()


def llenar_constancia(ruta_plantilla: Path, datos: DatosConstancia) -> bytes:
    """Llena la plantilla del Modelo B y devuelve los bytes del .docx.

    La plantilla se abre en copia (nunca se muta el archivo original).

    Raises:
        ErrorConfiguracionConstancia: la plantilla no existe o no es un
            DOCX válido.
    """
    if not ruta_plantilla.exists():
        raise ErrorConfiguracionConstancia(
            f"La plantilla de la constancia no existe: {ruta_plantilla}. "
            "Coloque el Modelo B en recursos/ o configure VISTOBUENO_PLANTILLA_CONSTANCIA."
        )
    try:
        doc = abrir_documento(str(ruta_plantilla))
    except zipfile.BadZipFile as e:
        raise ErrorConfiguracionConstancia(
            f"La plantilla de la constancia no es un DOCX válido: {ruta_plantilla}."
        ) from e

    _reemplazar_mergefields(doc, datos.mapa_mergefields())

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
