"""Constantes XML/OPC del factory de DOCX sintéticos (soporte de F6).

Concentra los namespaces WordprocessingML/DrawingML y las plantillas XML
fijas del paquete OPC (_rels, [Content_Types]). Nada de esto depende de
otro módulo; es el estrato de "datos estáticos" de la construcción.

Las relaciones se reparten por parte, como exige OPC: `_rels/.rels` solo
declara el documento principal y cada parte declara sus propios destinos en
`<parte>/_rels/<parte>.rels`. Los `Id` son locales a la parte que los usa.
"""

WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ANS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PNS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WPN = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""

# Override que solo se agrega cuando el ZIP incluye `word/footnotes.xml`.
FOOTNOTES_CONTENT_TYPE = (
    '  <Override PartName="/word/footnotes.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n'
)

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

# Relaciones de `word/document.xml`: cabecera, pie, imagen de portada y
# hipervínculo ORCID. Los destinos son relativos a `word/`.
DOCUMENT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/>
  <Relationship Id="rIdOrc" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://orcid.org/0000-0002-1825-0097" TargetMode="External"/>
</Relationships>"""

# Relación de notas al pie; se agrega a `DOCUMENT_RELS` solo si existe la parte.
FOOTNOTES_REL = (
    '  <Relationship Id="rIdFootnotes" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" '
    'Target="footnotes.xml"/>\n'
)

# Relaciones de `word/header1.xml`: el logo se referencia desde el encabezado.
HEADER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdImg" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/logo.png"/>
</Relationships>"""

# PNG válido de 1×1 (gris opaco). Basta para que el paquete sea íntegro: las
# reglas solo cuentan nodos `a:blip`, no inspeccionan los píxeles.
PNG_LOGO = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de"
    "0000000c49444154789c63606060000000040001f61738550000000049454e44ae426082"
)
