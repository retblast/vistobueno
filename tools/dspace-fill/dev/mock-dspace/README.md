# Ensayo general (mock-dspace)

Simulación local del flujo de depósito para ejercitar el userscript **sin
Tampermonkey y sin tocar la instancia real**. El mock imita el DOM del
formulario oficial (mismos `name`/`id`); la lógica Angular se reduce al
mínimo indispensable (filas repetibles, combobox, botón Depositar).

Qué SÍ cubre: la lógica del userscript (compuertas, mapeador, ejecutor,
buzón, timestamp, handle) y la mecánica DOM de relleno. Qué NO cubre: los
comportamientos del Angular real — esos quedan para el piloto con la
instancia real (borrador descartable).

## Requisitos

- VistoBueno corriendo: `nix run .#serve -- validator.api:app --port 8000`
- El mock: `nix run .#mock-dspace` (puerto 8080)
- Un DOCX de prueba (la plantilla de `recursos/` o el doc bueno del factory)
- El dist construido: `cd tools/dspace-fill && npm run build` (o `npm test`)

## Checklist (10 pasos)

1. Abre `http://127.0.0.1:8080/` — debe mostrar el índice con el flujo.
2. Entra a `http://127.0.0.1:8080/mock/submit` — el botón verde flotante
   dice "consultar buzón" y el panel dice "Sin ficha en el buzón".
3. Pulsa **"Publicar ficha de prueba"** (botón azul): publica una ficha
   completa (con manuales) en el buzón de la API real vía el proxy.
4. Pulsa el botón verde flotante **"Rellenar"**: consulta el buzón y
   rellena el formulario. El toast muestra el resumen (lleno / a mano /
   sin dato).
5. Verifica los campos: título, autores, asesor, resumen, palabras
   clave, año, DNI (tipo + número), ORCID.
6. Verifica el combobox: "Acceso abierto" debe quedar seleccionado (el
   fix del bug dc.rights).
7. Con dos autores: el botón "+ Agregar autor" debe haber creado la fila
   extra y el segundo nombre debe estar lleno.
8. Marca **"Confirmo la licencia"** y pulsa **Depositar** → navega al
   ítem del mock → el toast dice "Handle enviado a VistoBueno ✓" y el
   indicador persistente abajo muestra el handle y el timestamp.
9. Verifica el buzón: el indicador del ítem ya lo hace (verde = OK);
   por terminal: `curl -s http://127.0.0.1:8000/deposito`.
10. Genera el papeleo con esa respuesta: `POST /fila-registro` (json,
    tsv, csv o xlsx) y `POST /constancia` (una descarga por autor; con
    `?formato=zip` incluye el registro del autor) con la ficha + handle
    + timestamp.

## Notas

- El buzón viaja por el proxy `/api-proxy/*` (same-origin): la API real
  mantiene su invariante sin-CORS; solo Tampermonkey (producción) habla
  directo con `http://localhost:8000`. El proxy descarta query strings
  (`split("?")[0]`): si un endpoint futuro los necesita, actualizar
  `server.js`.
- Reiniciar la API vacía el buzón (memoria del proceso): re-publica la
  ficha (paso 3) y repite.
- Falla visible: si algo no se llena, el toast lo nombra en "a mano" —
  ese es el comportamiento correcto, no un bug.
