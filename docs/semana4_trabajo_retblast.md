# Semana 4 — Trabajo realizado

**Integrante**: retblast  
**Rol**: Integrante 1 — Backend / API  
**Semana**: 4 de 14 (22/09/2026 – 26/09/2026)  
**Proyecto**: VistoBueno — Validador automático de formato de tesis (UNT FECyC)

---

## Objetivos de la semana

1. Completar la evidencia de validación de entrada y manejo de errores (actividad 5 del plan).
2. Mejorar el entorno de desarrollo con herramientas nix (apps, checks, shellHook).
3. Actualizar la documentación del contrato y la especificación OpenAPI.

---

## Actividades realizadas

### Día 1 (22/09/2026): Entorno de desarrollo y rama de trabajo

**Fecha**: 22/09/2026  
**Acción**: Se creó la rama de trabajo `semana4-backend-error-handling-tests` y se mejoró el `flake.nix` del proyecto.

**Cambios en `flake.nix`**:
- Se agregó la sección `apps` para exponer comandos ejecutables vía `nix run`:
  - `nix run .#test` — ejecuta pytest
  - `nix run .#serve` — inicia uvicorn
- Se agregó la sección `checks` para ejecutar pytest vía `nix flake check`
- Se mejoró el `shellHook` para mostrar un menú de comandos disponibles al entrar al entorno

**Problemas encontrados y corregidos**:
- Se introdujo un error de sintaxis al editar el flake (punto y coma faltante en el bloque `checks`). El error se detectó con `nix flake show` y se corrigió inmediatamente.

**Commits**:
- `a9faf1e` — `chore(env): mejorar flake.nix con apps, checks y shellHook`
- `5efd18d` — `fix(env): agregar punto y coma faltante en flake.nix`

**Verificación**:
- `nix develop` — imprime el menú de comandos correctamente
- `nix flake show` — lista apps, checks y devShells
- `nix run .#test -- tests/ -v` — 53/53 tests pasando

---

### Día 2 (23/09/2026): _Pendiente_

---

### Día 3 (24/09/2026): _Pendiente_

---

## Evidencias producidas

| Evidencia | Archivo | Competencia curricular |
|-----------|---------|------------------------|
| Entorno de desarrollo con apps nix | `flake.nix` | Ingeniería de Software I |
| Menú de comandos en shellHook | `flake.nix` | Ingeniería de Software I |
| Corrección de error de sintaxis | `flake.nix` | Ingeniería de Software II |

---

## Relación con competencias

| Competencia | Actividad |
|-------------|-----------|
| **Ingeniería de Software I** — Technical documentation, tooling | Mejora del entorno de desarrollo con nix apps y shellHook documentado |
| **Ingeniería de Software II** — Configuration management | Gestión del entorno reproducible con Nix flake |

---

## Pendiente

- [x] Crear rama de trabajo
- [x] Mejorar flake.nix (apps, checks, shellHook)
- [x] Verificar entorno (nix develop, nix flake show, nix run)
- [ ] Test de archivo excedido (413) — Día 2
- [ ] Actualizar CONTRATO_API.md — Día 3
- [ ] Regenerar openapi_spec.json — Día 3
- [ ] Completar bitácora con Días 2 y 3

---

## Plan siguiente (Días 2–3)

- **Día 2**: Implementar test de archivo excedido (413) con generador de DOCX grande usando lorem ipsum.
- **Día 3**: Actualizar documentación (CONTRATO_API.md, openapi_spec.json) y completar bitácora.
