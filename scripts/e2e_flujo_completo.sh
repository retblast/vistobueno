#!/usr/bin/env bash
# Pruebas finales del flujo completo — Semana 7 (flujo completo con
# notificación v1.3.0). Versionado en el repo (observación Arreglos.txt v4).
#
# Uso (desde cualquier directorio):
#   ./scripts/e2e_flujo_completo.sh
#
# Requisitos: servicios libres en :8000 y :5173 (el script los
# (re)inicia), frontend con dependencias instaladas (npm ci) y un
# intérprete Python con las dependencias del proyecto (.venv o nix).
# La evidencia se imprime en stdout (redirigir a un .log si se desea).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
if [ -x "$ROOT/.venv/bin/python" ]; then
  BACKEND_VENV="$ROOT/.venv/bin/python"
else
  BACKEND_VENV="python3"
fi
DOCX="/tmp/tesis_prueba.docx"
BAD="/tmp/bad.txt"

echo "=== PRUEBAS E2E FLUJO COMPLETO S7 ==="
echo "Repo: $ROOT"
echo "Fecha: $(date)"
echo

# 0. Build frontend
echo "[0/9] Build frontend (npm run build)..."
cd "$FRONTEND" && npm run build > /tmp/build.log 2>&1
echo "  ✅ Build OK (dist/ generado)"

# 1. Tests backend (sin --cov: el addopts de pyproject ya no lo exige)
echo "[1/9] Tests backend (pytest)..."
cd "$ROOT" && "$BACKEND_VENV" -m pytest tests/ -q --tb=no 2>&1 | tail -1
echo "  ✅ pytest terminó sin fallos (el resumen real está en la línea de arriba; puede incluir skipped)"

# 2. Levantar backend
echo "[2/9] Levantando backend en :8000..."
pkill -f "uvicorn validator" 2>/dev/null || true
sleep 1
setsid nohup "$BACKEND_VENV" -m uvicorn validator.api:app --host 0.0.0.0 --port 8000 \
  > /tmp/backend.log 2>&1 < /dev/null &
sleep 3
curl -sf -o /dev/null http://127.0.0.1:8000/docs && echo "  ✅ Backend UP" || { echo "  ❌ Backend no arrancó"; exit 1; }

# 3. Levantar frontend (dev)
echo "[3/9] Levantando frontend en :5173..."
pkill -f "vite" 2>/dev/null || true
sleep 1
cd "$FRONTEND" && setsid nohup npm run dev > /tmp/frontend.log 2>&1 < /dev/null &
sleep 5
curl -sf -o /dev/null http://127.0.0.1:5173 && echo "  ✅ Frontend UP" || { echo "  ❌ Frontend no arrancó"; exit 1; }

# 4. Generar DOCX de prueba
echo "[4/9] Generando DOCX de prueba (1024 bytes objetivo)..."
"$BACKEND_VENV" -c "
from tests._docx_generator import build_large_docx
open('$DOCX','wb').write(build_large_docx(1024))
print('  ✅ DOCX generado:', __import__('os').path.getsize('$DOCX'), 'bytes')
"

# 5. Test válido -> 200 + reglas (>= 47: el PR #46 del backend amplió la suite)
echo "[5/9] POST /validar con DOCX válido (proxy :5173)..."
HTTP=$(curl -s -m 15 -o /tmp/ok.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar -F "archivo=@$DOCX")
python3 -c "
import json
d=json.load(open('/tmp/ok.json'))
assert d['resumen']['total']>=47, 'reglas<47'
assert d['semaforo'] in ('rojo','verde'), 'semaforo invalido'
# Contrato v1.5: aplicabilidad por tipo de documento
r=d['resumen']
assert 'total_evaluadas' in r, 'falta total_evaluadas'
assert r['total'] >= r['total_evaluadas'] >= 0, 'total_evaluadas incoherente'
assert r['total'] - r['total_evaluadas'] == r.get('reglas_no_aplicables', 0), 'reglas_no_aplicables incoherente'
assert all('aplicable' in x for x in d['resultados']), 'falta aplicable en resultados'
m=d.get('metadatos', {})
assert m.get('tipo_documento_estado') in ('vigente','sin_determinar','contradictorio'), f'tipo_documento_estado invalido: {m.get("tipo_documento_estado")!r}'
# Contrato v1.6: depósito en DSpace (sin depositar=true → sin_solicitud)
assert d.get('deposito', {}).get('estado') == 'sin_solicitud', f'deposito inesperado: {d.get("deposito")!r}'
print('  ✅ HTTP', '$HTTP', '| total:', r['total'], '| evaluadas:', r['total_evaluadas'], '| semaforo:', d['semaforo'])
" || { echo "  ❌ Falló validación"; exit 1; }

# 6. Error 415 con detail JSON (NO mock)
echo "[6/9] POST /validar con archivo .txt (debe dar 415 + detail JSON)..."
echo "x" > "$BAD"
HTTP=$(curl -s -m 5 -o /tmp/bad.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar -F "archivo=@$BAD")
python3 -c "
import json
assert '$HTTP' == '415', 'HTTP!=415'
d=json.load(open('/tmp/bad.json'))
assert 'detail' in d, 'falta detail'
assert 'docx' in d['detail'].lower(), 'detail no menciona docx'
print('  ✅ HTTP', '$HTTP', '| detail:', d['detail'][:80])
" || { echo "  ❌ Error 415 sin detail"; exit 1; }

# 7. Correo inválido -> 422 con detail español (NO mock)
echo "[7/9] correo inválido (debe dar 422 + detail)..."
HTTP=$(curl -s -m 15 -o /tmp/mal.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar -F "archivo=@$DOCX" -F "correo=esto-no-es-un-correo")
python3 -c "
import json
assert '$HTTP' == '422', 'HTTP!=422'
d=json.load(open('/tmp/mal.json'))
assert 'detail' in d, 'falta detail'
print('  ✅ HTTP', '$HTTP', '| detail:', str(d['detail'])[:80])
" || { echo "  ❌ 422 esperado"; exit 1; }

# 8. Correo válido + notificar=true -> 200 (opt-in aceptado + estado)
echo "[8/9] correo válido + notificar=true (debe dar 200 + notificacion.estado)..."
HTTP=$(curl -s -m 15 -o /tmp/notif.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar \
  -F "archivo=@$DOCX" -F "correo=estudiante@correo.unt.edu.pe" -F "notificar=true")
python3 -c "
import json
assert '$HTTP' == '200', 'HTTP!=200'
d=json.load(open('/tmp/notif.json'))
estado = d.get('notificacion', {}).get('estado')
VALIDOS = {'enviado','fallo','sin_correo','sin_observaciones','deshabilitado','no_solicitado'}
assert estado in VALIDOS, f'estado inesperado: {estado!r}'
print('  ✅ HTTP', '$HTTP', '| notificacion.estado:', estado)
" || { echo "  ❌ notificar=true rechazado o estado inválido"; exit 1; }

# 8b. Correo SIN notificar -> estado no_solicitado (opt-in real)
echo "[8b/9] correo SIN notificar (debe dar notificacion.estado=no_solicitado)..."
HTTP=$(curl -s -m 15 -o /tmp/no_sol.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar \
  -F "archivo=@$DOCX" -F "correo=estudiante@correo.unt.edu.pe")
python3 -c "
import json
assert '$HTTP' == '200', 'HTTP!=200'
d=json.load(open('/tmp/no_sol.json'))
estado = d.get('notificacion', {}).get('estado')
assert estado == 'no_solicitado', f'esperaba no_solicitado, vino: {estado!r}'
print('  ✅ HTTP', '$HTTP', '| notificacion.estado:', estado)
" || { echo "  ❌ no_solicitado no devuelto"; exit 1; }

# 8c. depositar=true con semáforo NO verde -> deposito.estado=no_apto (contrato v1.6)
echo "[8c/9] depositar=true con semáforo rojo (debe dar 200 + deposito.estado=no_apto)..."
HTTP=$(curl -s -m 15 -o /tmp/dep.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar \
  -F "archivo=@$DOCX" -F "depositar=true" -F "titulo=Tesis de prueba" -F "autores=Pérez, A.")
python3 -c "
import json
assert '$HTTP' == '200', 'HTTP!=200'
d=json.load(open('/tmp/dep.json'))
estado = d.get('deposito', {}).get('estado')
assert estado == 'no_apto', f'esperaba no_apto, vino: {estado!r}'
assert d['semaforo'] == 'rojo', 'el doc de prueba debía ser rojo'
print('  ✅ HTTP', '$HTTP', '| deposito.estado:', estado)
" || { echo "  ❌ deposito no_apto no devuelto"; exit 1; }

# 9. Backend caído -> proxy 500 body vacío -> mock avisado
echo "[9/9] Backend caído -> proxy 500 vacío -> mock avisado..."
pkill -f "uvicorn validator" 2>/dev/null || true
sleep 1
HTTP=$(curl -s -m 5 -o /tmp/down.json -w "%{http_code}" -X POST http://127.0.0.1:5173/validar -F "archivo=@$DOCX")
SIZE=$(wc -c < /tmp/down.json)
python3 -c "
assert '$HTTP' == '500', f'esperaba 500, vino $HTTP'
assert '$SIZE' == '0', f'body no vacio: $SIZE'
print('  ✅ Proxy 500 body vacío (size=0) -> frontend debe ir a mock demo')
"

# Restaurar backend
setsid nohup "$BACKEND_VENV" -m uvicorn validator.api:app --host 0.0.0.0 --port 8000 \
  > /tmp/backend.log 2>&1 < /dev/null &
sleep 3
curl -sf -o /dev/null http://127.0.0.1:8000/docs && echo "  ✅ Backend restaurado"

echo
echo "=== TODAS LAS PRUEBAS E2E PASARON ==="
echo "Fecha fin: $(date)"
