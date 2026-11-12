# Handover de correctitud — 2026-11-12

## 1. Alcance y reglas de ejecución

**Base auditada:** `master`, `9fdfc57`. **Estado:** trabajo pendiente.
Este documento asigna tareas. No afirma que los defectos estén corregidos.
Los ID `VA` corresponden a esta auditoría; no reemplazan los ID `AUD` anteriores.

**retblast es únicamente Integrante 1.** Leer y ejecutar solo su documento.
Los documentos de Int2 e Int3 pertenecen a esos integrantes. Una dependencia
no autoriza a modificar sus archivos. Si falta su entrega, registrar «bloqueado por
dependencia» y continuar otra tarea propia. No implementar su parte.

| Integrante | Entrega propia | No implementar |
|---|---|---|
| Int1 — retblast | API, DTO, buzón, correo, constancias, userscript, pruebas de esas áreas y docs de contrato | Frontend, extractor, motor, analizadores, reglas YAML y factory del motor |
| Int2 | SPA, pruebas de frontend y evidencia de uso | API, userscript y motor |
| Int3 | Extractor, motor, reglas, exportador/CLI y pruebas/factory del motor | API, userscript y SPA |

Los cambios de contrato se acuerdan por escrito: Int1 publica el contrato;
cada integrante adapta **sus** archivos. Este handover no delega permisos.

1. Trabajar en una rama por lote. No cambiar ramas de otro integrante.
2. Leer la tarea completa, sus dependencias y su prueba de aceptación.
3. Reproducir el fallo antes de corregirlo. Agregar una regresión que falle.
4. Corregir la causa. No ocultar el fallo, bajar severidades ni relajar el CI.
5. Verificar la regresión, la suite y los documentos reales afectados.
6. Registrar comando, resultado, limitaciones y PR/commit en la tabla §2.
7. Mantener `AGENTS.md` intacto salvo aprobación explícita del usuario.

No subir tesis reales, HAR, credenciales ni datos personales. Los fixtures usan
nombres ficticios. El HAR local conserva un login con credenciales no vacías.
No usarlo como adjunto de un PR. No escribir directamente en la API de DSpace.

**Resultado esperado:** reglas automatizadas correctas dentro de un alcance
declarado. No equivale a certificar todo el manual ni el contenido académico.

## Documentos por integrante

- **retblast / Int1:** [API y userscript; ejecutar B1–B8](HANDOVER_CORRECTITUD_INT1_2026-11-12.md).
- **Int2:** [frontend; ejecutar F1–F5](HANDOVER_CORRECTITUD_INT2_2026-11-12.md).
- **Int3:** [motor; ejecutar M0–M12 y M1a](HANDOVER_CORRECTITUD_INT3_2026-11-12.md).

La puerta de Angular está en §2 del documento de Int1. No se ha implementado
el diagnóstico ni se ha ejecutado el laboratorio Angular: son entregables pendientes.
Ver [plan de captura y laboratorio local](PLAN_LAB_DSPACE_LOCAL_2026-11-12.md).
No se realizan guardados experimentales en UNT. Los nombres mixtos están
confirmados por el usuario según la tesis aprobada por el jefe.

## Ampliación normativa

La [auditoría del manual y plantillas](AUDITORIA_NORMATIVA_2026-11-12.md)
incluye 66 grupos de requisitos, 226 criterios de rúbricas y 49 reglas activas.
NM-01 a NM-07 son trabajo de Int3 / M12. Int2 amplía F3 para comunicar alcance.
NM-08 registra la política confirmada: emular siempre acceso abierto en el
piloto. Int1 verifica su persistencia en B3. Su lista propia sigue siendo B1–B8.

## 2. Estado por hallazgo

`P1`: resolver antes del piloto. `P2`: resolver antes de declarar el alcance
completo. Cada documento por integrante indica archivos y aceptación. Los defectos
están pendientes de integración y verificación final. NM-08 registra una política decidida.

| ID | Prioridad | Problema | Tarea / dueño | Estado |
|---|---|---|---|---|
| VA-01 | P1 | Solo se revisa el primer run | M1 / Int3 | Pendiente |
| VA-02 | P1 | Formato heredado y propiedades omitidas | M1 / Int3 | Pendiente |
| VA-03 | P1 | Papel incorrecto en secciones posteriores | M2 / Int3 | Pendiente |
| VA-04 | P2 | Paginación incorrecta | M3 / Int3 | Pendiente |
| VA-05 | P2 | Dos tipos declarados: gana el primero | M4 / Int3 | Pendiente |
| VA-06 | P2 | Resumen sin máximo de palabras | M5 / Int3 | Pendiente |
| VA-07 | P2 | Abstract vacío; palabras clave incompletas | M5 / Int3 | Pendiente |
| VA-08 | P1 | Permanecen filas de autores/DNI anteriores | B4 / Int1 | Pendiente |
| VA-09 | P1 | Ficha y depósito sin identidad de trámite | B2 + F2 / Int1, Int2 | PR #95 abierto (Int1); contrato v1.13.0 publicado. Falta F2 (Int2) para la SPA |
| VA-10 | P1 | Resguardo identificado solo por filename | F1 / Int2 | Pendiente |
| VA-11 | P2 | DOCX malformado devuelve 500 | M1a + B5 / Int3, Int1 | Pendiente |
| VA-12 | P2 | Markdown activo en el PDF | M9 / Int3 | Pendiente |
| VA-13 | P1 | Autores, asesor, año y palabras clave mal capturados | M0 / Int3 | PR #75 abierto |
| VA-14 | P2 | «Base de datos» acordado, pero no aplicado | M6 / Int3 | Pendiente |
| VA-15 | P2 | Se anuncia tamaño de logo sin medirlo | M7 / Int3 | Pendiente |
| VA-16 | P2 | ORCID sin comprobación por persona/destino | M8 / Int3 | Pendiente |
| VA-17 | P1 | Ejemplos DOCX dañados; guardia incompleta | B6 / Int1; M11 / Int3 | Pendiente |
| VA-18 | P2 | Total presentado como reglas evaluadas | B7 + M10 / Int1, Int3 | PR #93 abierto (Int1). Falta M10 (Int3) para CLI y exportador |
| VA-19 | P1 | Un archivo real bloquea la siguiente validación | B1 + F4 / Int1, Int2 | Pendiente |
| VA-20 | P1 | Éxito de relleno sin comprobar aceptación de Angular | B3 / Int1 | Pendiente |
| VA-21 | P1 | Autofill y restauración del navegador pueden recuperar datos ajenos | B8 + F5 / Int1, Int2 | Riesgo reportado; verificar en navegador real |
| NM-01 | P1 | Paginación normativa incorrecta | M12a / Int3 | Pendiente |
| NM-02 | P1 | Carátula acepta escuela ausente y asesor 36 pt | M12b / Int3 | Pendiente |
| NM-03 | P1 | Esquemas y alcance sin correspondencia demostrada | M12c / Int3; F3 / Int2 | Pendiente |
| NM-04 | P2 | Longitud de título y orden de autores | M12d / Int3 | Pendiente de decisiones y reglas |
| NM-05 | P2 | Conteo y mínimos de referencias por ámbito | M12e / Int3 | Pendiente |
| NM-06 | P2 | Anexos incompletos y fuentes contradictorias | M12f / Int3 | Pendiente de decisiones y reglas |
| NM-07 | P2 | Citas normativas sin origen literal comprobado | M12g / Int3 | Pendiente |
| NM-08 | Decisión | Acceso abierto fijo reproduce al jefe | B3 / Int1 | Política decidida 2026-11-12; persistencia pendiente en B3 |

### 2.1 Registro de ejecución de Int1

Comando, resultado, limitaciones y PR de cada lote entregado. Un PR abierto no
cierra el hallazgo: falta la integración y, cuando aplica, la evidencia en el
navegador real.

| Lote | Hallazgo | PR / commit | Comandos de verificación | Resultado | Limitaciones |
|---|---|---|---|---|---|
| B7 | VA-18 | PR #93, commit `38868b9` | `nix run .#test -- tests/test_notificacion.py -v` (27 passed); `nix run .#test -- tests/ -q` (825 passed, 4 skipped, 6 xfailed); `ruff check` | El correo usa `resumen.total_evaluadas`: 49 totales y 41 evaluadas muestran 41 en HTML y texto | El mismo cambio en CLI y exportador es de Int3 (M10) |
| B2 | VA-09 | PR #95, commit `d9b7e1d` | `pytest tests/ -q` (837 passed, 4 skipped, 6 xfailed, cobertura 93.60 %); `ruff check`; `ruff format --check`; `mypy validator/ scripts/`; `python3 scripts/generate_openapi.py --check`; `npm --prefix tools/dspace-fill test` (42 passed) y drift de `dist/`; `npm --prefix frontend test|lint|build` (76 tests); `nix run .#test-ficha-deposito` (FLUJO COMPLETO OK); `nix flake check` | Contrato v1.13.0: `tramite_id` obligatorio, título observado, papeleo ligado al depósito vigente (409 si no) | La SPA sigue en v1.12.0 hasta que Int2 cierre F2. Eluserscript antiguo falla cerrado: sin `tramite_id` no reporta |
| B1 | VA-19 | — | Medición local con la plantilla oficial: 0.196 s de `thread_time` y 17.99 s de latencia de pared; la latencia del auditor no se reproduce aquí | No se tocaron los valores por defecto | Bloqueado por decisión del responsable: falta medir en la máquina del operador y acordar presupuesto y ventana. El test de dos validaciones consecutivas sin limpiar el limitador sigue pendiente |

## 3. Orden de integración y cierre

| Lote | Trabajo | Dependencia / puerta |
|---|---|---|
| A | M0 y M11 por Int3; B1 y contrato B2 por Int1 | B6 espera M11; no cambiar ramas de otro autor |
| B | M1a+B5; M1; M2; F1 | Fixtures válidos; coordinación de extractor |
| C | B2+F2; B3+B4+B8; F4+F5 | Contrato publicado en el PR, todos los consumidores adaptados |
| D | M3–M10 y M12 por Int3; B7 por Int1; F3 por Int2 | Decisiones de dominio con fuente |
| E | Regresión real, ensayo Angular de Int1 y piloto | Ningún P1 pendiente |

Pueden avanzar tareas independientes. No integrar una mitad del nuevo contrato
dejando el userscript o la SPA incompatibles. Un PR de documentación no cierra
un defecto funcional.

**Lista ejecutable de retblast:** B1, B2, B3, B4, B5 cuando Int3 entregue M1a,
B6 cuando Int3 entregue M11, B7 y B8. F1–F5 y M0–M12 son entregas de otros
integrantes. Retblast puede revisar sus resultados; no implementarlos.

Antes de cada cierre, ejecutar las comprobaciones del área y la suite completa:

```bash
nix develop -c pytest tests/ -v
nix develop -c ruff check validator/ scripts/ tests/
nix develop -c ruff format --check validator/ scripts/ tests/
nix develop -c mypy validator/ scripts/
nix develop -c python3 scripts/generate_openapi.py --check
nix develop -c npm --prefix frontend test
nix develop -c npm --prefix frontend run lint
nix develop -c npm --prefix frontend run build
nix develop -c npm --prefix tools/dspace-fill ci
nix develop -c npm --prefix tools/dspace-fill test
nix run .#test-ficha-deposito
nix flake check
```

El comando de depósito anterior usa el mock. Para Angular real se ejecuta
§2 del documento de Int1.
Verificar drift de `tools/dspace-fill/dist/`. Al tocar reglas, contrastar las
dos tesis locales y las cinco plantillas. No fijar como éxito el conteo histórico
de tests: nuevas regresiones cambian ese conteo.

Actualizar §2 y §11 de `HANDOVER_AUDITORIA_2026-10-26.md` con PR/commit y
evidencia al cerrar. Cambios de contrato requieren README, contrato, OpenAPI,
ejemplos y clientes sincronizados. Mantener bitácoras. No editar `AGENTS.md`
sin la aprobación indicada allí.

## 4. Qué permite afirmar «correcto»

Cerrar estos hallazgos es necesario; no demuestra correctitud universal.
Antes de declarar listo el producto, el equipo debe completar esta matriz:

| Evidencia necesaria | Responsable | Criterio |
|---|---|---|
| Requisito del manual → regla → prueba → límite declarado | Int3; valida encargado | Cada requisito del alcance tiene fuente y estado: automatizado, manual o no soportado |
| Pares DOCX equivalentes con formato directo y estilos | Int3 | Mismo resultado; mutaciones incorrectas detectadas |
| Corpus real autorizado con revisión independiente | Int3 + encargado | Explicar cada falso positivo y negativo; no solo obtener verde en una tesis |
| API y clientes con el mismo contrato | Int1 + Int2 | Ningún resultado de otro trámite genera papeleo |
| Relleno Angular persistido localmente, §2 de Int1 | Int1 | Campos sobreviven a recarga en DSpace local; diferencias con UNT documentadas |
| Recuperación y uso en máquina del operador | Int2 + Int1 | Windows/WSL, tiempos, recarga y segunda tesis comprobados |
| Comunicación del alcance | Int2; revisan Int1 e Int3 | Verde significa ausencia de errores en controles ejecutados, no aprobación académica |

No convertir límites desconocidos en «cumple». No asegurar página exacta sin
evidencia de render. No declarar validados esquemas que la API no carga.
Los tipos sin documentos reales siguen pendientes de validación. El asistente
de IA no reemplaza comprobaciones deterministas y su conexión no es parte de
estos arreglos. La aprobación institucional final corresponde al encargado.
