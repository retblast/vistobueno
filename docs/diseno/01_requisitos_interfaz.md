# Actividad 1 — Análisis de requisitos de interfaz

**Proyecto:** VistoBueno — Validación automática de formato de tesis
**Institución:** Universidad Nacional de Trujillo (UNT) — FECyC
**Autor:** Integrante 2 (Frontend / Experiencia de usuario)
**Fecha:** Semana 1

---

## 1. Contexto del sistema

**VistoBueno** es una aplicación web diseñada para la Biblioteca de la Facultad de Educación y Ciencias de la Comunicación (FECyC) de la Universidad Nacional de Trujillo. Su propósito es **validar automáticamente el formato de documentos de tesis** (DOCX) contra las directivas institucionales vigentes.

El sistema está orientado al **personal de la sede (Repositorio FECyC)**, que opera la web para validar documentos y el sistema notifica al estudiante por correo. Evita rechazos en la entrega de tesis por errores de presentación.

---

## 2. Usuarios objetivo

| Usuario | Descripción | Necesidad principal |
|---------|-------------|---------------------|
| **Personal del Repositorio FECyC** (operador principal) | Opera la web, sube y valida documentos de tesis | Herramienta ágil para verificar cumplimiento y notificar al estudiante |
| Estudiante de pregrado / postgrado | Receptor de la notificación (no opera la web) | Recibir el reporte de validación por correo |
| Bibliotecario/a | Revisa documentos antes de aceptar | Herramienta auxiliar para verificar cumplimiento |

---

## 3. Objetivos de la interfaz

1. Permitir al **operador del Repositorio FECyC** **validar el documento de tesis** de forma rápida y sencilla
2. Mostrar el **resultado de validación** de manera clara y visual (semáforo)
3. Proporcionar un **reporte detallado** organizado por categorías de reglas
4. Ofrecer **prompts listos para copiar** que el operador pueda usar en una IA para corregir problemas
5. **Capturar el correo del estudiante** (opcional) para notificar el reporte de validación
6. Funcionar en **dispositivos móviles, tablets y escritorios**

---

## 4. Requisitos funcionales

### 4.1 Carga de documentos

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-01 | El operador debe poder seleccionar un archivo desde su computadora | Alta |
| RF-02 | El operador debe poder arrastrar y soltar un archivo en la zona de carga | Alta |
| RF-03 | El sistema debe aceptar archivos en formato DOCX | Alta |
| RF-04 | El sistema debe rechazar archivos de otro formato con mensaje de error | Alta |
| RF-05 | El sistema debe rechazar archivos mayores a 10 MB con mensaje de error | Alta |
| RF-06 | El sistema debe mostrar el nombre, tamaño y extensión del archivo seleccionado | Media |
| RF-07 | El operador debe poder cancelar la selección y elegir otro archivo | Media |
| RF-08 | El operador debe poder ingresar el correo del estudiante (campo opcional) | Alta |
| RF-26 | El operador debe poder solicitar el envío de observaciones por correo al estudiante (casilla opt-in, habilitada solo con correo válido) | Alta |

### 4.2 Validación

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-09 | El operador debe poder iniciar la validación con un clic en "Validar" | Alta |
| RF-10 | El sistema debe mostrar un indicador de carga durante el proceso | Alta |
| RF-11 | El sistema debe enviar el archivo al endpoint POST /validar del backend | Alta |
| RF-12 | El sistema debe enviar el correo del estudiante y la solicitud de envío (`notificar=true`) en la misma petición POST /validar | Alta |
| RF-13 | Si la API no está disponible, el sistema debe mostrar datos de ejemplo (modo demo, avisado) | Baja |

### 4.3 Reporte de resultados

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-14 | El sistema debe mostrar un semáforo verde (cumple) o rojo (no cumple) | Alta |
| RF-15 | El sistema debe mostrar el total de reglas evaluadas, errores y advertencias | Alta |
| RF-16 | El operador debe poder filtrar resultados por severidad (errores, advertencias) | Alta |
| RF-17 | El operador debe poder ver resultados agrupados por categoría | Alta |
| RF-18 | El operador debe poder expandir/colapsar cada categoría | Alta |
| RF-19 | Cada regla debe mostrar el valor esperado y el valor encontrado | Alta |
| RF-20 | El sistema debe mostrar el estado de la notificación por correo (`enviado`, `fallo` con detalle técnico, `sin_correo`, `no_solicitado`, `deshabilitado` con nota de configuración para administradores cuando el backend envía `detalle`; sin badge en `sin_observaciones` y en `deshabilitado` sin `detalle`) | Media |

### 4.4 Prompts IA

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-21 | El sistema debe generar un prompt por cada regla fallida | Alta |
| RF-22 | El operador debe poder copiar el prompt al portapapeles con un clic | Alta |
| RF-23 | El sistema debe confirmar visualmente que el prompt fue copiado | Media |

### 4.5 Navegación

| ID | Requisito | Prioridad |
|----|-----------|-----------|
| RF-24 | El operador debe poder volver a la pantalla de carga desde el reporte | Alta |
| RF-25 | La aplicación debe ser una sola página (SPA) con vista intercalada | Media |

> **Nota de renumeración (S7):** respecto a la versión original se **eliminaron intencionalmente** dos requisitos que ninguna vez se implementaron y que quedan fuera del alcance del MVP:
> - RF-13 antiguo — *porcentaje de cumplimiento* (no existe en la app; el resumen usa KPIs de reglas/errores/advertencias).
> - RF-16 antiguo — *búsqueda de reglas por nombre/mensaje* (no existe en la app; sí existen los filtros por severidad).
>
> Los ID restantes se renumeraron de forma correlativa (RF-01…RF-25). En S7 se
> **agregó RF-26** (casilla opt-in de envío por correo) sin renumerar el resto.

---

## 5. Requisitos no funcionales

| ID | Requisito | Categoría |
|----|-----------|-----------|
| RNF-01 | La interfaz debe funcionar en dispositivos móviles (320px mínimo) | Usabilidad |
| RNF-02 | La interfaz debe adaptarse a tablets (600px+) y escritorios (900px+) | Usabilidad |
| RNF-03 | El sistema debe soportar modo oscuro | Usabilidad |
| RNF-04 | Los colores deben tener contraste suficiente (WCAG 2.1 AA) | Accesibilidad |
| RNF-05 | Los elementos interactivos deben ser navegables por teclado | Accesibilidad |
| RNF-06 | Los componentes deben tener atributos ARIA para lectores de pantalla | Accesibilidad |
| RNF-07 | La interfaz debe cargar en menos de 3 segundos en conexión normal | Rendimiento |
| RNF-08 | Los componentes React deben ser modulares y reutilizables | Mantenibilidad |

---

## 6. Restricciones técnicas

- **Frontend:** React 18 + Vite (sin TypeScript, solo JSX)
- **API:** Endpoint existente POST /validar (fastapi, por Integrante 1)
- **Formato de respuesta:** JSON con semáforo, resultados y prompts IA
- **Sin persistencia:** La app no almacena resultados (stateful en memoria)
- **Sin autenticación:** Acceso abierto sin login

---

## 7. Lista de funcionalidades principales

| # | Pantalla | Funcionalidad | Descripción |
|---|----------|---------------|-------------|
| 1 | Carga | Seleccionar archivo | Botón o drag-and-drop para elegir DOCX |
| 2 | Carga | Validar tipo y tamaño | Rechazo automático de formatos inválidos y archivos grandes |
| 3 | Carga | Capturar correo estudiante | Campo opcional para notificación por correo |
| 4 | Carga | Iniciar validación | Botón "Validar" que envía archivo, correo y opt-in `notificar` al backend |
| 5 | Reporte | Ver semáforo | Indicador verde/rojo del resultado general |
| 6 | Reporte | Ver resumen | KPIs: total reglas, errores, advertencias |
| 7 | Reporte | Filtrar por severidad | Chips para alternar entre todos/errores/advertencias |
| 8 | Reporte | Ver por categoría | Secciones expandibles agrupadas |
| 9 | Reporte | Ver estado de notificación | Badge según `notificacion.estado`: enviado / fallo (con detalle) / falta correo / no solicitado / deshabilitado (nota de config. para admins, con detalle) |
| 10 | Reporte | Copiar prompts IA | Botón para copiar cada prompt al portapapeles |
| 11 | Navegación | Volver a cargar | Botón para regresar a la pantalla de carga |

---

## 8. Referencias

- **Mockup de carga:** `mockups/carga.html`
- **Mockup de reporte:** `mockups/reporte.html`
- **Contrato de API:** `docs/CONTRATO_API.md`
- **Guía del proyecto:** `AGENTS.md`

---

## 9. Evidencia de producto

| Evidencia | Descripción |
|-----------|-------------|
| Documento de requisitos | Este archivo (`01_requisitos_interfaz.md`) |
| Lista de funcionalidades | Sección 7 de este documento |
| Mockups de interfaces | `mockups/carga.html`, `mockups/reporte.html` |
