#!/usr/bin/env bash
# Ensayo general de un solo comando — Semana 8 (hallazgo 10, revisión PR #55).
#
# Levanta TODO el flujo de ficha de depósito y lo verifica de punta a punta:
# validación (doc bueno del factory) → ficha → buzón → userscript contra el
# mock de DSpace → timestamp de Depositar → handle → constancia y registro
# en los formatos descargables (hallazgo 11).
#
# Uso (desde la raíz del repositorio):
#   nix run .#test-ficha-deposito      # recomendado: entorno completo
#   ./scripts/e2e_ficha_deposito.sh    # directo (requiere python con deps y node)
#
# Requisitos: puertos libres en :8000 y :8080; tools/dspace-fill con
# node_modules (el script lo instala si falta). VISTOBUENO_FIRMA se define
# sola si no viene en el entorno.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API="http://127.0.0.1:8000"
MOCK="http://127.0.0.1:8080"
DIR_TMP="$(mktemp -d /tmp/vistobueno-ensayo-XXXXXX)"

if [ -x "$ROOT/.venv/bin/python" ]; then
  BACKEND_PY="$ROOT/.venv/bin/python"
else
  BACKEND_PY="python3"
fi
export VISTOBUENO_FIRMA="${VISTOBUENO_FIRMA:-Lic. Ensayo General}"
export VISTOBUENO_PLANTILLA_CONSTANCIA="${VISTOBUENO_PLANTILLA_CONSTANCIA:-$ROOT/recursos/TESIS DIGITAL MODELO B-2026.docx}"

limpiar() {
  # ⚠️ Este pkill mata CUALQUIER uvicorn en el sistema, no solo el del
  # ensayo. Si tienes otro proceso corriendo, se detendrá también.
  pkill -f "uvicorn validator" 2>/dev/null || true
  pkill -f "[m]ock-dspace/server.js" 2>/dev/null || true
}
trap limpiar EXIT

# Pre-flight (hallazgo 16a): la plantilla del Modelo B vive en recursos/
# (no versionado). Sin ella, el paso 7 omite la constancia y continúa
# con el resto de verificaciones (hallazgo 16a, corregido en 5ce1f24).
if [ ! -f "$VISTOBUENO_PLANTILLA_CONSTANCIA" ]; then
  echo "⚠️  Falta la plantilla del Modelo B: $VISTOBUENO_PLANTILLA_CONSTANCIA"
  echo "   Descargue 'TESIS DIGITAL MODELO B-2026.docx' y colóquelo en recursos/"
  echo "   (o apunte VISTOBUENO_PLANTILLA_CONSTANCIA a su ruta)."
  echo "   El paso 7 omitirá la constancia pero verificará el registro."
  echo ""
fi

paso() { echo; echo "[$1/7] $2"; }
fallar() { echo "  ❌ $1"; echo "❌ FALLO EN PASO $2"; exit 1; }

echo "=== ENSAYO GENERAL DEL FLUJO DE FICHA DE DEPÓSITO (S8) ==="
echo "Repo: $ROOT | tmp: $DIR_TMP"
echo "API: $API | mock: $MOCK | firma: $VISTOBUENO_FIRMA"

paso 1 "Userscript: dependencias y dist"
cd "$ROOT/tools/dspace-fill"
[ -d node_modules ] || npm ci --no-fund --no-audit > /tmp/npm-ensayo.log 2>&1
npm run build > /dev/null
[ -f dist/vistobueno-dspace-fill.user.js ] || fallar "no se generó el dist" 1
echo "  ✅ dist construido"

paso 2 "DOC bueno del factory (determinista)"
cd "$ROOT"
"$BACKEND_PY" - <<PY
import sys
sys.path.insert(0, "tests")
from docx_factory import compilar_docx, configuracion_base
ruta = compilar_docx(configuracion_base())
import shutil
shutil.copy(ruta, "$DIR_TMP/plan_cuantitativo.docx")
print("  ✅ doc bueno generado")
PY

paso 3 "API en :8000 (con firma configurada)"
limpiar
sleep 1
setsid nohup "$BACKEND_PY" -m uvicorn validator.api:app --host 127.0.0.1 --port 8000 \
  > "$DIR_TMP/api.log" 2>&1 < /dev/null &
for i in $(seq 1 20); do
  curl -sf -o /dev/null "$API/docs" && break
  sleep 1
done
curl -sf -o /dev/null "$API/docs" || fallar "la API no arrancó (log: $DIR_TMP/api.log)" 3
echo "  ✅ API arriba"

paso 4 "Mock de DSpace en :8080"
setsid nohup node "$ROOT/tools/dspace-fill/dev/mock-dspace/server.js" \
  > "$DIR_TMP/mock.log" 2>&1 < /dev/null &
for i in $(seq 1 10); do
  curl -sf -o /dev/null "$MOCK/" && break
  sleep 1
done
curl -sf -o /dev/null "$MOCK/" || fallar "el mock no arrancó (log: $DIR_TMP/mock.log)" 4
echo "  ✅ mock arriba (proxy del buzón activo)"

paso 5 "Validar el DOC bueno y publicar la ficha en el buzón"
"$BACKEND_PY" - <<PY
import sys
sys.path.insert(0, "tests")
import httpx

r = httpx.post(
    "$API/validar",
    files={"archivo": ("plan_cuantitativo.docx", open("$DIR_TMP/plan_cuantitativo.docx", "rb"),
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    timeout=120,
)
assert r.status_code == 200, r.text
datos = r.json()
assert datos["semaforo"] == "verde", "el doc bueno dio semáforo " + datos["semaforo"]
ficha = datos["ficha_deposito"]
assert ficha is not None, "sin ficha en la respuesta verde"
assert ficha["extraidos"][0]["detectado"], "el motor no capturó el título"

# Manuales del operador (los que teclearía en la pantalla de Int2).
for campo in ficha["manuales"]:
    if campo["campo"] == "matricula":
        campo["valor"] = "10584011-18"
    if campo["campo"] == "renati.author.dni":
        campo["valor"] = "12345678"

pub = httpx.post("$API/ficha-pendiente", json=ficha, timeout=30)
assert pub.status_code == 204, pub.text
print("  ✅ verde + ficha capturada + publicada en el buzón (204)")
PY
[ $? -eq 0 ] || fallar "validación/publicación de la ficha" 5

paso 6 "Userscript contra el mock: relleno, Depositar y handle"
cd "$ROOT/tools/dspace-fill"
node dev/e2e_ensayo.js || fallar "driver del ensayo (ver salida arriba)" 6

paso 7 "Papeleo: registro descargable y constancia"
cd "$ROOT"
"$BACKEND_PY" - <<PY
import sys, os
sys.path.insert(0, "tests")
import httpx
import io
import zipfile

dep = httpx.get("$API/deposito", timeout=30).json()
assert "hdl.handle.net" in dep["handle"], dep
assert dep["timestamp"], dep

ficha = httpx.get("$API/ficha-pendiente", timeout=30).json()
cuerpo = {"ficha": ficha, "handle": dep["handle"], "timestamp": dep["timestamp"]}

for formato, firma in (("csv", b"registro.csv"), ("xlsx", b"registro.xlsx")):
    r = httpx.post("$API/fila-registro?formato=" + formato, json=cuerpo, timeout=30)
    assert r.status_code == 200, r.text
    assert "attachment" in r.headers.get("content-disposition", "")
    assert (formato == "xlsx") == r.content.startswith(b"PK")
    with open("$DIR_TMP/" + firma.decode(), "wb") as f:
        f.write(r.content)
    print("  ✅ registro." + formato + " (" + str(len(r.content)) + " bytes, descargable)")

# La constancia requiere la plantilla del Modelo B (recursos/, no
# versionado). En CI/clone fresco no existe: se verifica el registro
# igual y se reporta la constancia como omitida (hallazgo 16a).
plantilla_resuelta = os.environ.get("VISTOBUENO_PLANTILLA_CONSTANCIA", "")

if plantilla_resuelta and os.path.isfile(plantilla_resuelta):
    r = httpx.post("$API/constancia", json={**cuerpo, "indice_autor": 0}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"PK")
    with open("$DIR_TMP/constancia.docx", "wb") as f:
        f.write(r.content)
    print("  ✅ constancia.docx (" + str(len(r.content)) + " bytes)")

    with zipfile.ZipFile(io.BytesIO(r.content)) as docx:
        xml = docx.read("word/document.xml").decode("utf-8")
    assert "MERGEFIELD" not in xml, "la constancia quedó con MERGEFIELD sin reemplazar"
    assert "10584011-18" in xml, "la constancia no lleva la matrícula"
    assert "hdl.handle.net" in xml, "la constancia no lleva el handle"
    print("  ✅ constancia verificada: MERGEFIELD reemplazados, matrícula y handle presentes")

    r = httpx.post("$API/constancia?formato=zip", json={**cuerpo, "indice_autor": 0}, timeout=30)
    assert r.status_code == 200, r.text
    with zipfile.ZipFile(io.BytesIO(r.content)) as paquete:
        nombres = paquete.namelist()
        assert any(n.endswith(".docx") for n in nombres), nombres
        csv = paquete.read("registro.csv").decode("utf-8")
        assert "10584011-18" in csv and "hdl.handle.net" in csv
    with open("$DIR_TMP/constancia-registro.zip", "wb") as f:
        f.write(r.content)
    print("  ✅ paquete zip: constancia + registro.csv del autor (" + str(len(r.content)) + " bytes)")
else:
    print("  ⏭️ constancia omitida: plantilla del Modelo B no disponible (CI/clone fresco)")
    print("     El registro descargable SÍ se verificó arriba.")

print("  ✅ handle:", dep["handle"])
PY
[ $? -eq 0 ] || fallar "generación/verificación de constancia y registro" 7

echo
echo "✅ FLUJO COMPLETO OK — evidencia en $DIR_TMP (api.log, mock.log, registro.*, constancia.docx)"
