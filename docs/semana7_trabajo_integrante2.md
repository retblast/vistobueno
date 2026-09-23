# Semana 7 — Pruebas de usabilidad + documentación

**Integrante**: Integrante 2 (Frontend / UX)  
**Fecha**: 2026-09-23  
**Rama**: `s7-usabilidad-ihc` (PRs: retblast#31, Rodo00#10)

---

## Objetivos

1. Ejecutar pruebas de usabilidad del flujo de carga y visualización de resultados.
2. Aplicar mejoras IHC a la interfaz.
3. Pruebas finales del flujo completo (frontend ↔ backend).
4. Corregir errores y documentar avances.

---

## Actividades realizadas

### Evaluación IHC

Se evaluaron las interfaces de **carga**, **resultados** y **desplegables** contra principios de usabilidad (visibilidad de estado, prevención de errores, affordance, contraste, redundancia). Hallazgos principales:

- Límite de archivo inconsistente (25 MB UI vs 10 MB backend).
- Falta de feedback durante la validación.
- Errores de API ocultos detrás del reporte mock.
- Click en dropzone no abría el selector.
- Badge de severidad redundante con el icono.
- Fuentes por debajo de 12 px en contadores/detalles.
- `API_BASE_URL=''` acoplada a mismo origen sin documentar.

### Correcciones aplicadas (commit `e27e683` + commit de revisión)

| Área | Cambio |
|------|--------|
| **Carga** | Límite unificado a **10 MB**; spinner + dropzone deshabilitada; click en toda la dropzone; botón ✕ para quitar archivo; aviso de error cerrable; solo `.docx`. |
| **Errores API** | HTTP con cuerpo JSON (`detail`) → mensaje real al usuario **sin** mock. Error de red o proxy sin JSON → fallback a mock **como modo demo** (avisado en Report con `__mock`). Título de aviso genérico: “No se pudo validar.” |
| **Resultados** | Scroll suave al semáforo; categorías en cards IA en vez de `rule_id`; desplegables cerrados por defecto; badge de severidad eliminado (redundante con icono); iconos compactos con `aria-label`. |
| **Layout / CSS** | Pantalla completa centrada (alto y ancho); botón “← Validar otro archivo” visible; separación intro ↔ dropzone; footer separado; fuentes mínimas 12 px; `focus-visible` en `summary`/labels; botón Copiar ≥ 44 px; contraste dark en chips/avisos; spinner. |

### Documentación de despliegue (punto 2 de `Arreglos.txt`)

- `README.md` → sección **“Despliegue del frontend (`VITE_API_URL` y proxy)”**: tabla dev / preview / build, nota de reverse proxy y modo demo.
- `frontend/src/App.jsx` y `frontend/vite.config.js` → comentarios sobre alcance del proxy (solo `vite dev`) y variables de entorno.
- `frontend/.env.example` → plantilla de `VITE_API_URL`.

### Pruebas del flujo completo

- Backend: `.venv/bin/python -m uvicorn validator.api:app` en `:8000` (PID estable con `setsid`).
- Frontend: `npm run dev` en `:5173`.
- `POST` a `http://localhost:5173/validar` (proxy) → **HTTP 200**, 41 reglas, semáforo rojo con DOCX de prueba.
- Suite de tests backend: **132 passed, 17 skipped** (verificado en iteraciones previas).

---

## Evidencias

- Commits: `e27e683` (mejoras IHC), commit de correcciones de `Arreglos.txt`.
- PRs: https://github.com/retblast/vistobueno/pull/31 · https://github.com/Rodo00/vistobueno/pull/10
- Archivos: `frontend/src/components/Upload.jsx`, `Report.jsx`, `frontend/src/index.css`, `frontend/src/App.jsx`, `frontend/vite.config.js`, `frontend/.env.example`, `README.md`.

---

## Relación con competencias curriculares

| Competencia | Evidencia |
|-------------|-----------|
| **Interacción Humano-Computador** | Evaluación IHC, correcciones de usabilidad, pruebas de flujo, documentación de avances. |
| **Ingeniería de Software II** | Separación de manejo de errores (red vs HTTP), documentación de configuración de despliegue. |

---

## Dificultades y aprendizajes

- Distinguir **error de red** vs **respuesta HTTP con detalle** evita ocultar fallos reales del backend detrás del modo demo.
- El proxy de Vite **no existe** en build estático: hay que documentar `VITE_API_URL` o reverse proxy desde el inicio.

---

## Plan siguiente

- Integrar feedback de revisión del PR (si lo hay).
- Cerrar actividad 7 en `resultados_vistobueno/S7_pruebas_usabilidad/resumen.txt`.
